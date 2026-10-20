"""One normalisation policy for every pooled dataset."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalise as nm  # noqa: E402


def _frame(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n), "c": rng.normal(size=n)})


def test_constant_and_mostly_missing_columns_are_dropped_and_reported():
    df = _frame()
    df["const"] = 1.0
    df["holes"] = np.where(np.arange(len(df)) % 10 < 8, np.nan, 1.0)
    y = np.arange(len(df)) % 10 == 0
    x, y2, report = nm.clean(df, y)
    assert x.shape[1] == 3
    assert report["dropped_constant"] == ["const"] and report["dropped_missing"] == ["holes"]


def test_categorical_columns_are_one_hot_up_to_the_cap_and_dropped_beyond_it():
    df = _frame()
    df["few"] = ["u", "v", "w", "u"] * 50
    df["many"] = [f"id{i}" for i in range(len(df))]
    y = np.arange(len(df)) % 10 == 0
    x, _, report = nm.clean(df, y, category_cap=5)
    assert x.shape[1] == 3 + 3
    assert report["encoded"] == ["few"] and report["dropped_high_cardinality"] == ["many"]


def test_duplicates_are_removed_and_conflicting_labels_are_dropped_with_counts():
    df = pd.DataFrame({"a": [1, 1, 2, 2, 3, 4, 5, 6.0], "b": [0, 0, 0, 0, 1, 1, 1, 1.0]})
    y = np.array([0, 0, 0, 1, 0, 1, 0, 1])
    x, y2, report = nm.clean(df, y)
    assert report["duplicates_removed"] == 1 and report["conflicting_rows_removed"] == 2
    assert len(x) == len(y2) == 5


def test_split_is_stratified_70_15_15_and_reproducible_per_seed():
    rng = np.random.default_rng(1)
    x, y = rng.normal(size=(1000, 4)), np.arange(1000) % 20 == 0
    a, b = nm.split(x, y, seed=3), nm.split(x, y, seed=3)
    assert all(np.array_equal(a[k], b[k]) for k in a)
    assert [len(a[k]) for k in ("y_train", "y_val", "y_test")] == [700, 150, 150]
    assert a["y_train"].sum() == 35 and a["y_val"].sum() + a["y_test"].sum() == 15
    assert not np.array_equal(a["y_train"], nm.split(x, y, seed=4)["y_train"])


def test_imputation_and_scaling_are_fitted_on_the_training_rows_only():
    rng = np.random.default_rng(2)
    x = np.vstack([rng.normal(0, 1, (70, 2)), rng.normal(50, 1, (30, 2))])
    x[::7, 0] = np.nan
    y = np.arange(100) % 10 == 0
    s = nm.split(x, y, seed=0)
    raw = x[s["idx_train"]]
    median = np.nanmedian(raw, axis=0)
    filled = np.where(np.isnan(raw), median, raw)
    np.testing.assert_allclose(s["mean"], filled.mean(axis=0))
    np.testing.assert_allclose(s["scale"], filled.std(axis=0))
    assert not np.isnan(s["x_test"]).any()
    assert np.abs(s["x_test"].mean(axis=0)).max() > 0.05  # test is not re-centred on itself


def test_too_few_anomalies_are_refused_instead_of_split():
    x, y = np.random.default_rng(0).normal(size=(100, 3)), np.arange(100) < 2
    with pytest.raises(nm.NormaliseError, match="anomalies"):
        nm.split(x, y, seed=0)


def test_slow_detectors_are_skipped_beyond_the_declared_training_size():
    assert nm.skipped_detectors(10_000) == []
    assert nm.skipped_detectors(30_000) == ["ocsvm"]
    assert nm.skipped_detectors(80_000) == ["lof", "ocsvm"]
