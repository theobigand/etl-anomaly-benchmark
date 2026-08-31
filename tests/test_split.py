import numpy as np
import pandas as pd
import pytest

from etl_benchmark.split import stratified_split


def _frame(n: int = 2000, pos_rate: float = 0.05, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < pos_rate).astype(int)
    return pd.DataFrame({"x": rng.normal(size=n), "y": rng.normal(size=n), "label": y})


def test_split_sizes_match_ratios():
    df = _frame(2000)
    train, val, test = stratified_split(df, "label", ratios=(0.7, 0.15, 0.15), seed=1)

    assert len(train) + len(val) + len(test) == len(df)
    assert abs(len(train) / len(df) - 0.70) < 0.02
    assert abs(len(val) / len(df) - 0.15) < 0.02
    assert abs(len(test) / len(df) - 0.15) < 0.02


def test_split_preserves_class_balance():
    df = _frame(4000, pos_rate=0.05)
    overall = df["label"].mean()
    for part in stratified_split(df, "label", seed=1):
        assert abs(part["label"].mean() - overall) < 0.02


def test_split_is_a_partition():
    df = _frame(1500)
    train, val, test = stratified_split(df, "label", seed=1)
    combined = pd.concat([train, val, test]).sort_values(["x", "y"]).reset_index(drop=True)
    original = df.sort_values(["x", "y"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(combined, original)


def test_split_is_reproducible():
    df = _frame(1500)
    a = stratified_split(df, "label", seed=7)
    b = stratified_split(df, "label", seed=7)
    for pa, pb in zip(a, b, strict=True):
        pd.testing.assert_frame_equal(pa, pb)


def test_split_changes_with_seed():
    df = _frame(1500)
    a_train = stratified_split(df, "label", seed=7)[0]
    b_train = stratified_split(df, "label", seed=8)[0]
    assert not a_train.equals(b_train)


def test_split_accepts_a_series_to_stratify_on():
    df = _frame(2000).drop(columns="label")
    strat = pd.Series(np.r_[np.zeros(1900), np.ones(100)].astype(int), index=df.index)
    parts = stratified_split(df, strat, seed=1)
    assert sum(len(p) for p in parts) == len(df)


def test_split_rejects_bad_ratios():
    df = _frame(500)
    with pytest.raises(ValueError):
        stratified_split(df, "label", ratios=(0.5, 0.3, 0.3))
