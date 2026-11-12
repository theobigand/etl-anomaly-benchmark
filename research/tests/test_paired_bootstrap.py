"""Paired block bootstrap of an average-precision difference."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paired_bootstrap as pb  # noqa: E402


def _data(n=6000, seed=0):
    rng = np.random.default_rng(seed)
    times = pd.Series(pd.to_datetime(np.sort(rng.integers(0, 80000, n)), unit="s", utc=True))
    y = (rng.random(n) < 0.06).astype(int)
    good = y * 2.0 + rng.normal(size=n)
    poor = y * 0.0 + rng.normal(size=n)
    return y, good, poor, times


def test_a_clearly_better_scorer_has_an_interval_excluding_zero_and_the_reverse_is_negative():
    y, good, poor, times = _data()
    up = pb.paired_block_bootstrap(y, good, poor, times, 1800, 300, 42)
    down = pb.paired_block_bootstrap(y, poor, good, times, 1800, 300, 42)
    assert up["ci_low"] > 0 and up["difference"] > 0
    assert down["ci_high"] < 0 and down["difference"] == pytest.approx(-up["difference"])


def test_identical_scorers_have_a_zero_difference_and_a_degenerate_interval():
    y, good, _poor, times = _data()
    same = pb.paired_block_bootstrap(y, good, good.copy(), times, 1800, 100, 1)
    assert same["difference"] == 0 and same["ci_low"] == same["ci_high"] == 0


def test_the_resamples_are_shared_between_the_two_scorers_and_deterministic():
    y, good, poor, times = _data()
    a = pb.paired_block_bootstrap(y, good, poor, times, 1800, 100, 42)
    b = pb.paired_block_bootstrap(y, good, poor, times, 1800, 100, 42)
    assert a == b
    assert a["resamples_used"] <= 100


def test_inputs_must_be_aligned_and_contain_both_classes():
    y, good, poor, times = _data(200)
    with pytest.raises(ValueError):
        pb.paired_block_bootstrap(y[:-1], good, poor, times, 600, 10, 1)
    with pytest.raises(ValueError):
        pb.paired_block_bootstrap(np.zeros(200, int), good, poor, times, 600, 10, 1)


# --- the interval is pinned against an independent derivation of its definition -----------------


def _reference(y, a, b, times, block_seconds, resamples, seed):
    seconds = (
        (pd.to_datetime(times, utc=True) - pd.Timestamp("1970-01-01", tz="UTC"))
        .dt.total_seconds()
        .to_numpy()
    )
    blocks = np.floor(seconds / block_seconds).astype(int)
    groups = [np.flatnonzero(blocks == k) for k in np.unique(blocks)]
    rng = np.random.default_rng(seed)
    gaps = []
    for _ in range(resamples):
        picked = rng.choice(len(groups), len(groups))
        index = np.concatenate([groups[i] for i in picked])
        if y[index].min() != y[index].max():
            gaps.append(
                average_precision_score(y[index], a[index])
                - average_precision_score(y[index], b[index])
            )
    return gaps


def _small():
    rng = np.random.default_rng(3)
    n = 240
    y = (rng.uniform(size=n) < 0.2).astype(int)
    a = y * 0.8 + rng.normal(size=n)
    b = y * 0.3 + rng.normal(size=n)
    times = pd.Series(pd.date_range("2024-01-01", periods=n, freq="30min"))
    return y, a, b, times


def test_the_result_equals_its_definition_block_by_block():
    y, a, b, times = _small()
    got = pb.paired_block_bootstrap(y, a, b, times, 6 * 3600, 150, 11)
    gaps = _reference(y, a, b, times, 6 * 3600, 150, 11)
    assert got["resamples_used"] == len(gaps)
    assert got["ci_low"] == pytest.approx(np.percentile(gaps, 2.5), abs=1e-12)
    assert got["ci_high"] == pytest.approx(np.percentile(gaps, 97.5), abs=1e-12)
    assert got["ap_a"] == pytest.approx(average_precision_score(y, a))
    assert got["ap_b"] == pytest.approx(average_precision_score(y, b))
    assert got["difference"] == pytest.approx(got["ap_a"] - got["ap_b"])
    assert set(got) == {"ap_a", "ap_b", "difference", "ci_low", "ci_high", "resamples_used"}


def test_naive_timestamps_are_read_as_utc_and_dates_before_1970_fall_in_earlier_blocks():
    y, a, b, _ = _small()
    naive = pd.Series(pd.date_range("1969-12-30", periods=len(y), freq="30min"))
    got = pb.paired_block_bootstrap(y, a, b, naive, 6 * 3600, 120, 5)
    gaps = _reference(y, a, b, naive, 6 * 3600, 120, 5)
    assert got["resamples_used"] == len(gaps)
    assert got["ci_low"] == pytest.approx(np.percentile(gaps, 2.5), abs=1e-12)


def test_the_refusals_state_the_problem_in_full():
    y, a, b, times = _small()
    with pytest.raises(ValueError, match="^labels, scores and times must have equal length$"):
        pb.paired_block_bootstrap(y, a[:-1], b, times, 3600, 10, 1)
    with pytest.raises(ValueError, match="^both classes are required$"):
        pb.paired_block_bootstrap(np.zeros_like(y), a, b, times, 3600, 10, 1)


def test_a_missing_score_is_refused_instead_of_being_ranked_or_dropped():
    y, a, b, times = _small()
    missing = a.astype(object)
    missing[3] = None
    with pytest.raises(ValueError):
        pb.paired_block_bootstrap(y, missing, b, times, 3600, 10, 1)
    with pytest.raises(ValueError):
        pb.paired_block_bootstrap(y, a, missing, times, 3600, 10, 1)


def test_a_missing_timestamp_is_refused_so_that_no_row_silently_leaves_every_block():
    y, a, b, times = _small()
    times = times.copy()
    times[5] = pd.NaT
    with pytest.raises(ValueError, match="non-finite"):
        pb.paired_block_bootstrap(y, a, b, times, 3600, 10, 1)
