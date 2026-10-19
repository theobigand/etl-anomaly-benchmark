"""Paired block bootstrap of an average-precision difference."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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
