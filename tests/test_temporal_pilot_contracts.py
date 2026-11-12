"""Temporal pilot: exact definitions, recorded fields and the command line."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "experiments"))
import temporal_pilot as tp  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DatasetSpec  # noqa: E402
from etl_benchmark.quality.window_drift import WindowDriftMonitor, event_metrics  # noqa: E402
from etl_benchmark.split import chronological_split, stratified_split  # noqa: E402

MSG = "elapsed times must be finite and non-negative"


@pytest.mark.parametrize("bad", [[-1.0, 2.0], [np.nan, 1.0], ["a", "b"]])
def test_invalid_elapsed_times_are_refused_with_the_stated_reason(bad):
    with pytest.raises(ValueError, match=f"^{MSG}$"):
        tp.to_timestamps(pd.Series(bad))


def test_numeric_strings_are_read_as_seconds_and_fractions_are_kept():
    stamps = tp.to_timestamps(pd.Series(["0", "1.5", 90.0]))
    assert [(s - tp.ORIGIN).total_seconds() for s in stamps] == [0.0, 1.5, 90.0]


def test_time_blocks_floor_to_whole_intervals_also_before_the_origin_and_for_naive_times():
    naive = pd.Series(
        pd.to_datetime(["1969-12-31 23:59:59", "1970-01-01 00:29:59", "1970-01-01 00:30:00"])
    )
    assert tp.time_blocks(naive, 1800).tolist() == [-1, 0, 1]
    aware = pd.Series(pd.to_datetime([0, 1799, 1800, 5400], unit="s", utc=True))
    assert tp.time_blocks(aware, 1800).tolist() == [0, 0, 1, 3]
    strings = pd.Series(["1970-01-01T00:30:00Z", "1970-01-01T00:59:59Z"])
    assert tp.time_blocks(strings, 1800).tolist() == [1, 1]


def _reference(y, s, times, block_seconds, resamples, seed):
    seconds = (pd.to_datetime(times, utc=True) - tp.ORIGIN).dt.total_seconds().to_numpy()
    blocks = np.floor(seconds / block_seconds).astype(int)
    groups = [np.flatnonzero(blocks == b) for b in np.unique(blocks)]
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(resamples):
        index = np.concatenate([groups[i] for i in rng.choice(len(groups), len(groups))])
        if y[index].min() != y[index].max():
            values.append(average_precision_score(y[index], s[index]))
    return values


def _data(n=300, seed=2):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.2).astype(int)
    s = y * 0.7 + rng.normal(size=n)
    times = pd.Series(pd.date_range("2024-01-01", periods=n, freq="20min"))
    return y, s, times


def test_the_bootstrap_interval_equals_its_definition_block_by_block():
    y, s, times = _data()
    got = tp.block_bootstrap_ci(y, s, times, 6 * 3600, 120, 9)
    values = _reference(y, s, times, 6 * 3600, 120, 9)
    assert set(got) == {"estimate", "ci_low", "ci_high", "resamples_used"}
    assert got["resamples_used"] == len(values)
    assert got["ci_low"] == pytest.approx(np.percentile(values, 2.5), abs=1e-12)
    assert got["ci_high"] == pytest.approx(np.percentile(values, 97.5), abs=1e-12)
    assert got["estimate"] == pytest.approx(average_precision_score(y, s))


def test_the_bootstrap_refusals_state_the_problem_and_catch_each_length_mismatch():
    y, s, times = _data(50)
    for args in ((y, s[:-1], times), (y, s, times[:-1]), (y[:-1], s, times)):
        with pytest.raises(ValueError, match="^labels, scores and times must have equal length$"):
            tp.block_bootstrap_ci(*args, 3600, 5, 1)
    with pytest.raises(ValueError, match="^both classes are required$"):
        tp.block_bootstrap_ci(np.zeros(50, int), s, times, 3600, 5, 1)
    missing = s.astype(object)
    missing[2] = None
    with pytest.raises(ValueError):
        tp.block_bootstrap_ci(y, missing, times, 3600, 5, 1)


def test_a_shift_is_applied_to_times_given_as_strings_and_the_boundary_row_is_shifted():
    frame = pd.DataFrame(
        {tp.TIME_UTC: ["1970-01-01T00:00:10Z", "1970-01-01T00:00:20Z"], "V1": [0.0, 0.0]}
    )
    out = tp.inject_shift(
        frame, ["V1"], pd.Timestamp("1970-01-01T00:00:20Z"), 1.0, pd.Series({"V1": 2.0})
    )
    assert out["V1"].tolist() == [0.0, 2.0]


def _stream(n=9000, seed=0):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(rng.normal(size=(n, 3)), columns=["V1", "V2", "V3"])
    frame["V3"] = 7.0  # a constant column: its scale must be 1, not 0
    frame[tp.TIME_UTC] = tp.to_timestamps(pd.Series(np.arange(n, dtype=float)))
    return frame


def test_the_monitor_control_reports_what_an_independent_evaluation_gives():
    frame = _stream()
    train, val, test = frame.iloc[:3000], frame.iloc[3000:6000], frame.iloc[6000:]
    cols = ["V1", "V2", "V3"]
    out = tp.monitor_control(train, val, test, cols, deltas=(0.0, 2.0), window_size=150)
    scale = train[cols].std(ddof=0).replace(0.0, 1.0)
    assert scale["V3"] == 1.0 and scale["V1"] == pytest.approx(train["V1"].std(ddof=0))
    monitor = WindowDriftMonitor(tp.TIME_UTC, cols, window_size=150, threshold=1e12).fit(train)
    threshold = float(monitor.evaluate(val)["score"].max())
    monitor.threshold = threshold
    val_windows = monitor.evaluate(val)
    ordered = sorted(test[tp.TIME_UTC].unique())
    change = pd.Timestamp(ordered[len(ordered) // 2])
    assert out["threshold"] == threshold and out["validation_windows"] == len(val_windows)
    assert out["validation_false_alarms"] == int(val_windows["alert"].sum())
    assert out["change_time"] == change.isoformat() and out["window_size"] == 150
    assert out["columns"] == cols and list(out["controls"]) == ["0.0", "2.0"]
    for delta in (0.0, 2.0):
        windows = monitor.evaluate(tp.inject_shift(test, cols, change, delta, scale))
        ends = pd.to_datetime(windows["window_end"], utc=True)
        after = windows[ends >= change]
        alerts = np.flatnonzero(after["alert"].to_numpy())
        metrics = event_metrics(windows, change)
        got = out["controls"][str(float(delta))]
        assert got["windows_before"] == int((ends < change).sum()) and got["windows_after"] == len(
            after
        )
        assert got["delay_windows"] == (int(alerts[0]) + 1 if len(alerts) else None)
        assert (
            got["detected"] == metrics["detected"]
            and got["false_alarm_rate"] == metrics["false_alarm_rate"]
        )
        expected_delay = metrics["detection_delay"].total_seconds() if metrics["detected"] else None
        assert got["delay_seconds"] == expected_delay
        assert set(got) == {
            "detected",
            "false_alarm_rate",
            "delay_seconds",
            "delay_windows",
            "windows_before",
            "windows_after",
        }
    assert (
        out["controls"]["2.0"]["detected"] is True and out["controls"]["2.0"]["delay_windows"] >= 1
    )


def _spec(tmp_path, n=600):
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f"V{i}" for i in range(1, 7)])
    frame.insert(0, "Time", np.sort(rng.integers(0, 3000, size=n)).astype(float))
    frame["Amount"] = rng.gamma(2.0, 20.0, size=n)
    frame["Class"] = 0
    frame.loc[rng.choice(n, size=30, replace=False), "Class"] = 1
    path = tmp_path / "toy.csv"
    frame.to_csv(path, index=False)
    return DatasetSpec("toy", path, "Class", 1, detector_names=["zscore", "iqr"])


def test_scoring_uses_the_training_prevalence_and_returns_float_scores_and_boolean_flags(
    tmp_path, monkeypatch
):
    spec = _spec(tmp_path)
    frame = tp.load(spec)
    train, _val, test = tp.chronological_partitions(frame)
    seen = []
    real = tp.all_detectors
    monkeypatch.setattr(tp, "all_detectors", lambda **kw: seen.append(kw) or real(**kw))
    out = tp.score_partition(spec, train, test)
    assert seen == [
        {"ml_contamination": float(train[ANOMALY_COLUMN].mean()), "names": ["zscore", "iqr"]}
    ]
    assert list(out["scores"]) == ["zscore", "iqr"] == list(out["flags"])
    assert out["y"].tolist() == test[ANOMALY_COLUMN].tolist()
    for name in out["scores"]:
        assert out["scores"][name].dtype == float and out["flags"][name].dtype == bool
        assert len(out["scores"][name]) == len(test) == len(out["flags"][name])


def test_partitions_follow_the_configured_ratios_and_the_given_seed(tmp_path):
    frame = tp.load(_spec(tmp_path))
    for got, want in zip(
        tp.chronological_partitions(frame),
        chronological_split(frame, tp.TIME_UTC, config.SPLIT_RATIOS),
        strict=True,
    ):
        pd.testing.assert_frame_equal(got, want)
    a = tp.stratified_partitions(frame, 3)
    for got, want in zip(
        a, stratified_split(frame, ANOMALY_COLUMN, config.SPLIT_RATIOS, 3), strict=True
    ):
        pd.testing.assert_frame_equal(got, want)
    b = tp.stratified_partitions(frame, 4)
    assert not a[0].equals(b[0])
    assert len(a[0]) == len(b[0])


def test_describe_reports_rows_frauds_prevalence_and_the_time_range():
    frame = pd.DataFrame({"Time": [5.0, 1.0, 9.0, 3.0], ANOMALY_COLUMN: [0, 1, 0, 1]})
    assert tp.describe(frame) == {
        "rows": 4,
        "frauds": 2,
        "prevalence": 0.5,
        "time_min_s": 1.0,
        "time_max_s": 9.0,
    }


def test_run_returns_the_chronological_and_stratified_arms_and_the_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "RESAMPLES", 20)
    spec = _spec(tmp_path, n=8000)
    out = tp.run(spec, seeds=(1, 2))
    assert set(out) == {"partitions", "chronological", "stratified", "drift_control", "settings"}
    assert list(out["partitions"]) == ["train", "validation", "test"]
    assert sum(p["rows"] for p in out["partitions"].values()) == len(tp.load(spec))
    for name in ("zscore", "iqr"):
        ci = out["chronological"][name]["pr_auc_ci"]
        assert (
            set(ci) == {"estimate", "ci_low", "ci_high", "resamples_used"}
            and ci["resamples_used"] <= 20
        )
        values = out["stratified"][name]["recall"]
        assert len(values["values"]) == 2 and values["mean"] == pytest.approx(
            np.mean(values["values"])
        )
        assert values["std"] == pytest.approx(np.std(values["values"], ddof=1))
    assert out["settings"] == {
        "seeds": [1, 2],
        "block_seconds": 1800,
        "resamples": 20,
        "bootstrap_seed": 42,
        "window_size": 1000,
        "deltas": [0.0, 0.5, 1.0, 2.0],
        "ratios": list(config.SPLIT_RATIOS),
    }
    assert (
        out["drift_control"]["columns"] == tp.DRIFT_COLUMNS
        and out["drift_control"]["window_size"] == 1000
    )


def test_main_records_the_data_and_script_digests_and_the_provenance(tmp_path, monkeypatch, capsys):
    spec = _spec(tmp_path)
    monkeypatch.setattr(tp, "run", lambda s: {"settings": {"seeds": [1]}, "marker": s.csv.name})
    written = []
    import provenance

    monkeypatch.setattr(provenance, "write_record", lambda path, **kw: written.append((path, kw)))
    out = tmp_path / "o" / "pilot.json"
    assert tp.main(["--output", str(out), "--csv", str(spec.csv)]) == 0
    data = json.loads(out.read_text())
    assert data["marker"] == "toy.csv"
    prov = data["provenance"]
    assert prov["dataset_sha256"] == hashlib.sha256(spec.csv.read_bytes()).hexdigest()
    assert prov["script_sha256"] == hashlib.sha256(Path(tp.__file__).read_bytes()).hexdigest()
    assert prov["protocol"] == "verification/temporal_pilot.md"
    assert set(prov) == {
        "dataset_sha256",
        "script_sha256",
        "protocol",
        "python",
        "platform",
        "machine",
        "cpu_count",
    }
    assert out.read_text() == json.dumps(data, indent=2, sort_keys=True) + "\n"
    ((path, kw),) = written
    assert path == out.with_name("run_temporal_pilot.json")
    assert kw["experiment"] == "temporal_pilot" and kw["seeds"] == list(config.BENCHMARK_SEEDS)
    assert (
        kw["dataset"] == "credit_card"
        and kw["data_path"] is None
        and kw["outputs"] == ["pilot.json"]
    )
    assert kw["settings"] == {"seeds": [1], **prov}
    assert capsys.readouterr().out == f"wrote {out}\n"


def test_the_control_shifts_by_the_population_scale_with_a_huge_first_threshold(
    monkeypatch,
):
    frame = _stream(6000)
    train, val, test = frame.iloc[:2000], frame.iloc[2000:4000], frame.iloc[4000:]
    cols = ["V1", "V2", "V3"]
    scales, ctor = [], []
    real_shift, real_init = tp.inject_shift, WindowDriftMonitor.__init__

    def spy_shift(f, c, change, delta, scale):
        scales.append(scale)
        return real_shift(f, c, change, delta, scale)

    def spy_init(self, *a, **k):
        ctor.append((a, k))
        real_init(self, *a, **k)

    monkeypatch.setattr(tp, "inject_shift", spy_shift)
    monkeypatch.setattr(WindowDriftMonitor, "__init__", spy_init)
    tp.monitor_control(train, val, test, cols, deltas=(1.0,), window_size=120)
    expected = pd.Series({"V1": train["V1"].std(ddof=0), "V2": train["V2"].std(ddof=0), "V3": 1.0})
    pd.testing.assert_series_equal(scales[0], expected)
    assert ctor == [((tp.TIME_UTC, cols), {"window_size": 120, "threshold": 1e12})]
