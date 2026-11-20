"""Chronological study with controlled injection: real order, fit on the past, no invented time."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrono_injected as ci  # noqa: E402
import injection as inj  # noqa: E402


def test_timestamps_are_read_with_the_declared_format_and_unreadable_ones_become_missing():
    frame = pd.DataFrame({"d": ["1/12/2017", "2/12/2017", "bad"], "h": [0, 5, 1]})
    stamps, used = ci.parse_time(frame, {"date": "d", "hour": "h", "format": "%d/%m/%Y"})
    assert stamps.iloc[1] == pd.Timestamp("2017-12-02 05:00") and used == ["d", "h"]
    assert stamps.isna().sum() == 1


def test_counter_columns_that_follow_the_time_order_are_found():
    stamps = pd.Series(pd.date_range("2020-01-01", periods=200, freq="h"))
    frame = pd.DataFrame({"index": np.arange(200), "x": np.random.default_rng(0).normal(size=200)})
    assert ci.trend_columns(frame, stamps) == ["index"]


def test_the_chronological_arm_fits_on_the_past_and_the_random_arm_does_not():
    table = pd.DataFrame({"a": np.arange(100.0)})
    fit, test = ci.split_arm(table, "chronological", seed=1)
    assert fit["a"].max() < test["a"].min() and len(fit) == 60
    fit_r, test_r = ci.split_arm(table, "random", seed=1)
    assert fit_r["a"].max() > test_r["a"].min() and len(fit_r) == 60
    assert sorted([*fit_r["a"], *test_r["a"]]) == list(table["a"])


def test_injection_into_the_future_reads_its_magnitudes_from_the_past():
    rng = np.random.default_rng(0)
    past = pd.DataFrame(rng.normal(0, 1, (2000, 4)), columns=list("abcd"))
    future = pd.DataFrame(rng.normal(50, 1, (2000, 4)), columns=list("abcd"))  # drifted
    frame = inj.inject(future, seed=0, reference=past)
    outliers = frame[frame["anomaly_type"] == "univariate_outlier"][list("abcd")]
    # one column per row sits 6 to 12 past-sd from the past mean; the drifted future is at 50
    assert len(outliers) > 0
    assert ((outliers.abs() > 5) & (outliers.abs() < 13)).any(axis=1).all()


def test_unreadable_time_columns_make_a_table_ineligible(tmp_path):
    path = tmp_path / "t.csv"
    pd.DataFrame({"d": ["x"] * 5, "v": range(5)}).to_csv(path, index=False)
    ci.TIME_SPECS[999] = {"date": "d", "format": "%Y"}
    try:
        with pytest.raises(inj.NotEligible, match="timestamps"):
            ci.load_series(999, {"name": "t"}, path)
    finally:
        del ci.TIME_SPECS[999]
