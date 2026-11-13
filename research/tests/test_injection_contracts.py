"""The typed injection follows its written magnitudes, rows and labels."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402

COLUMNS = ["a", "b", "c", "d"]
SEED = 3


def _carrier(n=4000):
    rng = np.random.default_rng(11)
    a = rng.normal(50, 10, n)
    return pd.DataFrame(
        {
            "a": a,
            "b": 0.8 * a + rng.normal(0, 4, n),
            "c": rng.gamma(4, 5, n),
            "d": rng.normal(size=n),
        }
    )


def _injected(severity=1.0, n=4000):
    carrier = _carrier(n)
    out = inj.inject(carrier, seed=SEED, severity=severity)
    # the injected rows keep the identity of the shuffled carrier row they were made from
    pre = carrier.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    return carrier, out, pre


@pytest.mark.parametrize("severity", [1.0, 2.0])
def test_every_type_has_its_share_of_rows_and_the_clean_rest(severity):
    carrier, out, _ = _injected(severity)
    k = max(round(inj.RATE * len(carrier)), 15)
    counts = out["anomaly_type"].value_counts().to_dict()
    assert {t: counts[t] for t in inj.ANOMALY_TYPES} == {t: k for t in inj.ANOMALY_TYPES}
    assert counts["clean"] == len(carrier) - 5 * k
    assert len(out) == len(carrier) + k
    assert out["anomaly"].tolist() == (out["anomaly_type"] != "clean").tolist()


@pytest.mark.parametrize("severity", [1.0, 2.0])
def test_a_univariate_outlier_sits_between_six_and_twelve_deviations_times_the_severity(severity):
    carrier, out, pre = _injected(severity)
    mean, std = carrier.mean(), carrier.std()
    rows = out[out["anomaly_type"] == "univariate_outlier"]
    deviations = []
    for _, row in rows.iterrows():
        z = ((row[COLUMNS] - mean) / std).abs()
        far = z[z > 5]
        assert len(far) == 1, "exactly one column is moved far from the mean"
        untouched = [c for c in COLUMNS if c != far.index[0]]
        assert np.allclose(
            row[untouched].astype(float), pre.loc[row["group_id"], untouched].astype(float)
        )
        deviations.append(float(far.iloc[0]))
    low, high = 6 * severity, 12 * severity
    assert min(deviations) >= low - 1e-9 and max(deviations) <= high + 1e-9
    assert min(deviations) < low + 0.4 * severity and max(deviations) > high - 0.4 * severity
    signs = {
        np.sign(row[c] - mean[c])
        for _, row in rows.iterrows()
        for c in COLUMNS
        if abs(row[c] - mean[c]) > 5 * std[c]
    }
    assert signs == {-1.0, 1.0}


@pytest.mark.parametrize("severity", [1.0, 2.0])
def test_a_multivariate_outlier_takes_the_opposite_tail_quantiles_of_the_most_correlated_pair(
    severity,
):
    carrier, out, _ = _injected(severity)
    a, b, corr = inj._pair(carrier)
    q_hi, q_lo = min(1.0 - 0.03 / severity, 0.999), max(0.03 / severity, 0.001)
    hi = {c: float(carrier[c].quantile(q_hi)) for c in (a, b)}
    lo = {c: float(carrier[c].quantile(q_lo)) for c in (a, b)}
    rows = out[out["anomaly_type"] == "multivariate_outlier"].reset_index(drop=True)
    seen = {(round(float(r[a]), 9), round(float(r[b]), 9)) for _, r in rows.iterrows()}
    positive = corr > 0
    up_first = {(round(hi[a], 9), round(lo[b], 9))}
    down_first = {(round(lo[a], 9), round(hi[b], 9))}
    assert seen == (up_first | down_first)
    assert corr > 0 and positive
    assert abs(corr) > 0.5


@pytest.mark.parametrize("severity", [1.0, 2.0])
def test_a_drift_row_is_the_latest_in_time_and_three_columns_move_by_one_and_a_half_deviations(
    severity,
):
    carrier, out, pre = _injected(severity)
    std = carrier.std()
    n = len(carrier)
    rows = out[out["anomaly_type"] == "temporal_drift"]
    base = inj._BASE
    assert (rows["t"] >= base + pd.Timedelta(hours=0.9 * n)).all() and (
        rows["t"] <= base + pd.Timedelta(hours=n)
    ).all()
    shifts = {c: [] for c in COLUMNS}
    for _, row in rows.iterrows():
        for c in COLUMNS:
            shifts[c].append(float(row[c] - pre.loc[row["group_id"], c]))
    moved = [c for c in COLUMNS if np.abs(shifts[c]).max() > 1e-9]
    assert len(moved) == 3
    for c in moved:
        assert np.allclose(shifts[c], 1.5 * severity * std[c])
    unmoved = next(c for c in COLUMNS if c not in moved)
    assert np.allclose(shifts[unmoved], 0.0)


def test_a_missing_row_has_one_or_two_empty_cells_and_every_other_cell_is_the_carrier_value():
    _, out, pre = _injected()
    rows = out[out["anomaly_type"] == "missing_value"]
    counts = rows[COLUMNS].isna().sum(axis=1)
    assert set(counts) == {1, 2}
    for _, row in rows.iterrows():
        present = [c for c in COLUMNS if not np.isnan(row[c])]
        assert np.allclose(
            row[present].astype(float), pre.loc[row["group_id"], present].astype(float)
        )
    assert not out[out["anomaly_type"] != "missing_value"][COLUMNS].isna().any().any()


def test_an_invalid_row_has_one_cell_flipped_set_to_the_sentinel_or_scaled():
    carrier, out, pre = _injected()
    rows = out[out["anomaly_type"] == "invalid_format"]
    kinds = set()
    for _, row in rows.iterrows():
        before = pre.loc[row["group_id"], COLUMNS].astype(float)
        changed = [c for c in COLUMNS if not np.isclose(row[c], before[c])]
        assert len(changed) == 1
        value, original = float(row[changed[0]]), float(before[changed[0]])
        if np.isclose(value, -999.0):
            kinds.add("sentinel")
        elif np.isclose(value, -abs(original) - 1e-9):
            kinds.add("sign")
        else:
            assert np.isclose(value, original * 1000.0)
            kinds.add("scale")
    assert kinds == {"sign", "sentinel", "scale"}
    non_negative = {c for c in COLUMNS if carrier[c].min() >= 0}
    flipped = {c for _, r in rows.iterrows() for c in COLUMNS if np.isclose(r[c], -999.0)}
    assert flipped and flipped <= non_negative


def test_a_carrier_without_a_non_negative_column_only_gets_scale_errors():
    carrier = _carrier(1000)
    negative = carrier.assign(**{c: -carrier[c] - 1000.0 for c in COLUMNS})
    out = inj.inject(negative, seed=SEED)
    pre = negative.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    rows = out[out["anomaly_type"] == "invalid_format"]
    for _, row in rows.iterrows():
        before = pre.loc[row["group_id"], COLUMNS].astype(float)
        changed = [c for c in COLUMNS if not np.isclose(row[c], before[c])]
        assert len(changed) == 1 and np.isclose(row[changed[0]], before[changed[0]] * 1000.0)


def test_duplicates_are_exact_copies_of_clean_rows_in_the_same_group():
    _, out, _ = _injected()
    clean = out[out["anomaly_type"] == "clean"].set_index("group_id")
    for _, row in out[out["anomaly_type"] == "duplicate"].iterrows():
        original = clean.loc[row["group_id"]]
        assert np.allclose(row[COLUMNS].astype(float), original[COLUMNS].astype(float))
        assert row["t"] == original["t"]


def test_the_same_seed_gives_the_same_table_and_another_seed_a_different_one():
    carrier = _carrier(1000)
    first = inj.inject(carrier, seed=1)
    assert first.equals(inj.inject(carrier, seed=1))
    assert not first.equals(inj.inject(carrier, seed=2))
