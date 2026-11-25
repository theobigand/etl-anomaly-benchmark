"""Finite-sample behaviour of the registered 5 percent label-free threshold (documentation)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_batch as pb  # noqa: E402


@pytest.mark.parametrize("n", range(12, 61))
def test_on_its_own_validation_scores_the_alerts_follow_the_interpolated_quantile(n):
    scores = np.random.default_rng(n).normal(size=n)
    rate = pb.alert_metrics(scores, scores, np.zeros(n, dtype=bool))["false_alert_rate"]
    alerts = n - 1 - int(np.floor(round(0.95 * (n - 1), 9)))
    assert rate == pytest.approx(alerts / n)


def test_the_achieved_validation_rate_is_one_over_n_for_16_to_21_batches_then_doubles():
    rates = {}
    for n in (16, 17, 18, 19, 20, 21, 22):
        scores = np.random.default_rng(n).normal(size=n)
        rates[n] = pb.alert_metrics(scores, scores, np.zeros(n, dtype=bool))["false_alert_rate"]
    assert [round(rates[n] * n) for n in rates] == [1, 1, 1, 1, 1, 1, 2]
    assert rates[16] == pytest.approx(0.0625) and rates[20] == pytest.approx(0.05)
    assert rates[22] == pytest.approx(2 / 22)  # 9.1 percent against a nominal 5


def test_tied_validation_scores_give_no_alert_at_all():
    scores = np.zeros(20)
    out = pb.alert_metrics(scores, scores, np.zeros(20, dtype=bool))
    assert out["false_alert_rate"] == 0.0  # the comparison is strict: nothing exceeds the maximum


def test_a_new_clean_score_exceeds_the_maximum_with_probability_one_over_n_plus_one():
    rng = np.random.default_rng(0)
    n, trials = 20, 20000
    val = rng.normal(size=(trials, n))
    new = rng.normal(size=trials)
    rate = np.mean(new > val.max(axis=1))
    assert rate == pytest.approx(1 / (n + 1), abs=0.004)
