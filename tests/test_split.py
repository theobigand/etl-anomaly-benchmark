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


def test_split_aligns_series_by_original_index():
    df = _frame(300, pos_rate=0.25, seed=6)
    df.index = np.arange(1000, 1300)
    ordered = stratified_split(df, df["label"], seed=12)
    shuffled_label = df["label"].sample(frac=1, random_state=99)
    aligned = stratified_split(df, shuffled_label, seed=12)
    for expected, actual in zip(ordered, aligned, strict=True):
        pd.testing.assert_frame_equal(expected, actual)


def test_split_keeps_exact_counts_of_a_rare_class_for_every_seed():
    df = pd.DataFrame({"x": np.arange(1000), "label": [1] * 10 + [0] * 990})
    for seed in range(20):
        train, val, test = stratified_split(df, "label", seed=seed)
        assert train["label"].sum() == 7
        assert val["label"].sum() >= 1
        assert test["label"].sum() >= 1
        assert val["label"].sum() + test["label"].sum() == 3


@pytest.mark.parametrize("ratios", [(0.5, 0.3, 0.3), (0.0, 0.5, 0.5), (0.5, 0.5)])
def test_split_rejects_bad_ratios(ratios):
    with pytest.raises(ValueError, match="^ratios must be three positive fractions summing to 1"):
        stratified_split(_frame(500), "label", ratios=ratios)


@pytest.mark.parametrize("ratios", [(float("nan"), 0.2, 0.8), (float("inf"), 0.1, 0.1)])
def test_split_rejects_nonfinite_ratios(ratios):
    with pytest.raises(ValueError, match="ratios"):
        stratified_split(_frame(500), "label", ratios=ratios)


def test_split_rejects_ambiguous_row_alignment():
    frame = _frame(500)
    duplicated = frame.copy()
    duplicated.index = [0] * len(duplicated)
    with pytest.raises(ValueError, match="^input index must be unique so rows can be aligned$"):
        stratified_split(duplicated, "label")
    labels = frame["label"].iloc[:-1]
    with pytest.raises(
        ValueError, match="^stratification Series index must match the input index$"
    ):
        stratified_split(frame, labels)
    labels = frame["label"].copy()
    labels.index = [0] * len(labels)
    with pytest.raises(
        ValueError, match="^stratification Series index must match the input index$"
    ):
        stratified_split(frame, labels)


def test_a_class_too_rare_to_stratify_is_an_error_not_a_random_fallback():
    df = pd.DataFrame({"x": np.arange(200.0), "label": [1] + [0] * 199})
    with pytest.raises(ValueError, match="least populated class"):
        stratified_split(df, "label", seed=0)


@pytest.mark.parametrize(
    ("ratios", "sizes", "positives"),
    [
        ((0.7, 0.15, 0.15), (700, 150, 150), (70, 15, 15)),
        ((0.6, 0.2, 0.2), (600, 200, 200), (60, 20, 20)),
    ],
)
def test_split_gives_the_hand_computed_sizes_and_class_counts(ratios, sizes, positives):
    # 1000 rows with 10% positives: sizes and positives follow by arithmetic.
    df = pd.DataFrame({"x": range(1000), "label": [1] * 100 + [0] * 900})
    parts = stratified_split(df, "label", ratios, seed=3)
    assert tuple(len(part) for part in parts) == sizes
    assert tuple(int(part["label"].sum()) for part in parts) == positives
