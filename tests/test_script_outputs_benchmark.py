"""What run_benchmark.py reads, logs and writes, checked through its own entry point."""

import json
import logging
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import run_benchmark  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS, DatasetSpec  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402

STAMP = r"\d{8}_\d{6}"


def _toy(tmp_path, n=400):
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(rng.normal(size=(n, 3)), columns=["V1", "V2", "V3"])
    frame["Class"] = ([1] * (n // 10)) + ([0] * (n - n // 10))
    frame.loc[frame.Class == 1, "V1"] += 4.0
    csv = tmp_path / "toy.csv"
    frame.sample(frac=1, random_state=1).to_csv(csv, index=False)
    return csv


def _spec(csv, names=("zscore", "iqr")):
    return DatasetSpec("toy", csv, "Class", 1, detector_names=list(names), note="a toy note")


def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["run_benchmark", *map(str, args)])


def _messages(caplog):
    return [r.getMessage() for r in caplog.records if r.name.endswith("run_benchmark")]


def test_command_writes_four_timestamped_files_with_the_documented_content(
    tmp_path, monkeypatch, capsys, caplog
):
    csv = _toy(tmp_path)
    out = tmp_path / "a" / "b" / "results"
    _argv(
        monkeypatch,
        *("--dataset", "credit_card", "--csv", csv, "--detectors", "zscore", "iqr"),
        *("--seeds", 1, 2, "--results-dir", out),
    )
    with caplog.at_level(logging.INFO):
        run_benchmark.main()
    names = sorted(path.name for path in out.iterdir())
    patterns = [
        rf"benchmark_credit_card_{STAMP}\.csv",
        rf"benchmark_credit_card_{STAMP}\.md",
        rf"run_benchmark_credit_card_{STAMP}\.json",
        rf"split_ids_credit_card_{STAMP}\.json\.gz",
    ]
    assert [bool(re.fullmatch(p, n)) for p, n in zip(sorted(patterns), names, strict=True)] == [
        True
    ] * 4
    spec = replace_csv(DATASETS["credit_card"], csv, ["zscore", "iqr"])
    mean, std = run_benchmark.run(spec, [1, 2])
    table = next(out.glob("benchmark_*.csv"))
    expected = mean.join(std, lsuffix="_mean", rsuffix="_std")
    written = pd.read_csv(table, index_col="detector")
    assert written.columns.tolist() == expected.columns.tolist()
    steady = [c for c in expected.columns if not c.startswith("detect_s")]
    pd.testing.assert_frame_equal(written[steady], expected[steady])
    header = "credit_card, 2 seeds, mean ± std on the 15% test split.\n\n"
    markdown = header + run_benchmark.to_markdown(mean, std)
    saved = next(out.glob("benchmark_*.md")).read_text()
    assert _without_time(saved) == _without_time(markdown)
    assert _without_time(capsys.readouterr().out) == _without_time("\n" + markdown + "\n")
    stamp = re.search(STAMP, table.name).group()
    messages = _messages(caplog)
    assert f"dataset credit_card: {DATASETS['credit_card'].note}" in messages
    assert f"saved -> experiments/results/benchmark_credit_card_{stamp}.csv" == messages[-1]


def _without_time(markdown):
    """Drop the last table column (latency), which differs from run to run."""
    return "\n".join(
        line.rsplit("|", 2)[0] if line.startswith("|") else line for line in markdown.split("\n")
    )


def replace_csv(spec, csv, names):
    from dataclasses import replace

    return replace(spec, csv=csv, detector_names=names)


def test_record_describes_the_protocol_exactly(tmp_path, monkeypatch):
    csv = _toy(tmp_path)
    out = tmp_path / "results"
    _argv(
        monkeypatch,
        *("--dataset", "credit_card", "--csv", csv, "--detectors", "zscore"),
        *("--seeds", 3, "--results-dir", out, "--fit-sample", 50),
    )
    run_benchmark.main()
    record = json.loads(next(out.glob("run_benchmark_*.json")).read_text())
    assert record["experiment"] == "real_benchmark"
    assert record["seeds"] == [3]
    assert record["dataset"]["identity"] == "credit_card"
    assert record["dataset"]["path"] == str(csv)
    assert record["settings"] == {
        "split_ratios": [0.7, 0.15, 0.15],
        "split_strategy": "stratified",
        "fit_sample": 50,
        "detectors": ["zscore"],
        "not_run": {
            "iqr": "not requested",
            "great_expectations": "not requested",
            "isolation_forest": "not requested",
            "lof": f"ineligible: {DATASETS['credit_card'].note}",
            "ocsvm": f"ineligible: {DATASETS['credit_card'].note}",
        },
        "features": ["V1", "V2", "V3"],
        "calibration": "train_prevalence",
        "fixed_contamination": None,
        "pr_auc_definition": "average_precision",
    }
    assert sorted(record["outputs"]) == sorted(
        p.name for p in out.iterdir() if "run_" not in p.name
    )


def test_fixed_calibration_is_recorded_with_its_value(tmp_path, monkeypatch):
    out = tmp_path / "results"
    _argv(
        monkeypatch,
        *("--dataset", "credit_card", "--csv", _toy(tmp_path), "--detectors", "zscore"),
        *("--seeds", 1, "--results-dir", out, "--calibration", "fixed"),
        *("--fixed-contamination", 0.05),
    )
    run_benchmark.main()
    settings = json.loads(next(out.glob("run_benchmark_*.json")).read_text())["settings"]
    assert (settings["calibration"], settings["fixed_contamination"]) == ("fixed", 0.05)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--detectors", "lof"], "detectors not eligible for credit_card: ['lof']"),
        (["--fit-sample", "0"], "--fit-sample must be positive"),
        (["--fit-sample", "-3"], "--fit-sample must be positive"),
        (["--calibration", "fixed"], "fixed contamination must be between"),
        (
            ["--calibration", "fixed", "--fixed-contamination", "0.9"],
            "fixed contamination must be between",
        ),
        (["--fixed-contamination", "0.02"], "--fixed-contamination requires --calibration fixed"),
    ],
)
def test_invalid_options_stop_before_any_work(tmp_path, monkeypatch, capsys, args, message):
    out = tmp_path / "results"
    _argv(monkeypatch, "--dataset", "credit_card", *args, "--results-dir", out)
    with pytest.raises(SystemExit) as stopped:
        run_benchmark.main()
    assert stopped.value.code == 2
    assert message in capsys.readouterr().err
    assert not out.exists()


