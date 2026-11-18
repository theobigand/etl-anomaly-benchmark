"""What one seed of the complete-registry study hands to the split, the detector and the metrics."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import full_registry as fr  # noqa: E402


def _stand_ins(monkeypatch, failing=()):
    seen = {"build": [], "capped": [], "detect": [], "split": []}

    def split(df, column, ratios, seed):
        seen["split"].append((df, column, ratios, seed))
        return df.iloc[:6], df.iloc[6:8], df.iloc[8:]

    def build(name, contamination, seed):
        seen["build"].append((name, contamination, seed))
        return SimpleNamespace(name=name, settings=lambda: {"name": name})

    def capped(frame, name, seed):
        seen["capped"].append((name, seed))
        return ("capped", name, seed)

    def detect(test_x, detector, fit_df=None):
        seen["detect"].append((detector.name, fit_df))
        if detector.name in failing:
            raise RuntimeError(f"{detector.name} failed")
        flags = pd.Series([True] + [False] * (len(test_x) - 1), index=test_x.index)
        return SimpleNamespace(
            flags=flags, scores=np.arange(len(test_x), dtype=float), detect_s=0.5
        )

    monkeypatch.setattr(fr, "stratified_split", split)
    monkeypatch.setattr(fr, "build", build)
    monkeypatch.setattr(fr, "capped", capped)
    monkeypatch.setattr(fr, "detect", detect)
    return seen


def _real_frame():
    return pd.DataFrame({"x": range(10), fr.ANOMALY_COLUMN: [0, 1] * 5})


def _spec():
    return SimpleNamespace(features=lambda frame: frame[["x"]])


def test_a_real_split_uses_the_dataset_label_the_configured_ratios_and_the_seed(monkeypatch):
    seen = _stand_ins(monkeypatch)
    df = _real_frame()
    fr.real_seed(_spec(), df, 7, ["vae"])
    frame, column, ratios, seed = seen["split"][0]
    assert frame is df and column == fr.ANOMALY_COLUMN
    assert ratios == fr.config.SPLIT_RATIOS and seed == 7


def test_each_detector_gets_the_training_contamination_the_seed_and_the_capped_training_rows(
    monkeypatch,
):
    seen = _stand_ins(monkeypatch)
    out = fr.real_seed(_spec(), _real_frame(), 7, ["vae", "lunar"])
    train_label = _real_frame().iloc[:6][fr.ANOMALY_COLUMN]
    expected = fr.calibrate_contamination(train_label)
    assert seen["build"] == [("vae", expected, 7), ("lunar", expected, 7)]
    assert seen["capped"] == [("vae", 7), ("lunar", 7)]
    assert seen["detect"] == [("vae", ("capped", "vae", 7)), ("lunar", ("capped", "lunar", 7))]
    assert out["seed"] == 7 and out["fit_rows"] == 6 and set(out["methods"]) == {"vae", "lunar"}
    row = out["methods"]["vae"]
    assert row["detect_s"] == 0.5 and row["settings"] == {"name": "vae"}
    assert {"precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"} <= set(row)


def test_a_failing_detector_is_recorded_and_the_next_ones_still_run(monkeypatch):
    _stand_ins(monkeypatch, failing={"vae"})
    out = fr.real_seed(_spec(), _real_frame(), 1, ["vae", "lunar"])
    assert out["methods"]["vae"] == {"error": "RuntimeError('vae failed')"}
    assert "f1" in out["methods"]["lunar"]


def test_the_real_summary_skips_a_detector_without_any_success_and_keeps_the_next_ones():
    def row(value):
        return {m: value for m in fr.METRICS}

    runs = [
        {"methods": {"bad": {"error": "x"}, "good": row(0.5)}},
        {"methods": {"bad": {"error": "y"}, "good": row(1.0)}},
    ]
    table = fr.real_summary(runs, ["bad", "good"])
    assert list(table.index) == ["good"]
    assert table.loc["good", "f1_mean"] == pytest.approx(0.75)
    assert table.loc["good", "seeds"] == 2


def _synthetic_frame(n=40):
    types = ["clean"] * (n - 8) + [
        "univariate_outlier", "multivariate_outlier", "temporal_drift", "missing_value",
        "invalid_format", "duplicate", "univariate_outlier", "temporal_drift",
    ]  # fmt: skip
    frame = pd.DataFrame({c: np.linspace(0, 1, n) for c in fr.FEATURE_COLUMNS})
    frame["anomaly_type"] = types
    frame["anomaly"] = [t != "clean" for t in types]
    return frame


def _synthetic_stand_ins(monkeypatch, failing=()):
    seen = _stand_ins(monkeypatch, failing)
    frame = _synthetic_frame()
    made = []
    monkeypatch.setattr(fr, "make_synthetic", lambda **kw: made.append(kw) or frame)
    monkeypatch.setattr(
        fr.rsb,
        "_split_synthetic",
        lambda df, seed: seen["split"].append(("synthetic", seed)) or (df, df.iloc[:0], df),
    )
    return seen, made, frame


@pytest.mark.parametrize(
    ("rows", "expected"), [(None, {"seed": 4}), (0, {"seed": 4}), (300, {"seed": 4, "n_rows": 300})]
)
def test_the_synthetic_table_is_made_with_the_seed_and_a_row_count_only_when_one_is_given(
    monkeypatch, rows, expected
):
    _seen, made, _frame = _synthetic_stand_ins(monkeypatch)
    fr.synthetic_seed(4, rows, ["vae"])
    assert made == [expected]


def test_a_synthetic_seed_splits_by_identity_and_gives_each_detector_the_training_prevalence(
    monkeypatch,
):
    seen, _made, frame = _synthetic_stand_ins(monkeypatch)
    out = fr.synthetic_seed(4, None, ["vae"])
    assert ("synthetic", 4) in seen["split"]
    assert seen["build"] == [("vae", float(frame["anomaly"].mean()), 4)]
    assert seen["capped"] == [("vae", 4)]
    assert seen["detect"] == [("vae", ("capped", "vae", 4))]
    assert out["seed"] == 4 and out["errors"] == {}


def test_a_synthetic_seed_reports_recall_precision_false_alarms_metrics_and_settings(monkeypatch):
    _seen, _made, frame = _synthetic_stand_ins(monkeypatch)
    out = fr.synthetic_seed(4, None, ["vae"])
    assert set(out) == {"seed", "recall", "precision", "fpr", "metrics", "settings", "errors"}
    assert out["recall"]["index"] == ["vae"] and out["recall"]["columns"] == fr.ANOMALY_TYPES
    assert out["precision"]["index"] == ["vae"] and out["precision"]["columns"] == fr.ANOMALY_TYPES
    json.dumps(out["recall"])
    clean = frame["anomaly_type"] == "clean"
    flags = pd.Series([True] + [False] * (len(frame) - 1), index=frame.index)
    assert out["fpr"] == {"vae": float(flags[clean].mean())}
    assert set(out["metrics"]["vae"]) >= {"precision", "recall", "f1"}
    assert out["settings"]["vae"]["name"] == "vae" and out["settings"]["vae"]["seconds"] >= 0


def test_the_synthetic_seconds_are_the_time_the_detector_took_not_the_clock_sum(monkeypatch):
    _synthetic_stand_ins(monkeypatch)
    clock = iter([100.0, 103.0])
    monkeypatch.setattr(fr.time, "perf_counter", lambda: next(clock))
    out = fr.synthetic_seed(4, None, ["vae"])
    assert out["settings"]["vae"]["seconds"] == 3.0


def test_a_failing_synthetic_detector_is_named_in_the_errors_and_the_others_run(monkeypatch):
    _synthetic_stand_ins(monkeypatch, failing={"vae"})
    out = fr.synthetic_seed(4, None, ["vae", "lunar"])
    assert out["errors"] == {"vae": "RuntimeError('vae failed')"}
    assert out["recall"]["index"] == ["lunar"] and list(out["fpr"]) == ["lunar"]


def _help(capsys, *argv):
    with pytest.raises(SystemExit):
        fr.main([*argv, "--help"])
    return capsys.readouterr().out


def test_the_command_line_describes_itself_and_each_command(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    text = _help(capsys)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    assert any(
        line.startswith("Neural detectors on the real datasets and the synthetic") for line in lines
    )
    assert "real neural detectors on Credit Card, Cardio and Water Quality" in lines
    assert "synthetic neural detectors on the synthetic matrix" in lines
    assert "summary hypotheses H3 to H5 from the archived matrices" in lines
    summary = [" ".join(line.split()) for line in _help(capsys, "summary").splitlines()]
    assert "default: the synthetic runs in --output" in summary


def test_the_summary_reads_its_classical_matrix_from_the_archived_evidence_by_default(
    tmp_path, monkeypatch
):
    seen = {}
    monkeypatch.setattr(fr, "mean_matrix", lambda runs: pd.DataFrame())
    monkeypatch.setattr(
        fr, "_published", lambda path: seen.update(path=path) or (_ for _ in ()).throw(KeyError)
    )
    with pytest.raises(KeyError):
        fr.main(["summary", "--output", str(tmp_path / "o")])
    assert seen["path"] == fr.ROOT / "verification/evidence/synthetic_recall.csv"
    assert isinstance(seen["path"], Path)


@pytest.mark.parametrize("command", ["real", "synthetic", "summary"])
def test_every_command_requires_an_output_folder(command):
    with pytest.raises(SystemExit) as stop:
        fr.main([command])
    assert stop.value.code == 2


def test_the_runs_of_a_real_dataset_are_stored_under_runs_and_each_seed_is_flushed(
    tmp_path, monkeypatch
):
    spec = SimpleNamespace(load=lambda: "frame")
    monkeypatch.setattr(fr, "DATASETS", {"toy": spec})
    monkeypatch.setattr(fr, "real_seed", lambda s, df, seed: {"seed": seed})
    collected = []
    monkeypatch.setattr(fr, "real_summary", lambda runs: collected.append(runs) or pd.DataFrame())
    flushes = []
    monkeypatch.setattr(fr, "print", lambda *a, **k: flushes.append(k), raising=False)
    fr.main(["real", "--output", str(tmp_path / "o")])
    stored = json.loads((tmp_path / "o/real_toy.json").read_text())
    assert stored["runs"] == [{"seed": s} for s in fr.SEEDS]
    assert collected == [[{"seed": s} for s in fr.SEEDS]]
    assert flushes == [{"flush": True}] * len(fr.SEEDS)
    flushes.clear()
    monkeypatch.setattr(fr, "synthetic_seed", lambda seed, rows: {"seed": seed})
    fr.main(["synthetic", "--output", str(tmp_path / "s")])
    assert flushes == [{"flush": True}] * len(fr.SEEDS)
