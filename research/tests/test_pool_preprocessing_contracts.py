"""Array shapes and missing-value markers handed to the frozen preprocessing."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_preprocessing as pp  # noqa: E402


def test_no_numeric_columns_give_an_array_with_one_row_per_record_and_no_columns():
    assert pp._numeric(pd.DataFrame({"a": [1, 2, 3]}), []).shape == (3, 0)


def test_integer_columns_become_floating_point_values():
    values = pp._numeric(pd.DataFrame({"a": [1, 2], "b": [3, 4]}), ["a", "b"])
    assert values.dtype == np.float64 and values.tolist() == [[1.0, 3.0], [2.0, 4.0]]


def test_categorical_values_are_objects_and_a_missing_one_is_a_float_nan():
    frame = pd.DataFrame({"c": ["x", None, "y"], "d": ["p", "q", None]})
    values = pp._categorical(frame, ["c", "d"])
    assert values.dtype == object and values.shape == (3, 2)
    assert values[0].tolist() == ["x", "p"]
    assert isinstance(values[1, 0], float) and np.isnan(values[1, 0])
    assert isinstance(values[2, 1], float) and np.isnan(values[2, 1])
