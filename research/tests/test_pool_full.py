"""One-pass pool run: thresholds read from the fit scores equal a refit (pool_extension.md)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_full as pf  # noqa: E402

from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES, DETECTOR_NAMES  # noqa: E402


def _problem(n=400, anomalies=40, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    x[:anomalies] += 5
    return x, y


def _frames(seed=3):
    x, y = _problem()
    cut = 280
    names = [f"f{i}" for i in range(4)]
    return pd.DataFrame(x[:cut], columns=names), pd.DataFrame(x[cut:], columns=names), y[cut:]


@pytest.mark.parametrize("method", [*DETECTOR_NAMES, *DEEP_NAMES])
def test_the_threshold_read_from_the_fit_scores_equals_a_refit_with_that_contamination(method):
    train, test, _ = _frames()
    first = pf.build(method, 0.10, seed=5)
    got = detect(test, first, fit_df=train)
    kept = pf.fit_scores(first, train)
    again = detect(test, pf.build(method, pf.FIXED, seed=5), fit_df=train)
    if kept is None:  # a rule: the contamination is not read
        np.testing.assert_array_equal(got.flags, again.flags)
    else:
        derived = pf.flags_at(kept, got.scores.to_numpy(), pf.FIXED)
        np.testing.assert_array_equal(derived, again.flags.to_numpy())


def test_a_problem_gives_every_threshold_table_from_one_fit():
    x, y = _problem()
    result = pf.run_problem(x, y, seeds=(42, 1), methods=["zscore", "isolation_forest", "ecod"])
    forest = result["runs"]["isolation_forest"]
    assert [r["seed"] for r in forest] == [42, 1]
    assert {"metrics", "fixed", "sweep", "fit_s", "predict_s", "score_s"} <= set(forest[0])
    assert set(forest[0]["sweep"]) == {str(c) for c in pf.GRID}
    assert "curve" in forest[0] and "curve" not in forest[1]
    assert "sweep" not in result["runs"]["ecod"][0]
    rule = result["runs"]["zscore"][0]
    assert rule["fixed"] == rule["metrics"] and rule["fixed_is_same"]


def test_the_fixed_threshold_flags_about_two_percent_of_the_fit_rows():
    train, test, y = _frames()
    detector = pf.build("hbos", 0.10, seed=1)
    result = detect(test, detector, fit_df=train)
    kept = pf.fit_scores(detector, train)
    share = (kept > np.percentile(kept, 100 * (1 - pf.FIXED))).mean()
    assert share == pytest.approx(pf.FIXED, abs=0.01)
    assert len(pf.flags_at(kept, result.scores.to_numpy(), pf.FIXED)) == len(test)


def test_the_curve_is_downsampled_and_keeps_its_ends():
    y = np.r_[np.ones(300), np.zeros(700)].astype(int)
    scores = np.random.default_rng(0).normal(size=1000) + 2 * y
    curve = pf._curve(y, scores)
    assert len(curve["precision"]) <= pf.CURVE_POINTS
    assert curve["recall"][0] == 1.0 and curve["recall"][-1] == 0.0
    assert 0.5 < curve["average_precision"] <= 1.0


def test_a_failing_detector_is_recorded_and_a_skip_is_listed(monkeypatch):
    x, y = _problem()
    monkeypatch.setattr(pf.nm, "KNN_MAX_TRAIN", 10)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(pf, "run_method", boom)
    result = pf.run_problem(x, y, seeds=(42,), methods=["zscore", "knn"])
    assert result["skipped"] == ["knn"] and result["runs"] == {}
    assert result["errors"]["zscore"][0]["error"] == "RuntimeError('boom')"


def test_unknown_methods_are_refused():
    x, y = _problem()
    with pytest.raises(ValueError, match="unknown"):
        pf.run_problem(x, y, seeds=(1,), methods=["nope"])