def test_defaults_and_help(monkeypatch, capsys):
    _argv(monkeypatch, "--help")
    with pytest.raises(SystemExit):
        run_benchmark.main()
    out = capsys.readouterr().out
    assert "Benchmark the detectors on a real dataset." in out
    for option in ("--dataset", "--csv", "--detectors", "--results-dir", "--seeds"):
        assert option in out
    assert "--calibration {train_prevalence,fixed}" in out
    assert "--fit-sample" in out


def test_default_dataset_seeds_and_directory(tmp_path, monkeypatch):
    seen = {}

    def fake_run(spec, seeds, fit_sample, calibration, fixed):
        seen.update(name=spec.name, seeds=seeds, fit=fit_sample, calibration=calibration)
        raise RuntimeError("stop")

    monkeypatch.setattr(run_benchmark, "run", fake_run)
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "default-results")
    _argv(monkeypatch)
    with pytest.raises(RuntimeError, match="^stop$"):
        run_benchmark.main()
    assert seen == {
        "name": "credit_card",
        "seeds": list(config.BENCHMARK_SEEDS),
        "fit": None,
        "calibration": "train_prevalence",
    }


def test_run_logs_the_population_and_every_detector_result(tmp_path, caplog):
    csv = _toy(tmp_path)
    spec = _spec(csv)
    frame = spec.load()
    with caplog.at_level(logging.INFO):
        mean, _ = run_benchmark.run(spec, [4])
    messages = _messages(caplog)
    anomalies = int(frame[ANOMALY_COLUMN].sum())
    assert messages[0] == f"loading {csv}"
    assert messages[1] == (
        f"{len(frame)} rows x {frame.shape[1]} cols, {anomalies} anomalies "
        f"({100 * frame[ANOMALY_COLUMN].mean():.3f}%)"
    )
    single = run_benchmark.evaluate(spec, frame, 4, None)
    for name, line in zip(["zscore", "iqr"], messages[2:], strict=True):
        row = single.loc[name]
        assert line == (
            f"  seed 4 {name:<18} P={row.precision:.3f} R={row.recall:.3f} F1={row.f1:.3f} "
            f"ROC={row.roc_auc:.3f} PR={row.pr_auc:.3f} flag={row.flagged_pct:.1f}%"
        )
    assert list(mean.index) == ["zscore", "iqr"]


