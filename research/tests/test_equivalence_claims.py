"""Differential checks of the proposed LSTM equivalence claims (evidence, not approval).

Each test compares the original expression with the mutated one over a wide set of inputs and
fails if a counterexample appears, so a dependency change that breaks an argument is noticed.
A passing test does not accept an equivalence: that needs an independent reviewer.
"""

from importlib.metadata import version

import numpy as np
import pandas as pd
import pytest
import torch

DTYPE_FRAMES = {
    "int64": pd.DataFrame({"a": [1, 2, 3]}),
    "float32": pd.DataFrame({"a": np.array([1, 2, 3], dtype="float32")}),
    "bool": pd.DataFrame({"a": [True, False, True]}),
    "nullable_int": pd.DataFrame({"a": pd.array([1, None, 3], dtype="Int64")}),
    "object_floats": pd.DataFrame({"a": pd.Series([1.5, 2.5], dtype=object)}),
    "numeric_text": pd.DataFrame({"a": ["1.5", "2"]}),
    "with_nan": pd.DataFrame({"a": [1.0, np.nan]}),
}


@pytest.mark.parametrize("name", sorted(DTYPE_FRAMES))
def test_astype_none_gives_the_same_float64_values_as_astype_float(name):
    frame = DTYPE_FRAMES[name]
    first, second = frame.astype(float), frame.astype(None)
    assert first.dtypes.tolist() == second.dtypes.tolist() == [np.dtype("float64")]
    assert np.array_equal(first.to_numpy(), second.to_numpy(), equal_nan=True)


def test_astype_none_fails_exactly_where_astype_float_fails():
    frame = pd.DataFrame({"a": pd.to_datetime(["2020-01-01"])})
    with pytest.raises(TypeError):
        frame.astype(float)
    with pytest.raises(TypeError):
        frame.astype(None)


def test_a_numpy_array_cast_to_none_is_float64_like_a_cast_to_float():
    array = torch.arange(6, dtype=torch.float32).reshape(2, 3).numpy()
    assert array.astype(None).dtype == array.astype(float).dtype == np.dtype("float64")
    assert np.array_equal(array.astype(None), array.astype(float))


def test_the_last_axis_of_a_two_dimensional_error_tensor_is_dim_one_and_minus_one():
    for features in (1, 2, 5):
        error = torch.rand(7, 4, features)[:, -1]
        assert error.dim() == 2
        assert torch.equal(error.mean(dim=-1), error.mean(dim=+1))


def test_a_none_replace_flag_samples_without_replacement_like_false():
    for seed in range(300):
        for population, size in ((50, 20), (10, 10), (7, 1)):
            plain = np.random.default_rng(seed).choice(population, size, replace=False)
            none = np.random.default_rng(seed).choice(population, size, replace=None)
            assert np.array_equal(plain, none) and len(set(none.tolist())) == size


def test_selecting_every_index_then_sorting_is_the_identity():
    for seed in range(100):
        for count in (1, 2, 17, 60):
            kept = np.sort(np.random.default_rng(seed).choice(count, count, replace=False))
            assert np.array_equal(kept, np.arange(count))


@pytest.mark.parametrize("package", ["torch", "numpy"])
def test_distribution_names_are_looked_up_without_regard_to_case(package):
    assert version(package.upper()) == version(package) == version(package.capitalize())
