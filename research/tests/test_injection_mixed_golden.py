"""Characterisation of the mixed-schema injection: exact output on fixed small tables.

The snapshots in tests/golden/injection_mixed were generated once; their invariants (group sizes,
changed cells per type, untouched clean rows, train-only magnitudes) are asserted separately in
test_injection_mixed.py and below. Regenerate only after reviewing a deliberate change.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection_mixed as im  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "injection_mixed"


def table(kind: str, n: int = 260) -> tuple[pd.DataFrame, dict[str, str]]:
    rng = np.random.default_rng(7)
    num = {
        "a": rng.normal(10, 2, n).round(3),
        "b": (rng.normal(500, 30, n)).round(3),
        "c": np.abs(rng.normal(5, 1, n)).round(3),
    }
    cat = {
        "p": rng.choice(["x", "y", "z", "w"], n),
        "q": rng.choice(["m1", "m2", "m3"], n),
    }
    columns = {"mixed": {**num, **cat}, "num": num, "cat": {**cat, "r": rng.choice(["u", "v"], n)}}
    frame = pd.DataFrame(columns[kind])
    return frame, im.column_kinds(frame)


def render(frame: pd.DataFrame) -> str:
    shown = frame.assign(t=frame["t"].dt.strftime("%Y-%m-%d %H:%M:%S.%f"))
    return shown.round(6).to_csv(index=True)


@pytest.mark.parametrize("kind", ["mixed", "num", "cat"])
def test_injected_table_equals_the_snapshot(kind):
    clean, kinds = table(kind)
    out = im.inject_mixed(clean, kinds, seed=3)
    assert render(out) == (GOLDEN / f"{kind}.csv").read_text()


def test_severity_and_reference_change_magnitudes_and_the_snapshot_records_it():
    clean, kinds = table("mixed")
    ref = clean.iloc[:100].reset_index(drop=True)
    out = im.inject_mixed(clean, kinds, seed=3, severity=2.0, reference=ref)
    assert render(out) == (GOLDEN / "mixed_severity2_reference.csv").read_text()
    out = im.inject_mixed(clean, kinds, seed=3, severity=100.0)
    assert render(out) == (GOLDEN / "mixed_severity100.csv").read_text()


def test_group_sizes_and_types_per_schema():
    expected = {
        "mixed": {
            "missing_value", "univariate_outlier", "multivariate_outlier", "distribution_shift",
            "invalid_format", "invalid_code", "cross_column_swap", "duplicate",
        },
        "num": {
            "missing_value", "univariate_outlier", "multivariate_outlier", "distribution_shift",
            "invalid_format", "cross_column_swap", "duplicate",
        },
        "cat": {"missing_value", "distribution_shift", "invalid_code", "cross_column_swap",
                "duplicate"},
    }  # fmt: skip
    for kind, types in expected.items():
        clean, kinds = table(kind)
        out = im.inject_mixed(clean, kinds, seed=1)
        counts = out["anomaly_type"].value_counts()
        assert set(counts.index) == types | {"clean"}
        assert all(counts[t] == im.TIER_B_K for t in types)
        assert len(out) == len(clean) + im.TIER_B_K
        assert counts["clean"] == len(clean) - im.TIER_B_K * (len(types) - 1)


def test_the_swapped_columns_exchange_values_and_stay_in_the_other_domain():
    clean, kinds = table("mixed")
    out = im.inject_mixed(clean, kinds, seed=1)
    swapped = out[out["anomaly_type"] == "cross_column_swap"]
    a, b, _ = im.swap_pairs(clean, kinds)[0]
    original = clean.drop_duplicates()
    assert len(swapped) == im.TIER_B_K
    assert (swapped[a].isin(set(clean[b]))).all() and (swapped[b].isin(set(clean[a]))).all()
    assert not original.empty


def test_missing_cells_are_one_or_two_per_row_and_duplicates_copy_clean_rows():
    clean, kinds = table("mixed")
    out = im.inject_mixed(clean, kinds, seed=2)
    cols = list(clean.columns)
    missing = out[out["anomaly_type"] == "missing_value"][cols].isna().sum(axis=1)
    assert missing.between(1, 2).all() and set(missing) == {1, 2}
    dup = out[out["anomaly_type"] == "duplicate"]
    clean_rows = out[out["anomaly_type"] == "clean"]
    merged = dup[cols].merge(clean_rows[cols], how="left", indicator=True)
    assert (merged["_merge"] == "both").all()
    assert (dup["group_id"].isin(clean_rows["group_id"])).all()


def test_the_distribution_shift_rows_are_the_most_recent_and_shift_three_columns():
    clean, kinds = table("mixed")
    out = im.inject_mixed(clean, kinds, seed=2)
    shifted = out[out["anomaly_type"] == "distribution_shift"]
    normal = out[out["anomaly_type"] == "clean"]
    horizon = pd.Timestamp("2020-01-01") + pd.to_timedelta(0.9 * len(clean), unit="h")
    assert (shifted["t"] >= horizon).all()
    assert shifted["t"].min() > normal["t"].quantile(0.5)
    assert (shifted[["a", "b", "c"]].mean() > clean[["a", "b", "c"]].mean()).sum() >= 2


def test_invalid_format_values_are_a_sign_flip_sentinel_or_scale_error():
    clean, kinds = table("num")
    out = im.inject_mixed(clean, kinds, seed=5)
    bad = out[out["anomaly_type"] == "invalid_format"]
    originals = clean.round(9)
    for _, row in bad.iterrows():
        diffs = [c for c in "abc" if not (originals[c] == row[c]).any()]
        assert diffs
        value = row[diffs[0]]
        assert value < 0 or value == -999.0 or abs(value) > 100
