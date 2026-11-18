"""Differential checks behind the focused-mutation equivalence candidates (evidence, not approval).

Each test compares the original expression with the mutated one over a set of inputs and fails
when a counterexample appears, so a dependency change that breaks an argument is noticed. A
passing test does not accept an equivalence: that needs the repository owner's recorded decision in
``verification/mutation_equivalence.json``. The candidates are listed in
``docs/thesis-remediation/OWNER_EQUIVALENCE_REVIEW_2026-11-12.md``.
"""

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalise as nm  # noqa: E402
import source_clustered as sc  # noqa: E402


def _ordered_stack(seed):
    rng = np.random.default_rng(seed)
    frames = [pd.Series(rng.random(5), index=list("edcba")) for _ in range(3)]
    return pd.concat(frames, keys=range(3))


@pytest.mark.parametrize("seed", range(5))
def test_groupby_sort_none_groups_exactly_like_sort_false(seed):
    stack = _ordered_stack(seed)
    kept = stack.groupby(level=1, sort=False).mean()
    none = stack.groupby(level=1, sort=None).mean()
    pd.testing.assert_series_equal(kept, none)
    assert list(none.index) == list("edcba")  # appearance order, not sorted


@pytest.mark.parametrize(
    "values",
    [
        pd.Series([True, False, True]),
        pd.Series([1, 2, 3]),
        pd.Series([0.5, 1.5]),
        pd.Series([1, None, 3], dtype="Int64"),
        pd.Series([0.5, None], dtype="Float64"),
        pd.Series(["1", "2"]),
    ],
)
def test_pandas_astype_none_is_astype_float(values):
    pd.testing.assert_series_equal(values.astype(None), values.astype(float))


@pytest.mark.parametrize(
    "labels", [[0, 1, 1], [False, True, True], [0.0, 1.0, 1.0], ["0", "1", "1"]]
)
def test_numpy_astype_none_agrees_with_int_for_binary_labels(labels):
    array = np.asarray(labels)
    assert ((array.astype(None) == 0) == (array.astype(int) == 0)).all()


def test_numpy_astype_none_differs_from_int_for_fractional_labels():
    array = np.asarray([0.0, 0.5])
    assert ((array.astype(None) == 0) != (array.astype(int) == 0)).any()


@pytest.mark.parametrize(
    "values",
    [
        pd.Series([1.0, 2.0]),
        pd.Series([1, 2]),
        pd.Series([1, None], dtype="Int64"),
        pd.Series([1.5, None], dtype="Float64"),
        pd.Series(["a", "2"]),
    ],
)
def test_to_numpy_without_a_dtype_equals_float_after_numeric_coercion(values):
    coerced = pd.to_numeric(values, errors="coerce")
    assert np.array_equal(
        coerced.to_numpy(dtype=None), coerced.to_numpy(dtype=float), equal_nan=True
    )


def test_generator_choice_replaces_by_default():
    for seed in range(5):
        a = np.random.default_rng(seed).choice(7, size=7, replace=True)
        b = np.random.default_rng(seed).choice(7, size=7)
        assert a.tolist() == b.tolist()


def test_csv_and_row_hash_treat_a_missing_index_flag_as_false():
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": [3, 4]})
    left, right = io.StringIO(), io.StringIO()
    frame.to_csv(left, index=None)
    frame.to_csv(right, index=False)
    assert left.getvalue() == right.getvalue()
    assert (
        pd.util.hash_pandas_object(frame, index=None)
        == pd.util.hash_pandas_object(frame, index=False)
    ).all()


@pytest.mark.parametrize("zone", ["UTC", "Europe/Paris", "Asia/Tokyo"])
def test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag(zone):
    column = pd.Series(pd.date_range("2024-01-01", periods=6, freq="h", tz=zone))
    change = pd.Timestamp("2024-01-01T02:00:00", tz=zone)
    expected = (pd.to_datetime(column, utc=True) >= change).tolist()
    for flag in (None, False):
        assert (pd.to_datetime(column, utc=flag) >= change).tolist() == expected
    assert (pd.to_datetime(column) >= change).tolist() == expected


def test_source_ids_do_not_depend_on_which_colon_splits_the_problem_name():
    assert all(":" not in name for name in sc.UCI_SOURCES)
    names = [f"adbench:{name}" for name in sc.UCI_SOURCES] + [
        "uci:7", "adbench:other", "adbench:a:b", "x:adbench:cardio", "nocolon", ""
    ]  # fmt: skip
    for problem in names:
        kind, _, name = problem.rpartition(":")
        expected = (
            f"uci:{sc.UCI_SOURCES[name][0]}"
            if kind == "adbench" and name in sc.UCI_SOURCES
            else problem
        )
        assert sc.source_id(problem) == expected


def test_holm_of_nothing_is_nothing():
    assert sc.holm([]) == []


@pytest.mark.parametrize("seed", range(4))
def test_constant_label_vectors_give_the_same_cleaning(seed):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "a": rng.integers(0, 3, 40).astype(float),
            "b": rng.choice(["x", "y", "z"], 40),
            "c": rng.normal(size=40),
        }
    )
    x0, _, report0 = nm.clean(frame, [0] * 40)
    x1, _, report1 = nm.clean(frame, [1] * 40)
    assert np.array_equal(x0, x1) and report0 == report1


def test_cleaning_returns_values_not_column_labels():
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": ["u", "v", "u", "w"]})
    renamed = frame.rename(columns={"a": "alpha", "b": "beta"})
    x, y, report = nm.clean(frame, [0, 1, 0, 1])
    x2, y2, report2 = nm.clean(renamed, [0, 1, 0, 1])
    assert np.array_equal(x, x2) and np.array_equal(y, y2)
    assert {k: v for k, v in report.items() if not isinstance(v, list)} == {
        k: v for k, v in report2.items() if not isinstance(v, list)
    }
