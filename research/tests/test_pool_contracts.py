"""Wiring, thresholds and result fields of the pool pipelines, against independent oracles."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_benchmark as lb  # noqa: E402
import pool_full as pf  # noqa: E402

from etl_benchmark.metrics import compute_metrics  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _problem(n=400, anomalies=40, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:: n // anomalies] = 1
    x[y == 1] += 5
    return x, y


def _frames():
    x, y = _problem()
    names = [f"f{i}" for i in range(4)]
    return pd.DataFrame(x[:280], columns=names), pd.DataFrame(x[280:], columns=names), y[280:]


def test_the_curve_keeps_exactly_the_documented_number_of_points_and_both_ends():
    y = np.r_[np.ones(300), np.zeros(700)].astype(int)
    scores = np.random.default_rng(0).normal(size=1000) + 2 * y
    curve = pf._curve(y, scores)
    assert len(curve["precision"]) == len(curve["recall"]) == pf.CURVE_POINTS
    assert (
        curve["recall"][0] == 1.0 and curve["recall"][-1] == 0.0 and curve["precision"][-1] == 1.0
    )
    assert set(curve) == {"precision", "recall", "average_precision"}
    short = pf._curve(np.array([0, 1, 0, 1]), np.array([0.1, 0.8, 0.3, 0.6]))
    assert len(short["precision"]) == 5 and short["recall"][0] == 1.0


def test_a_method_run_uses_the_training_prevalence_and_the_seeded_capped_fit(monkeypatch):
    train, test, y = _frames()
    seen = {}
    real_build, real_capped, real_detect = pf.build, pf.capped, pf.detect

    def build(method, contamination, seed):
        seen["build"] = (method, contamination, seed)
        return real_build(method, contamination, seed)

    def capped(frame, method, seed):
        seen["capped"] = (len(frame), method, seed)
        return real_capped(frame, method, seed)

    def detect(frame, detector, fit_df=None):
        seen["detect"] = (len(frame), len(fit_df))
        return real_detect(frame, detector, fit_df=fit_df)

    for name, function in (("build", build), ("capped", capped), ("detect", detect)):
        monkeypatch.setattr(pf, name, function)
    row = pf.run_method("hbos", train, test, y, 11, 0.125)
    assert seen["build"] == ("hbos", 0.125, 11)
    assert seen["capped"] == (280, "hbos", 11)
    assert seen["detect"] == (120, 280) and row["fit_rows"] == 280 and row["seed"] == 11


def test_the_fixed_and_sweep_tables_equal_an_independent_threshold_computation():
    train, test, y = _frames()
    row = pf.run_method("isolation_forest", train, test, y, 7, 0.1)
    detector = pf.build("isolation_forest", 0.1, 7)
    result = pf.detect(test, detector, fit_df=pf.capped(train, "isolation_forest", 7))
    kept = np.asarray(detector._model.decision_scores_, dtype=float)
    scores = result.scores.to_numpy()
    expected = compute_metrics(y, scores > np.percentile(kept, 100 * (1 - pf.FIXED)), scores)
    assert row["fixed"] == pytest.approx(expected)
    assert list(row["sweep"]) == [str(c) for c in pf.GRID]
    for contamination in pf.GRID:
        flags = scores > np.percentile(kept, 100 * (1 - contamination))
        assert row["sweep"][str(contamination)] == pytest.approx(compute_metrics(y, flags, scores))
    assert row["fixed"] != row["metrics"] and "curve" not in row


def test_a_rule_does_not_read_the_contamination_and_only_one_method_has_a_sweep():
    train, test, y = _frames()
    rule = pf.run_method("zscore", train, test, y, 7, 0.1)
    assert rule["fixed"] == rule["metrics"] and rule["fixed_is_same"] is True
    assert "sweep" not in rule
    other = pf.run_method("hbos", train, test, y, 7, 0.1)
    assert "sweep" not in other and "fixed_is_same" not in other


def test_the_curve_is_kept_for_the_curve_seed_only():
    train, test, y = _frames()
    at = pf.run_method("zscore", train, test, y, pf.CURVE_SEED, 0.1)
    away = pf.run_method("zscore", train, test, y, pf.CURVE_SEED + 1, 0.1)
    assert set(at["curve"]) == {"precision", "recall", "average_precision"}
    assert "curve" not in away and at["curve"]["average_precision"] > 0.5


@pytest.mark.parametrize("module", [lb, pf], ids=["labelled_benchmark", "pool_full"])
def test_each_seed_uses_its_own_stratified_split_and_training_prevalence(monkeypatch, module):
    x, y = _problem()
    calls = []
    real = module.nm.split

    def split(a, b, seed):
        part = real(a, b, seed)
        calls.append((seed, float(part["y_train"].mean()), len(part["y_test"])))
        return part

    monkeypatch.setattr(module.nm, "split", split)
    module.run_problem(x, y, seeds=(3, 9), methods=["zscore"])
    assert [call[0] for call in calls] == [3, 9]
    assert calls[0][1] == pytest.approx(calls[1][1], abs=0.02) and calls[0][1] > 0


def test_a_skipped_detector_does_not_stop_the_other_detectors_of_the_seed(monkeypatch):
    x, y = _problem()
    monkeypatch.setattr(pf.nm, "skipped_detectors", lambda rows: ["iqr"])
    result = pf.run_problem(x, y, seeds=(1,), methods=["iqr", "zscore", "hbos"])
    assert result["skipped"] == ["iqr"] and sorted(result["runs"]) == ["hbos", "zscore"]
    monkeypatch.setattr(lb.nm, "skipped_detectors", lambda rows: ["iqr"])
    other = lb.run_problem(x, y, seeds=(1,), methods=["iqr", "zscore", "hbos"])
    assert other["skipped"] == ["iqr"] and sorted(other["metrics"]) == ["hbos", "zscore"]


@pytest.mark.parametrize("module", [lb, pf], ids=["labelled_benchmark", "pool_full"])
def test_a_failed_detector_records_its_seed_and_the_error_under_the_method(monkeypatch, module):
    x, y = _problem()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(module, "detect" if module is lb else "run_method", boom)
    result = module.run_problem(x, y, seeds=(5, 6), methods=["zscore", "iqr"])
    expected = [
        {"seed": 5, "error": "RuntimeError('boom')"},
        {"seed": 6, "error": "RuntimeError('boom')"},
    ]
    assert result["errors"] == {"zscore": expected, "iqr": expected}


@pytest.mark.parametrize("module", [lb, pf], ids=["labelled_benchmark", "pool_full"])
def test_a_failed_job_keeps_the_exception_text(module, tmp_path):
    job = {
        "problem": "adbench:x",
        "source": "adbench",
        "name": "x",
        "path": str(tmp_path / "no.npz"),
    }
    result = module.run_job(job)
    assert result["failed"].startswith("FileNotFoundError(")


class _Serial:
    seen: dict = {}

    def __init__(self, max_workers):
        _Serial.seen["workers"] = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, function, items):
        return [function(item) for item in items]


@pytest.mark.parametrize("module", [lb, pf], ids=["labelled_benchmark", "pool_full"])
def test_the_command_defaults_point_at_the_repository_data_and_use_four_workers(
    module, monkeypatch, tmp_path
):
    captured = {}

    def jobs(registry, adbench, pool):
        captured["paths"] = (registry, adbench, pool)
        return []

    _Serial.seen = {}
    monkeypatch.setattr(lb, "jobs", jobs)
    monkeypatch.setattr(module, "ProcessPoolExecutor", _Serial)
    assert module.main(["--output", str(tmp_path / "deep" / "er" / "out")]) == 0
    assert captured["paths"] == (
        ROOT / "verification" / "evidence" / "dataset_registry",
        ROOT / "data" / "adbench",
        ROOT / "data" / "pool",
    )
    assert _Serial.seen["workers"] == 4 and (tmp_path / "deep" / "er" / "out").is_dir()


@pytest.mark.parametrize("module", [lb, pf], ids=["labelled_benchmark", "pool_full"])
def test_the_method_choice_is_restricted_and_the_help_is_the_module_description(
    module, tmp_path, capsys
):
    with pytest.raises(SystemExit) as caught:
        module.main(["--output", str(tmp_path), "--methods", "quantum"])
    assert caught.value.code == 2 and "invalid choice" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        module.main(["--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    assert " ".join(module.__doc__.split())[:60] in help_text
    assert "--only" in help_text and "--resume" in help_text


@pytest.mark.parametrize(("module", "indent"), [(lb, 1), (pf, None)], ids=["lb", "pf"])
def test_result_files_use_sorted_keys_and_the_documented_layout(
    module, indent, monkeypatch, tmp_path
):
    job = {"problem": "uci:1", "source": "uci", "meta": {}, "path": "x"}
    result = {"problem": "uci:1", "b": 1, "a": {"z": 1, "y": 2}}
    monkeypatch.setattr(lb, "jobs", lambda *a: [job])
    monkeypatch.setattr(module, "run_job", lambda job, methods=None: dict(result))
    monkeypatch.setattr(module, "ProcessPoolExecutor", _Serial)
    module.main(["--output", str(tmp_path)])
    text = (tmp_path / "uci_1.json").read_text()
    assert text == json.dumps(result, indent=indent, sort_keys=True) + "\n"
    assert list(json.loads(text)) == ["a", "b", "problem"]
