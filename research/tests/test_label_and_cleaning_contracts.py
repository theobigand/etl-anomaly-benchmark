"""Boundaries of label derivation, column roles, table repair and cleaning."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalise as nm  # noqa: E402
import uci_loader as ul  # noqa: E402

META = {
    "tasks": ["Classification"],
    "target_col": ["cls"],
    "variables": [{"name": "cls", "role": "Target"}],
}


def _table(rare, common):
    values = ["rare"] * rare + ["common"] * common
    rng = np.random.default_rng(0)
    return pd.DataFrame({"f0": rng.normal(size=len(values)), "cls": values})


def _no_labels(frame, meta=META):
    with pytest.raises(ul.NoLabels) as caught:
        ul.derive_labels(frame, meta)
    return str(caught.value)


def test_refusals_state_their_exact_reason():
    assert _no_labels(_table(30, 300), {**META, "tasks": ["Regression"]}) == (
        "not a classification task"
    )
    assert _no_labels(_table(0, 300)) == "fewer than 2 classes"
    assert _no_labels(_table(ul.MIN_ANOMALIES - 1, 300)) == (
        f"fewer than {ul.MIN_ANOMALIES} rows in the rarest class"
    )


def test_a_rarest_class_with_exactly_the_minimum_rows_is_accepted():
    features, labels, info = ul.derive_labels(_table(ul.MIN_ANOMALIES, 380), META)
    assert info["anomalies"] == ul.MIN_ANOMALIES and info["rows"] == 400
    assert labels.dtype == np.dtype(int) and int(labels.sum()) == ul.MIN_ANOMALIES
    assert info["kind"] == "native_rare" and len(features) == 400


def test_the_target_rate_boundary_is_kept_as_is_and_above_it_is_downsampled():
    _, labels, info = ul.derive_labels(_table(40, 360), META)  # exactly 10 %
    assert info["natural_rate"] == pytest.approx(ul.TARGET_RATE)
    assert info["kind"] == "native_rare" and int(labels.sum()) == 40 and info["rows"] == 400
    features, labels, info = ul.derive_labels(_table(200, 300), META)
    assert info["kind"] == "downsampled"
    kept = round(300 * ul.TARGET_RATE / (1 - ul.TARGET_RATE))
    assert (info["rows"], info["anomalies"]) == (300 + kept, kept)
    assert int(labels.sum()) == kept and len(features) == len(labels) == 300 + kept


def test_the_downsampled_rows_follow_the_fixed_seed():
    frame = _table(200, 300)
    first = ul.derive_labels(frame, META)[0]
    assert first.equals(ul.derive_labels(frame, META)[0])
    rare = np.flatnonzero((frame["cls"] == "rare").to_numpy())
    chosen = np.random.default_rng(ul.SEED).choice(rare, 33, replace=False)
    expected = np.sort(np.r_[np.flatnonzero((frame["cls"] == "common").to_numpy()), chosen])
    assert np.array_equal(first["f0"].to_numpy(), frame["f0"].to_numpy()[expected])


def test_identifier_and_other_roles_leave_the_features_but_other_case_does_not():
    frame = pd.DataFrame(
        {"a": [1.0, 2], "id": [1, 2], "misc": [3, 4], "case": [5, 6], "cls": ["x", "y"]}
    )
    meta = {
        "target_col": ["cls"],
        "variables": [
            {"name": "id", "role": "ID"},
            {"name": "misc", "role": "Other"},
            {"name": "case", "role": "other"},
            {"name": "cls", "role": "Target"},
        ],
    }
    features, target = ul.split_columns(frame, meta)
    assert list(features.columns) == ["a", "case"] and list(target) == ["x", "y"]


@pytest.mark.parametrize("targets", [[], ["cls", "other"], ["absent"]])
def test_a_missing_or_ambiguous_target_gives_an_all_missing_aligned_target(targets):
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0], "cls": ["x", "y", "x"], "other": [1, 2, 3]})
    frame.index = [5, 6, 7]
    features, target = ul.split_columns(frame, {"target_col": targets, "variables": []})
    assert target.isna().all() and list(target.index) == [5, 6, 7] and len(target) == 3


def test_the_index_value_tokens_follow_the_documented_share_and_exponent_forms(tmp_path):
    def read(tokens):
        path = tmp_path / "t.csv"
        pd.DataFrame({"v": tokens, "k": range(len(tokens))}).to_csv(path, index=False)
        return ul.read_table(path)["v"]

    tokens = [f"{i}:{i}.5" for i in range(99)] + ["garbage"]
    assert pd.to_numeric(read(tokens), errors="coerce").notna().sum() == 99  # exactly 99 % kept
    below = [f"{i}:{i}.5" for i in range(98)] + ["x", "y"]
    assert read(below).iloc[0] == "0:0.5"  # 98 % is below the 99 % share
    assert read([f"{i}:2E5" for i in range(10)]).iloc[0] == 2e5
    assert read([f"{i}:2e-3" for i in range(10)]).iloc[0] == pytest.approx(2e-3)


def test_a_numeric_looking_text_column_becomes_numbers_only_at_ninety_nine_percent(tmp_path):
    def read(extra):
        path = tmp_path / "n.csv"
        values = [str(i) for i in range(100 - len(extra))] + extra
        pd.DataFrame({"v": values, "k": range(100)}).to_csv(path, index=False)
        return ul.read_table(path)["v"]

    exact = read(["x"])  # 99 of 100 values are numbers
    assert pd.api.types.is_numeric_dtype(exact) and int(exact.isna().sum()) == 1
    assert not pd.api.types.is_numeric_dtype(read(["x", "y"]))  # 98 % is below the share


def test_cleaning_reports_rows_in_and_keeps_boundary_columns():
    rows = 40
    frame = pd.DataFrame(
        {
            "num": np.arange(rows, dtype=float),
            "half": np.where(np.arange(rows) % 2 == 0, np.nan, np.arange(rows, dtype=float)),
            "cat": [f"c{i % nm.CATEGORY_CAP}" for i in range(rows)],
        }
    )
    x, y, report = nm.clean(frame, np.arange(rows) % 2)
    assert report["rows_in"] == rows and report["dropped_missing"] == []
    assert report["encoded"] == ["cat"] and report["dropped_high_cardinality"] == []
    assert x.shape[1] == 2 + nm.CATEGORY_CAP and y.dtype == np.dtype(int)
    over = frame.assign(cat=[f"c{i % (nm.CATEGORY_CAP + 1)}" for i in range(rows)])
    assert nm.clean(over, np.arange(rows) % 2)[2]["dropped_high_cardinality"] == ["cat"]
    more = frame.assign(
        half=np.where(np.arange(rows) % 4 != 3, np.nan, np.arange(rows, dtype=float))
    )
    assert nm.clean(more, np.arange(rows) % 2)[2]["dropped_missing"] == ["half"]


def test_encoded_columns_are_prefixed_with_their_name_and_numeric(tmp_path):
    frame = pd.DataFrame({"num": [1.0, 2, 3, 4], "kind": ["a", "b", "a", "b"]})
    x, y, report = nm.clean(frame, [0, 1, 0, 1])
    assert x.dtype == np.dtype(float) and x.shape == (4, 3)
    assert report["features_out"] == 3 and report["rows_out"] == 4


def test_a_frame_without_any_usable_feature_is_refused_with_the_exact_reason():
    frame = pd.DataFrame({"constant": [1.0] * 6, "empty": [np.nan] * 6})
    with pytest.raises(nm.NormaliseError) as caught:
        nm.clean(frame, [0, 1] * 3)
    assert str(caught.value) == "no usable feature left"


def test_rows_with_identical_features_and_conflicting_labels_are_removed_even_with_missing_values():
    frame = pd.DataFrame(
        {"a": [1.0, 1.0, np.nan, np.nan, 5.0, 6.0], "b": [2.0, 2.0, 3.0, 3.0, 9.0, 8.0]}
    )
    x, y, report = nm.clean(frame, [0, 1, 0, 1, 1, 0])
    assert report["conflicting_rows_removed"] == 4 and report["rows_out"] == 2
    assert sorted(y.tolist()) == [0, 1] and report["duplicates_removed"] == 0


def test_labels_are_read_as_integers():
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [4.0, 3.0, 1.0, 2.0]})
    _, y, _ = nm.clean(frame, np.array([0.0, 1.0, 1.0, 0.0]))
    assert y.dtype == np.dtype(int) and y.tolist() == [0, 1, 1, 0]
