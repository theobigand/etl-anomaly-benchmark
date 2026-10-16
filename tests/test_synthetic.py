import numpy as np
import pandas as pd
import pytest
from faker import Faker

from etl_benchmark.synthetic import (
    ANOMALY_TYPES,
    FEATURE_COLUMNS,
    _clean_population,
    make_synthetic,
)


def test_make_synthetic_is_reproducible():
    a = make_synthetic(n_rows=2_000, seed=7)
    b = make_synthetic(n_rows=2_000, seed=7)

    pd.testing.assert_frame_equal(a, b)


def test_requested_population_must_hold_each_injected_group():
    with pytest.raises(ValueError, match="cannot hold six anomaly groups"):
        make_synthetic(n_rows=94, anomaly_rate=1 / 6)


def test_make_synthetic_changes_with_seed():
    a = make_synthetic(n_rows=2_000, seed=7)
    b = make_synthetic(n_rows=2_000, seed=8)

    assert not a.equals(b)


def test_default_severity_is_the_reference_dataset():
    a = make_synthetic(n_rows=2_000, seed=7)
    b = make_synthetic(n_rows=2_000, seed=7, severity=1.0)

    pd.testing.assert_frame_equal(a, b)


def test_higher_severity_pushes_injections_further():
    lo = make_synthetic(n_rows=3_000, seed=1, severity=1.0)
    hi = make_synthetic(n_rows=3_000, seed=1, severity=3.0)

    for t in ("univariate_outlier", "temporal_drift"):
        lo_mag = lo.loc[lo["anomaly_type"] == t, "annual_income"].abs().mean()
        hi_mag = hi.loc[hi["anomaly_type"] == t, "annual_income"].abs().mean()
        assert hi_mag > lo_mag
    # types without a magnitude are unaffected
    lo_miss = lo["anomaly_type"].eq("missing_value").sum()
    hi_miss = hi["anomaly_type"].eq("missing_value").sum()
    assert lo_miss == hi_miss


def test_every_anomaly_type_is_present():
    df = make_synthetic(n_rows=4_000, seed=1)

    present = set(df["anomaly_type"].unique())
    assert present == {"clean", *ANOMALY_TYPES}
    # each injected type is a small minority, none absent
    counts = df.loc[df["anomaly_type"] != "clean", "anomaly_type"].value_counts()
    assert (counts >= 10).all()


def test_anomaly_flag_matches_type():
    df = make_synthetic(n_rows=3_000, seed=2)

    assert (df["anomaly"] == (df["anomaly_type"] != "clean")).all()


def test_clean_rows_dominate():
    df = make_synthetic(n_rows=5_000, seed=3, anomaly_rate=0.03)

    assert df["anomaly"].mean() < 0.25
    assert df["anomaly_type"].eq("clean").mean() > 0.7


def test_feature_columns_exist_and_exclude_ground_truth():
    df = make_synthetic(n_rows=1_500, seed=4)

    for col in FEATURE_COLUMNS:
        assert col in df.columns
    assert "anomaly" not in FEATURE_COLUMNS
    assert "anomaly_type" not in FEATURE_COLUMNS


def test_duplicate_rows_are_exact_copies_on_features():
    df = make_synthetic(n_rows=3_000, seed=5)
    dups = df[df["anomaly_type"] == "duplicate"]

    assert len(dups) > 0
    # every injected duplicate matches some other row on all feature columns
    others = df[df["anomaly_type"] != "duplicate"][FEATURE_COLUMNS].drop_duplicates()
    merged = dups[FEATURE_COLUMNS].merge(others, how="left", indicator=True)
    assert (merged["_merge"] == "both").all()


def test_missing_value_rows_have_nulls_in_features():
    df = make_synthetic(n_rows=3_000, seed=6)
    mv = df[df["anomaly_type"] == "missing_value"]

    assert mv[FEATURE_COLUMNS].isna().any(axis=1).all()


@pytest.mark.parametrize("n", [500, 20_000])
def test_row_count_is_close_to_requested(n):
    df = make_synthetic(n_rows=n, seed=0)
    # clean + 6 injected groups, duplicates append rather than replace
    assert n <= len(df) <= int(n * 1.2)


class _RecordingRng:
    """A real generator whose income draw is forced and whose Poisson rate is recorded."""

    def __init__(self, log_income_mean, seed=0):
        self._inner = np.random.default_rng(seed)
        self._log_income_mean = log_income_mean
        self.rates = None

    def normal(self, loc, scale, size=None):
        if loc == 10.6:
            return np.full(size, self._log_income_mean)
        return self._inner.normal(loc, scale, size)

    def poisson(self, rate):
        self.rates = np.asarray(rate)
        return self._inner.poisson(rate)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_the_transaction_rate_never_exceeds_ninety():
    # Income of about 1.2 million would give a rate of 300 without the cap.
    rng = _RecordingRng(14.0)
    _clean_population(50, rng, Faker("en_US"))
    assert (rng.rates == 90.0).all()


def test_the_transaction_rate_never_falls_below_two():
    # Income at the 6 000 floor gives 1.5 before the lower bound is applied.
    rng = _RecordingRng(5.0)
    _clean_population(200, rng, Faker("en_US"))
    assert rng.rates.min() == 2.0
    assert (rng.rates >= 2.0).all()
