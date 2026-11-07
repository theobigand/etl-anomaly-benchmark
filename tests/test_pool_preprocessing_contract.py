"""Exact refusals, thresholds and report fields of the frozen-partition preparation."""

import numpy as np
import pandas as pd
import pytest

from research.pool_preprocessing import (
    CATEGORY_CAP,
    MAX_MISSING_SHARE,
    prepare_frozen,
    validate_partitions,
)

FOLDS = {"train": list(range(8)), "validation": [8, 9], "test": [10, 11]}


def _numeric_frame():
    return pd.DataFrame({"x": np.arange(12, dtype=float), "y": np.arange(12, dtype=float) ** 2})


@pytest.mark.parametrize(
    ("partitions", "message"),
    [
        ({"train": [0], "validation": [1]}, "partitions must contain train, validation and test"),
        (
            {"train": [], "validation": [1], "test": [2]},
            "each partition must be a nonempty position list",
        ),
        (
            {"train": (0,), "validation": [1], "test": [2]},
            "each partition must be a nonempty position list",
        ),
        (
            {"train": [0], "validation": [1], "test": [3]},
            "partition positions must be in-range integers",
        ),
        (
            {"train": [0], "validation": [1], "test": [True]},
            "partition positions must be in-range integers",
        ),
        (
            {"train": [0], "validation": [1], "test": [1]},
            "partitions must cover every row exactly once without overlap",
        ),
        (
            {"train": [0, 0], "validation": [1], "test": [2]},
            "partitions must cover every row exactly once without overlap",
        ),
    ],
)
def test_partition_refusals_state_their_exact_reason(partitions, message):
    with pytest.raises(ValueError) as caught:
        validate_partitions(partitions, 3)
    assert str(caught.value) == message


def test_a_valid_assignment_is_accepted_without_change():
    folds = {"train": [2, 0], "validation": [1], "test": [3]}
    assert validate_partitions(folds, 4) is None
    assert folds == {"train": [2, 0], "validation": [1], "test": [3]}


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame(index=range(12)),
        pd.DataFrame(np.ones((12, 2)), columns=["a", "a"]),
        pd.DataFrame(np.ones((12, 2)), columns=[0, 1]),
    ],
)
def test_unusable_columns_are_refused_with_the_exact_reason(frame):
    with pytest.raises(ValueError) as caught:
        prepare_frozen(frame, FOLDS)
    assert str(caught.value) == "feature columns must be nonempty, unique strings"


def test_a_single_defect_is_enough_to_refuse_the_columns():
    one_empty_name_free = pd.DataFrame(np.ones((12, 1)), columns=[0])
    with pytest.raises(ValueError, match="nonempty, unique strings"):
        prepare_frozen(one_empty_name_free, FOLDS)
    duplicated = pd.DataFrame(np.arange(24.0).reshape(12, 2), columns=["a", "a"])
    with pytest.raises(ValueError, match="nonempty, unique strings"):
        prepare_frozen(duplicated, FOLDS)


def test_duplicate_feature_rows_across_partitions_are_refused_with_the_exact_reason():
    frame = _numeric_frame()
    frame.iloc[10] = frame.iloc[0]
    with pytest.raises(ValueError) as caught:
        prepare_frozen(frame, FOLDS)
    assert str(caught.value) == "duplicate feature rows cross partitions"


def test_a_frame_without_a_usable_training_feature_is_refused_with_the_exact_reason():
    frame = pd.DataFrame({"constant": [1.0] * 8 + [2.0, 3.0, 4.0, 5.0]})
    with pytest.raises(ValueError) as caught:
        prepare_frozen(frame, FOLDS)
    assert str(caught.value) == "no usable training feature remains"


def test_infinite_and_overflowing_values_are_refused_with_the_exact_reason():
    infinite = _numeric_frame()
    infinite.loc[3, "x"] = np.inf
    with pytest.raises(ValueError) as caught:
        prepare_frozen(infinite, FOLDS)
    assert str(caught.value) == "numeric feature values must be finite or missing"
    huge = _numeric_frame()
    huge["x"] *= 1e-100
    huge.loc[10, "x"] = 1e308
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError) as caught:
        prepare_frozen(huge, FOLDS)
    assert str(caught.value) == "transformed features must be finite"


def test_the_missing_share_and_category_cap_boundaries_keep_the_boundary_value():
    rows = 40
    folds = {
        "train": list(range(30)),
        "validation": list(range(30, 35)),
        "test": list(range(35, 40)),
    }
    base = pd.DataFrame({"x": np.arange(rows, dtype=float)})
    values = np.arange(rows, dtype=float)
    half = base.assign(half=np.where(np.arange(rows) % 2 == 0, np.nan, values))
    assert half.loc[folds["train"], "half"].isna().mean() == MAX_MISSING_SHARE
    kept = prepare_frozen(half, folds)["fit"]
    assert kept["numeric_columns"] == ["x", "half"] and kept["dropped"]["missing"] == []

    more = base.assign(half=np.where(np.arange(rows) % 4 != 3, np.nan, values))
    assert more.loc[folds["train"], "half"].isna().mean() > MAX_MISSING_SHARE
    assert prepare_frozen(more, folds)["fit"]["dropped"]["missing"] == ["half"]

    exact = base.assign(label=[f"c{i % CATEGORY_CAP}" for i in range(rows)])
    fit = prepare_frozen(exact, folds)["fit"]
    assert fit["categorical_columns"] == ["label"] and fit["dropped"]["cardinality"] == []
    over = base.assign(label=[f"c{i % (CATEGORY_CAP + 1)}" for i in range(rows)])
    fit = prepare_frozen(over, folds)["fit"]
    assert fit["dropped"]["cardinality"] == ["label"] and fit["categorical_columns"] == []


def test_the_fit_report_and_frames_carry_every_documented_field():
    frame = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
            "kind": ["a", "b"] * 6,
        }
    )
    folds = {"train": [0, 1, 2, 3, 4, 5, 6, 7], "validation": [8, 9], "test": [10, 11]}
    prepared = prepare_frozen(frame, folds)
    fit = prepared["fit"]
    assert set(fit) == {
        "input_columns",
        "numeric_columns",
        "categorical_columns",
        "dropped",
        "medians",
        "categories",
        "mean",
        "scale",
        "output_columns",
        "category_cap",
        "max_missing_share",
        "unknown_categories",
    }
    assert fit["input_columns"] == ["x", "kind"] and fit["output_columns"] == ["f0", "f1", "f2"]
    assert fit["medians"] == [4.5] and fit["categories"] == [["a", "b"]]
    assert fit["mean"] == pytest.approx([4.5, 0.5, 0.5]) and len(fit["scale"]) == 3
    assert fit["category_cap"] == CATEGORY_CAP and fit["max_missing_share"] == MAX_MISSING_SHARE
    assert fit["unknown_categories"] == "zero one-hot block before scaling"
    for name, positions in folds.items():
        assert list(prepared[name].columns) == ["f0", "f1", "f2"]
        assert list(prepared[name].index) == positions


def test_a_categorical_only_frame_has_no_numeric_block_and_no_medians():
    frame = pd.DataFrame({"kind": [f"c{i}" for i in range(12)]})
    folds = {"train": list(range(8)), "validation": [8, 9], "test": [10, 11]}
    prepared = prepare_frozen(frame, folds)
    assert prepared["fit"]["medians"] == [] and prepared["fit"]["numeric_columns"] == []
    assert prepared["train"].shape == (8, 8) and prepared["test"].shape == (2, 8)