def test_seed_mean_and_spread_are_taken_per_detector_across_seeds(tmp_path):
    spec = _spec(_toy(tmp_path))
    frame = spec.load()
    mean, std = run_benchmark.run(spec, [1, 2, 3])
    per_seed = [run_benchmark.evaluate(spec, frame, s, None) for s in (1, 2, 3)]
    for detector in ("zscore", "iqr"):
        for column in ("precision", "recall", "f1", "roc_auc", "pr_auc"):
            values = [frame_.loc[detector, column] for frame_ in per_seed]
            assert mean.loc[detector, column] == pytest.approx(np.mean(values))
            assert std.loc[detector, column] == pytest.approx(np.std(values, ddof=1))


def test_fit_sample_caps_the_training_rows_without_touching_the_scored_rows(
    tmp_path, monkeypatch, tracking_detector
):
    spec = _spec(_toy(tmp_path), names=("zscore",))
    frame = spec.load()
    train, _, test = stratified_split(frame, ANOMALY_COLUMN, config.SPLIT_RATIOS, 6)
    monkeypatch.setattr(run_benchmark, "all_detectors", lambda **_: [tracking_detector])
    for cap, size in ((20, 20), (len(train), len(train)), (len(train) + 50, len(train))):
        run_benchmark.evaluate(spec, frame, 6, cap)
        assert len(tracking_detector.fit_input) == size
        assert len(tracking_detector.predict_input) == len(test)
        assert tracking_detector.fit_input.columns.tolist() == ["V1", "V2", "V3"]
    run_benchmark.evaluate(spec, frame, 6, 20)
    expected = spec.features(train).sample(n=20, random_state=6)
    pd.testing.assert_frame_equal(tracking_detector.fit_input, expected)
    run_benchmark.evaluate(spec, frame, 6, None)
    assert len(tracking_detector.fit_input) == len(train)


def test_unrun_detectors_carry_a_reason_that_depends_on_the_cause():
    spec = DatasetSpec("d", Path("x.csv"), "y", 1, detector_names=["zscore"], note="why")
    reasons = run_benchmark.not_run(spec, eligible=["zscore", "iqr"])
    assert reasons["iqr"] == "not requested"
    assert reasons["lof"] == "ineligible: why"
    assert "zscore" not in reasons


def test_markdown_table_has_a_header_a_separator_and_one_row_per_detector():
    mean = pd.DataFrame(
        {c: [0.5, 0.25] for c in run_benchmark.METRIC_COLUMNS}, index=["zscore", "iqr"]
    )
    std = mean.copy() / 10
    std.loc["iqr"] = np.nan
    columns = run_benchmark.METRIC_COLUMNS
    expected = "\n".join(
        [
            "| detector | " + " | ".join(columns) + " |",
            "| --- | " + " | ".join("---" for _ in columns) + " |",
            "| zscore | " + " | ".join("0.500 ± 0.050" for _ in columns) + " |",
            "| iqr | " + " | ".join("0.250 ± n/a" for _ in columns) + " |",
        ]
    )
    assert run_benchmark.to_markdown(mean, std) == expected + "\n"


