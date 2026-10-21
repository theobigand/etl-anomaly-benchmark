"""Labelled-pool benchmark: one problem, every detector, five seeds (protocol labelled_pool.md)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_benchmark as lb  # noqa: E402

METHODS = ["zscore", "iqr", "great_expectations", "isolation_forest", "lof", "ocsvm"]


def _problem(n=600, anomalies=40, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    x[:anomalies] += 6
    return x, y


def test_a_problem_gives_one_metric_row_per_method_and_seed():
    x, y = _problem()
    result = lb.run_problem(x, y, seeds=(42, 1))
    assert sorted(result["metrics"]) == sorted(METHODS)
    for rows in result["metrics"].values():
        assert len(rows) == 2
        assert {"precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"} <= set(rows[0])
    assert result["skipped"] == []


def test_detectors_find_planted_outliers_better_than_chance():
    x, y = _problem()
    result = lb.run_problem(x, y, seeds=(42,))
    assert result["metrics"]["isolation_forest"][0]["roc_auc"] > 0.9
    assert result["metrics"]["zscore"][0]["roc_auc"] > 0.9


def test_quadratic_detectors_are_skipped_above_the_limits_and_the_skip_is_recorded(monkeypatch):
    x, y = _problem()
    monkeypatch.setattr(lb.nm, "LOF_MAX_TRAIN", 100)
    monkeypatch.setattr(lb.nm, "OCSVM_MAX_TRAIN", 100)
    result = lb.run_problem(x, y, seeds=(42,))
    assert result["skipped"] == ["lof", "ocsvm"]
    assert "lof" not in result["metrics"] and "ocsvm" not in result["metrics"]


def test_the_result_is_reproducible_for_a_seed():
    x, y = _problem()
    a = lb.run_problem(x, y, seeds=(3,), methods=["zscore", "isolation_forest"])
    b = lb.run_problem(x, y, seeds=(3,), methods=["zscore", "isolation_forest"])
    assert a == b


def test_unknown_method_is_rejected():
    x, y = _problem()
    with pytest.raises(ValueError, match="unknown"):
        lb.run_problem(x, y, seeds=(1,), methods=["nope"])


def test_adbench_problem_is_read_from_its_npz(tmp_path):
    x, y = _problem()
    np.savez(tmp_path / "9_toy.npz", X=x, y=y)
    features, labels, report = lb.load_adbench("toy", tmp_path / "9_toy.npz")
    assert features.shape[0] == report["rows_out"] and set(labels) == {0, 1}
    assert report["source"] == "adbench"
