"""Counterexample searches for classes of surviving mutants that look behaviourally equivalent.

These tests approve nothing and change no policy file. Each one states a language or library
fact that a surviving mutant would have to contradict, and searches for a contradiction over
structured and random inputs with a fixed seed. A failure would be a counterexample to the
proposal of the second owner review packet; a pass is evidence for the owner, not a decision.
"""

import ast
import json
import random
import string
import urllib.request
from importlib.metadata import version

import numpy as np
import pandas as pd
import pytest

RNG = random.Random(20261113)
ALPHABET = "ab:_.,;/ \u00e9"


def _words(count=2000):
    for _ in range(count):
        yield "".join(RNG.choice(ALPHABET) for _ in range(RNG.randint(0, 14)))


@pytest.mark.parametrize("separator", ["::", "__mutmut_", ": ", "#", "?", "[", "*"])
def test_the_first_part_of_a_split_does_not_depend_on_a_limit_of_one_or_more(separator):
    for text in _words():
        text = text.replace(":", separator[:1]) if RNG.random() < 0.5 else text
        first = text.split(separator, 1)[0]
        assert first == text.split(separator)[0] == text.split(separator, 2)[0]
        assert first == text.split(separator, -1)[0] == text.split(separator, 5)[0]


def test_json_with_allow_nan_none_refuses_non_finite_numbers_like_false():
    for value in (float("nan"), float("inf"), -float("inf"), {"a": [float("nan")]}):
        with pytest.raises(ValueError) as strict:
            json.dumps(value, allow_nan=False)
        with pytest.raises(ValueError) as lenient:
            json.dumps(value, allow_nan=None)
        assert str(strict.value) == str(lenient.value)
    for value in (1, 2.5, "x", [1, {"b": None}]):
        assert json.dumps(value, allow_nan=False) == json.dumps(value, allow_nan=None)


def test_ast_dump_without_field_names_is_the_same_for_false_and_none():
    for source in ("x = 1", "def f(a, *b, c=2):\n    return a + c", "class A:\n    y: int = 3"):
        tree = ast.parse(source)
        assert ast.dump(tree, annotate_fields=False) == ast.dump(tree, annotate_fields=None)


@pytest.mark.parametrize("name", ["stable", "STABLE", "Stable", "mergesort"])
def test_a_sort_kind_is_read_without_case(name):
    values = np.random.default_rng(1).integers(0, 5, 200)
    assert np.argsort(values, kind="stable").tolist() == np.argsort(values, kind=name).tolist()


def test_a_missing_sort_flag_in_a_groupby_means_no_sorting_like_false():
    frame = pd.DataFrame({"k": ["b", "a", "b", "c", "a"], "v": [1, 2, 3, 4, 5]})
    for aggregate in ("mean", "sum", "std", "first"):
        left = getattr(frame.groupby("k", sort=False)["v"], aggregate)()
        right = getattr(frame.groupby("k", sort=None)["v"], aggregate)()
        pd.testing.assert_series_equal(left, right)


def test_a_missing_index_flag_in_to_csv_writes_no_index_like_false(tmp_path):
    frame = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}, index=[10, 20])
    frame.to_csv(tmp_path / "a.csv", index=False)
    frame.to_csv(tmp_path / "b.csv", index=None)
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()


def test_a_missing_replace_flag_in_a_choice_samples_without_replacement_like_false():
    for seed in range(50):
        values = np.arange(10)
        size = int(np.random.default_rng(seed).integers(1, 11))
        a = np.random.default_rng(seed).choice(values, size=size, replace=False)
        b = np.random.default_rng(seed).choice(values, size=size, replace=None)
        assert a.tolist() == b.tolist()


def test_a_package_version_is_looked_up_without_regard_to_case():
    for name in ("numpy", "pandas"):
        assert version(name) == version(name.upper()) == version(name.capitalize())


def test_http_header_names_are_stored_with_one_capitalisation():
    first = urllib.request.Request("https://example.org", headers={"User-Agent": "x"})
    for name in ("user-agent", "USER-AGENT", "User-agent"):
        other = urllib.request.Request("https://example.org", headers={name: "x"})
        assert other.header_items() == first.header_items()


@pytest.mark.parametrize("name", ["utc", "UTC", "Etc/UTC"])
def test_a_timezone_name_is_read_without_case_for_utc(name):
    stamp = pd.Timestamp("2020-01-01")
    assert stamp.tz_localize("UTC") == stamp.tz_localize(name)


def test_a_codec_name_is_read_without_case():
    data = "h\u00e9llo".encode()
    assert data.decode("utf-8", "replace") == data.decode("UTF-8", "replace")


def test_a_division_by_minus_one_is_a_multiplication_by_minus_one():
    gen = np.random.default_rng(3)
    values = gen.normal(size=200)
    assert (values / -1).tolist() == (values * -1).tolist()
    assert (np.arange(5) / -1).tolist() == (np.arange(5) * -1).tolist()


def test_the_first_element_of_a_split_with_several_limits_is_stable_for_random_text():
    letters = string.ascii_lowercase
    for _ in range(500):
        text = "".join(RNG.choice(letters + "|") for _ in range(RNG.randint(0, 20)))
        assert text.split("|", 1)[0] == text.partition("|")[0]