def test_a_cap_as_large_as_the_training_set_leaves_it_untouched_and_run_forwards_the_cap(
    tmp_path, monkeypatch, tracking_detector
):
    spec = _spec(_toy(tmp_path), names=("zscore",))
    frame = spec.load()
    train, _, _ = stratified_split(frame, ANOMALY_COLUMN, config.SPLIT_RATIOS, 6)
    monkeypatch.setattr(run_benchmark, "all_detectors", lambda **_: [tracking_detector])
    run_benchmark.evaluate(spec, frame, 6, len(train))
    pd.testing.assert_frame_equal(tracking_detector.fit_input, spec.features(train))
    run_benchmark.run(spec, [6], fit_sample=25)
    assert len(tracking_detector.fit_input) == 25


def test_dataset_choices_are_listed_and_checked(tmp_path, monkeypatch, capsys):
    _argv(monkeypatch, "--dataset", "unknown", "--results-dir", tmp_path)
    with pytest.raises(SystemExit):
        run_benchmark.main()
    assert "invalid choice: 'unknown' (choose from 'cardio', 'credit_card', 'water_quality')" in (
        capsys.readouterr().err
    )


def test_option_help_texts_describe_what_each_option_does(monkeypatch, capsys):
    _argv(monkeypatch, "--help")
    with pytest.raises(SystemExit):
        run_benchmark.main()
    text = " ".join(capsys.readouterr().out.split())
    for sentence in (
        "local CSV override for a declared dataset schema",
        "subset of this dataset's detectors",
        "cap the train set at N rows before fitting (bounds quadratic models)",
    ):
        assert sentence in text


def test_a_run_without_options_uses_the_configured_result_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "configured")
    _argv(monkeypatch, "--csv", _toy(tmp_path), "--detectors", "zscore", "--seeds", 1)
    run_benchmark.main()
    assert len(list((tmp_path / "configured").glob("run_benchmark_credit_card_*.json"))) == 1
    record = json.loads(next((tmp_path / "configured").glob("run_benchmark_*.json")).read_text())
    assert record["settings"]["fit_sample"] is None


def test_a_second_run_may_reuse_the_result_directory_and_stamps_are_utc(tmp_path, monkeypatch):
    out = tmp_path / "results"
    args = ["--csv", _toy(tmp_path), "--detectors", "zscore", "--seeds", 1, "--results-dir", out]
    from datetime import UTC, datetime

    for _ in range(2):
        _argv(monkeypatch, *args)
        run_benchmark.main()
    now = datetime.now(UTC).replace(tzinfo=None)
    stamp = re.search(STAMP, next(out.glob("benchmark_*.csv")).name).group()
    written = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
    assert abs((now - written).total_seconds()) < 120


def test_the_split_archive_records_the_requested_fit_sample(tmp_path, monkeypatch):
    out = tmp_path / "results"
    _argv(
        monkeypatch,
        *("--csv", _toy(tmp_path), "--detectors", "zscore", "--seeds", 5),
        *("--results-dir", out, "--fit-sample", 30),
    )
    run_benchmark.main()
    from provenance import read_split_ids

    parts = read_split_ids(next(out.glob("split_ids_*.json.gz")))["seeds"]["5"]
    assert len(parts["fit"]) == 30 and set(parts["fit"]) <= set(parts["train"])


def test_the_pipeline_logger_is_quietened_for_great_expectations(tmp_path, monkeypatch):
    logging.getLogger("great_expectations").setLevel(logging.NOTSET)
    _argv(
        monkeypatch,
        *("--csv", _toy(tmp_path), "--detectors", "zscore", "--seeds", 1),
        *("--results-dir", tmp_path / "r"),
    )
    run_benchmark.main()
    assert logging.getLogger("great_expectations").level == logging.WARNING


def test_a_fit_sample_of_one_row_is_accepted(tmp_path, monkeypatch):
    out = tmp_path / "results"
    _argv(
        monkeypatch,
        *("--csv", _toy(tmp_path), "--detectors", "zscore", "--seeds", 1),
        *("--results-dir", out, "--fit-sample", 1),
    )
    run_benchmark.main()
    assert (
        json.loads(next(out.glob("run_benchmark_*.json")).read_text())["settings"]["fit_sample"]
        == 1
    )
