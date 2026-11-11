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
    assert nm.skipped_detectors(50_000) == ["ocsvm"]
    assert nm.skipped_detectors(50_001) == ["lof", "ocsvm", "knn"]
    assert nm.skipped_detectors(80_000) == ["lof", "ocsvm", "knn"]


# --- exact encoding, split and standardisation --------------------------------------------------


def _labelled(n=200, anomalies=20, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3)) * [1.0, 5.0, 0.2] + [0.0, 10.0, -3.0]
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    return x, y


def test_a_boolean_column_is_encoded_as_two_indicators_not_read_as_a_number():
    frame = _frame(n=40)
    frame["flag"] = [True, False] * 20
    x, _, report = nm.clean(frame, np.zeros(40, dtype=int))
    assert report["encoded"] == ["flag"] and report["features_out"] == 3 + 2
    assert x.shape[1] == 5


def test_validation_and_test_each_hold_their_share_of_the_anomalies_for_every_seed():
    x, y = _labelled()
    for seed in range(8):
        part = nm.split(x, y, seed)
        assert (len(part["y_train"]), len(part["y_val"]), len(part["y_test"])) == (140, 30, 30)
        assert (part["y_train"].sum(), part["y_val"].sum(), part["y_test"].sum()) == (14, 3, 3)


def test_every_split_is_standardised_with_the_training_mean_and_spread_and_labels_stay_integers():
    x, y = _labelled()
    x[5, 1] = np.nan  # a training or evaluation row with a missing value
    part = nm.split(x, y, 3)
    train = x[part["idx_train"]]
    median = np.nanmedian(train, axis=0)
    filled = np.where(np.isnan(train), median, train)
    mean, scale = filled.mean(axis=0), filled.std(axis=0)
    assert np.allclose(part["mean"], mean) and np.allclose(part["scale"], scale)
    for name in ("train", "val", "test"):
        rows = x[part[f"idx_{name}"]]
        expected = (np.where(np.isnan(rows), median, rows) - mean) / scale
        assert np.allclose(part[f"x_{name}"], expected)
        assert np.array_equal(part[f"y_{name}"], y[part[f"idx_{name}"]])
        assert part[f"y_{name}"].dtype.kind == "i"
    assert not np.isnan(np.vstack([part["x_train"], part["x_val"], part["x_test"]])).any()


def test_a_column_that_is_constant_in_training_is_left_unscaled_not_divided_by_zero():
    x, y = _labelled()
    part0 = nm.split(x, y, 3)
    x[part0["idx_train"], 2] = 7.0  # constant on the training rows only
    part = nm.split(x, y, 3)
    assert part["scale"][2] == 1.0 and part["mean"][2] == 7.0
    held_out = x[part["idx_val"], 2]
    assert np.allclose(part["x_val"][:, 2], held_out - 7.0)
    assert np.isfinite(part["x_test"]).all()


def test_a_scale_of_exactly_one_is_a_real_scale_not_a_replacement():
    x = np.tile(np.array([[0.0], [2.0]]), (60, 1))  # std exactly 1 around mean 1
    y = np.tile([0, 1], 60)
    part = nm.split(x, y, 0)
    assert part["scale"][0] == pytest.approx(1.0)
    constant = np.full((120, 1), 5.0)
    assert nm.split(constant, y, 0)["scale"][0] == 1.0


def test_known_limitation_three_to_five_anomalies_pass_the_guard_but_fail_the_stratified_split():
    """MIN_CLASS_COUNT = 3 is below what a 70/15/15 stratified split needs (6 anomalies).

    The set is still refused, but by scikit-learn's ``ValueError`` and not by ``NormaliseError``,
    which ``build_pool`` catches to record an exclusion. The module is hashed in archived evidence
    manifests, so the guard is left unchanged and this behaviour is pinned until the owner decides.
    """
    x = np.arange(100.0).reshape(-1, 1)
    for anomalies in range(nm.MIN_CLASS_COUNT, 6):
        y = np.zeros(100, dtype=int)
        y[:anomalies] = 1
        with pytest.raises(ValueError) as refused:
            nm.split(x, y, 0)
        assert not isinstance(refused.value, nm.NormaliseError)
    y = np.zeros(100, dtype=int)
    y[:6] = 1
    part = nm.split(x, y, 0)
    assert (part["y_train"].sum(), part["y_val"].sum(), part["y_test"].sum()) == (4, 1, 1)


def test_fewer_anomalies_than_the_minimum_or_a_scarce_normal_class_is_refused_by_the_guard():
    x = np.arange(60.0).reshape(-1, 1)
    with pytest.raises(nm.NormaliseError, match=r"^too few anomalies to split \(2\)$"):
        nm.split(x, np.r_[np.ones(2, dtype=int), np.zeros(58, dtype=int)], 0)
    mostly_anomalous = np.ones(60, dtype=int)
    mostly_anomalous[:2] = 0  # the scarce class is the normal one
    with pytest.raises(nm.NormaliseError):
        nm.split(x, mostly_anomalous, 0)
