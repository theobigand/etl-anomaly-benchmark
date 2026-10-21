"""Decision-level evaluation under temporal shift (issue #63), protocol temporal_decision.md."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import temporal_decision as td  # noqa: E402


def test_thresholds_follow_the_three_policies():
    train = np.arange(100.0)
    val = np.arange(100.0) + 50
    test = np.arange(200.0) + 100
    thr = td.thresholds(train, val, test, pi=0.1, blocks=4)
    assert np.allclose(thr["P0"], np.quantile(train, 0.9))
    assert np.allclose(thr["P1"], np.quantile(val, 0.9))
    assert len(thr["P2"]) == len(test)
    assert thr["P2"][0] < thr["P2"][-1]  # the rolling threshold follows the drift


def test_rolling_threshold_uses_only_scores_before_the_block():
    test = np.concatenate([np.zeros(100), np.full(100, 1000.0)])
    thr = td.thresholds(np.zeros(50), np.zeros(50), test, pi=0.1, blocks=2)
    assert thr["P2"][100:].max() <= 0.0  # the second block never sees its own scores


def test_decision_metrics_count_false_alarms_and_flagged_share():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    scores = np.array([9.0, 1.0, 8.0, 0, 0, 0, 0, 0, 0, 0])
    m = td.decision_metrics(y, scores, thr=np.full(10, 0.5))
    assert m["recall"] == 1.0 and m["precision"] == pytest.approx(2 / 3)
    assert m["fpr"] == pytest.approx(1 / 8)
    assert m["flagged_share"] == pytest.approx(0.3)


def test_match_prevalence_reaches_the_target_by_dropping_the_majority_side():
    rng = np.random.default_rng(0)
    y = np.array([1] * 100 + [0] * 900)
    kept = td.match_prevalence(y, 0.02, rng)
    assert abs(y[kept].mean() - 0.02) < 0.005
    kept2 = td.match_prevalence(y, 0.5, rng)
    assert abs(y[kept2].mean() - 0.5) < 0.01


def _stream(n=6000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    late = np.arange(n) > 0.8 * n
    y[rng.random(n) < np.where(late, 0.02, 0.06)] = 1
    x[y == 1] += 4
    x[late] += 0.6  # a shift of the normal rows after the training period
    times = pd.Series(pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"))
    return pd.DataFrame(x, columns=list("abcd")), y, times


def test_run_frame_reports_both_arms_and_the_three_policies():
    x, y, times = _stream()
    out = td.run_frame(x, y, times, methods=["zscore", "isolation_forest"], seeds=(1, 2))
    assert set(out["chronological"]) == {"zscore", "isolation_forest"}
    row = out["chronological"]["isolation_forest"]
    assert set(row["policies"]) == {"P0", "P1", "P2"}
    assert row["pr_ci"]["ci_low"] <= row["pr_auc"] <= row["pr_ci"]["ci_high"]
    strat = out["stratified"]["isolation_forest"]
    assert {"pr_auc", "pr_auc_matched", "roc_auc"} <= set(strat)
    assert out["partitions"]["test"]["prevalence"] < out["partitions"]["train"]["prevalence"]


def test_the_run_is_deterministic():
    x, y, times = _stream(3000)
    a = td.run_frame(x, y, times, methods=["zscore"], seeds=(1,))
    b = td.run_frame(x, y, times, methods=["zscore"], seeds=(1,))
    assert a == b


def _result(error, f1_p2, f1_p0, gap_matched, gap_strat, order):
    methods = ["m1", "m2", "m3", "m4"]
    strat = {m: 0.5 - 0.1 * i for i, m in enumerate(methods)}
    chrono = {m: 0.5 - 0.1 * order[i] - gap_strat for i, m in enumerate(methods)}
    return {
        "chronological": {
            m: {
                "pr_auc": chrono[m],
                "policies": {
                    "P0": {"share_error": error[0], "f1": f1_p0},
                    "P1": {"share_error": error[1], "f1": 0.0},
                    "P2": {"share_error": error[2], "f1": f1_p2},
                },
            }
            for m in methods
        },
        "stratified": {
            m: {"pr_auc": strat[m], "pr_auc_matched": chrono[m] + gap_matched} for m in methods
        },
    }


def test_hypotheses_follow_the_preregistered_rules():
    good = _result((2.0, 1.0, 0.5), 0.4, 0.3, 0.0, 0.2, [0, 1, 2, 3])
    h = td.hypotheses({"a": good, "b": good})
    assert h["H1"]["supported"] and h["H2"]["supported"] and h["H3"]["supported"]
    assert h["H4"]["supported"]
    bad = _result((0.5, 1.0, 2.0), 0.1, 0.3, 0.2, 0.2, [3, 2, 1, 0])
    h = td.hypotheses({"a": bad, "b": bad})
    assert not h["H1"]["supported"] and not h["H2"]["supported"] and not h["H3"]["supported"]
    assert not h["H4"]["supported"]


def test_a_rank_correlation_of_exactly_the_threshold_counts_despite_float_error():
    # with four methods one swapped pair gives rho = 0.8, computed as 0.7999999999999999
    two_swaps = _result((2.0, 1.0, 0.5), 0.4, 0.3, 0.0, 0.2, [1, 0, 3, 2])
    assert td.hypotheses({"a": two_swaps})["H1"]["supported"] is False
    swapped = _result((2.0, 1.0, 0.5), 0.4, 0.3, 0.0, 0.2, [1, 0, 2, 3])
    h = td.hypotheses({"a": swapped})
    assert h["H1"]["spearman"]["a"] == pytest.approx(0.8)
    assert h["H1"]["supported"] is True
