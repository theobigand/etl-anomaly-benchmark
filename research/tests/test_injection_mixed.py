"""Mixed-schema typed injection (issue 77): faults per column kind, train-only statistics."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402
import injection_mixed as im  # noqa: E402


def _table(n=900, seed=0, cats=2, nums=3):
    rng = np.random.default_rng(seed)
    cols = {}
    for i in range(nums):
        cols[f"n{i}"] = rng.normal(100 * (i + 1) ** 2, 5 * (i + 1), n)
    for i in range(cats):
        levels = [f"c{i}_{j}" for j in range(4)] if i == 0 else [f"d{j}" for j in range(3)]
        cols[f"k{i}"] = rng.choice(levels, n)
    return pd.DataFrame(cols)


def test_prepare_drops_unusable_columns_and_reports_them():
    frame = _table()
    frame["const"] = 1.0
    frame["empty"] = np.nan
    frame["mostly_missing"] = np.where(np.arange(len(frame)) % 3 == 0, np.nan, 1.0)
    table, kinds, report = im.prepare_mixed(frame, seed=0)
    assert set(report["columns_dropped"]) == {"const", "empty", "mostly_missing"}
    assert kinds["n0"] == "num" and kinds["k0"] == "cat"
    assert len(table) == len(frame.drop_duplicates())


def test_small_or_narrow_tables_are_not_eligible():
    with pytest.raises(inj.NotEligible, match="rows"):
        im.prepare_mixed(_table(n=150), seed=0)
    assert im.tier(len(im.prepare_mixed(_table(n=300), seed=0)[0])) == "B"
    assert im.group_size(300) == im.TIER_B_K
    with pytest.raises(inj.NotEligible, match="columns"):
        im.prepare_mixed(_table(cats=0, nums=2), seed=0)


def test_supported_types_follow_the_schema():
    num_only = im.supported_types({"a": "num", "b": "num", "c": "num"})
    cat_only = im.supported_types({"a": "cat", "b": "cat", "c": "cat"})
    assert "univariate_outlier" in num_only and "invalid_code" not in num_only
    assert "invalid_code" in cat_only and "univariate_outlier" not in cat_only
    assert {"missing_value", "duplicate", "distribution_shift"} <= set(num_only) & set(cat_only)
    assert "multivariate_outlier" not in im.supported_types({"a": "num", "b": "cat", "c": "cat"})


def test_injection_labels_every_group_and_leaves_clean_rows_untouched():
    clean, kinds, _ = im.prepare_mixed(_table(), seed=0)
    out = im.inject_mixed(clean, kinds, seed=1)
    types = set(out["anomaly_type"]) - {"clean"}
    assert types <= set(im.supported_types(kinds)) and "invalid_code" in types
    assert (out["anomaly"] == (out["anomaly_type"] != "clean")).all()
    cols = list(clean.columns)
    kept = out[out["anomaly_type"] == "clean"][cols].round(9).astype(str).agg("|".join, axis=1)
    pool = clean[cols].round(9).astype(str).agg("|".join, axis=1)
    assert kept.isin(set(pool)).all()


def test_invalid_codes_fall_outside_the_domain_and_numeric_outliers_are_far():
    clean, kinds, _ = im.prepare_mixed(_table(), seed=0)
    out = im.inject_mixed(clean, kinds, seed=2)
    codes = out[out["anomaly_type"] == "invalid_code"]
    changed = [c for c in ("k0", "k1") if codes[c].str.startswith("__INVALID_").any()]
    assert changed and all(
        set(codes[c][codes[c].str.startswith("__INVALID_")]) - set(clean[c]) for c in changed
    )
    uni = out[out["anomaly_type"] == "univariate_outlier"]
    z = (
        (uni[["n0", "n1", "n2"]] - clean[["n0", "n1", "n2"]].mean())
        / clean[["n0", "n1", "n2"]].std()
    ).abs()
    assert (z.max(axis=1) > 5).all()


def test_statistics_come_from_the_reference_not_from_the_whole_table():
    clean, kinds, _ = im.prepare_mixed(_table(), seed=0)
    shifted = clean.copy()
    shifted[["n0", "n1", "n2"]] = shifted[["n0", "n1", "n2"]] + 1000.0
    a = im.inject_mixed(clean, kinds, seed=3, reference=clean)
    b = im.inject_mixed(clean, kinds, seed=3, reference=shifted)
    uni_a = a[a["anomaly_type"] == "univariate_outlier"][["n0", "n1", "n2"]].max().max()
    uni_b = b[b["anomaly_type"] == "univariate_outlier"][["n0", "n1", "n2"]].max().max()
    assert uni_b > uni_a + 500
    assert list(a["group_id"]) == list(b["group_id"]) and list(a["anomaly_type"]) == list(
        b["anomaly_type"]
    )


def test_encoder_is_fitted_on_training_rows_and_unseen_values_become_zero_rows():
    train = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "k": ["a", "b", "a", "b"]})
    enc = im.Encoder.fit(train, {"x": "num", "k": "cat"})
    test = pd.DataFrame({"x": [1.0, np.nan], "k": ["a", "__INVALID_1__"]})
    out = enc.transform(test)
    assert list(out.columns) == ["x", "k=a", "k=b"]
    assert out.loc[0, "k=a"] == 1 and out.loc[1, ["k=a", "k=b"]].sum() == 0
    assert np.isnan(out.loc[1, "x"])


def test_high_cardinality_columns_use_frequency_encoding_with_zero_for_unseen():
    train = pd.DataFrame({"k": [f"v{i % 30}" for i in range(300)], "x": np.arange(300.0)})
    enc = im.Encoder.fit(train, {"k": "cat", "x": "num"})
    out = enc.transform(pd.DataFrame({"k": ["v1", "zzz"], "x": [1.0, 2.0]}))
    assert out.loc[0, "k"] == pytest.approx(1 / 30) and out.loc[1, "k"] == 0.0
