"""Typed anomaly injection on numeric carrier tables."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402

TYPES = inj.ANOMALY_TYPES


def _carrier(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    a = rng.normal(50, 10, n)
    b = 0.8 * a + rng.normal(0, 4, n)  # strongly correlated with a
    c = rng.gamma(4, 5, n)
    d = rng.normal(0, 1, n)
    return pd.DataFrame({"a": a, "b": b, "c": c, "d": d, "flag": rng.integers(0, 2, n)})


def test_only_columns_with_enough_distinct_values_count_as_continuous():
    assert inj.continuous_columns(_carrier()) == ["a", "b", "c", "d"]


def test_a_carrier_needs_four_continuous_columns_and_enough_rows():
    with pytest.raises(inj.NotEligible, match="continuous"):
        inj.prepare(_carrier()[["a", "b", "flag"]], seed=0)
    with pytest.raises(inj.NotEligible, match="rows"):
        inj.prepare(_carrier(500), seed=0)


def test_prepare_caps_rows_drops_incomplete_rows_and_is_reproducible():
    frame = _carrier(5000)
    frame.loc[:99, "a"] = np.nan
    one, report = inj.prepare(frame, seed=0, cap=3000)
    two, _ = inj.prepare(frame, seed=0, cap=3000)
    assert len(one) == 3000 and list(one.columns) == ["a", "b", "c", "d"]
    assert report["rows_incomplete_dropped"] == 100 and one.equals(two)


def test_every_type_gets_the_requested_share_and_duplicates_are_appended():
    clean, _ = inj.prepare(_carrier(), seed=0)
    out = inj.inject(clean, seed=0)
    k = round(0.03 * len(clean))
    counts = out["anomaly_type"].value_counts()
    assert all(counts[t] == k for t in TYPES)
    assert len(out) == len(clean) + k and (out["anomaly"] == (out["anomaly_type"] != "clean")).all()


def test_injection_is_reproducible_and_changes_with_the_seed():
    clean, _ = inj.prepare(_carrier(), seed=0)
    assert inj.inject(clean, seed=1).equals(inj.inject(clean, seed=1))
    assert not inj.inject(clean, seed=1).equals(inj.inject(clean, seed=2))


def test_duplicates_are_exact_copies_sharing_the_group_of_a_clean_row():
    out = inj.inject(inj.prepare(_carrier(), seed=0)[0], seed=0)
    dup = out[out["anomaly_type"] == "duplicate"]
    clean = out[out["anomaly_type"] == "clean"].set_index("group_id")
    for _, row in dup.head(20).iterrows():
        original = clean.loc[row["group_id"]]
        assert (original[inj.FEATURES_OF(out)] == row[inj.FEATURES_OF(out)]).all()


def test_missing_rows_have_one_or_two_empty_cells_and_nothing_else_is_missing():
    out = inj.inject(inj.prepare(_carrier(), seed=0)[0], seed=0)
    cols = inj.FEATURES_OF(out)
    holes = out[cols].isna().sum(axis=1)
    miss = out["anomaly_type"] == "missing_value"
    assert holes[miss].between(1, 2).all() and (holes[~miss] == 0).all()


def test_univariate_outliers_sit_at_least_six_deviations_from_the_clean_mean():
    clean, _ = inj.prepare(_carrier(), seed=0)
    out = inj.inject(clean, seed=0)
    z = ((out[clean.columns] - clean.mean()) / clean.std()).abs()
    rows = out["anomaly_type"] == "univariate_outlier"
    assert (z[rows].max(axis=1) >= 6).all()
    assert (z[out["anomaly_type"] == "clean"].max(axis=1) < 6).all()


def test_multivariate_outliers_keep_each_value_in_range_but_break_the_correlation():
    clean, _ = inj.prepare(_carrier(), seed=0)
    out = inj.inject(clean, seed=0)
    rows = out[out["anomaly_type"] == "multivariate_outlier"]
    assert (rows["a"] >= clean["a"].min()).all() and (rows["a"] <= clean["a"].max()).all()
    assert (rows["b"] >= clean["b"].min()).all() and (rows["b"] <= clean["b"].max()).all()
    # a and b are positively correlated, so the pair sits at opposite quantiles
    assert (
        (rows["a"] > clean["a"].quantile(0.9)) & (rows["b"] < clean["b"].quantile(0.1))
    ).sum() + (
        (rows["a"] < clean["a"].quantile(0.1)) & (rows["b"] > clean["b"].quantile(0.9))
    ).sum() == len(rows)


def test_drift_rows_are_the_most_recent_and_shifted_by_one_and_a_half_deviations():
    clean, _ = inj.prepare(_carrier(), seed=0)
    out = inj.inject(clean, seed=0)
    drift = out[out["anomaly_type"] == "temporal_drift"]
    cutoff = pd.Timestamp("2020-01-01") + pd.Timedelta(hours=0.9 * len(clean))
    assert (drift["t"] >= cutoff).all() and str(out["t"].dtype).startswith("datetime64")
    shifted = [
        c for c in clean.columns if (drift[c].mean() - clean[c].mean()) / clean[c].std() > 1.0
    ]
    assert len(shifted) == 3


def test_invalid_rows_hold_a_sign_flip_a_sentinel_or_a_thousandfold_scale_error():
    clean, _ = inj.prepare(_carrier(), seed=0)
    out = inj.inject(clean, seed=0)
    rows = out[out["anomaly_type"] == "invalid_format"]
    kinds = set()
    for _, row in rows.iterrows():
        z = (row[clean.columns] - clean.mean()).abs() / clean.std()
        col = z.idxmax()
        value = row[col]
        kinds.add("sentinel" if value == -999 else "scale" if z[col] > 30 else "sign")
    assert kinds <= {"sentinel", "scale", "sign"} and len(kinds) >= 2
