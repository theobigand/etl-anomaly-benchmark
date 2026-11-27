"""Unit scoring contract, featurizers and synthetic end-to-end validation (no real data)."""

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unit_runner as ur  # noqa: E402
import unit_scoring as us  # noqa: E402

from etl_benchmark.quality import ZScoreDetector  # noqa: E402


class Stub:
    """Scores one named feature; a detector in name only, to test the wiring."""

    def __init__(self, column):
        self.column = column

    def fit(self, frame):
        return self

    def score(self, frame):
        return frame[self.column]


def test_the_alert_count_is_a_floor_free_of_binary_rounding():
    assert us.alert_count(100, 0.29) == 29
    assert us.alert_count(1000, 0.01) == 10
    assert us.alert_count(99, 0.01) == 0  # no minimum-one-alert exception
    assert us.alert_count(1500, 0.01) == 15
    for budget in (0, -0.1, 1.5):
        with pytest.raises(ValueError, match="^the budget must be in \\(0, 1\\]$"):
            us.alert_count(10, budget)


def test_alerts_follow_the_score_and_break_ties_by_the_sha256_of_the_identifier():
    scores = pd.Series({"a": 1.0, "b": 2.0, "c": 2.0, "d": 0.5})
    alerts = us.select_alerts(scores, 2)
    assert alerts == sorted(["b", "c"], key=lambda u: hashlib.sha256(u.encode()).hexdigest())
    assert us.select_alerts(scores, 3)[2] == "a" and us.select_alerts(scores, 0) == []
    assert us.select_alerts(scores, 9) == [*alerts, "a", "d"]
    assert us.tie_key("a") == hashlib.sha256(b"a").hexdigest()


def test_a_missing_score_or_a_repeated_identifier_is_an_error_not_a_low_score():
    with pytest.raises(ValueError, match="^a missing score is not a score$"):
        us.select_alerts(pd.Series({"a": 1.0, "b": np.nan}), 1)
    with pytest.raises(ValueError, match="^unit identifiers must be unique$"):
        us.select_alerts(pd.Series([1.0, 2.0], index=["a", "a"]), 1)


def test_recall_and_the_attainable_maximum():
    assert us.recall_at_k(["a", "x"], ["a", "b"]) == 0.5
    assert us.max_recall(2, 5) == 0.4 and us.max_recall(9, 5) == 1.0
    with pytest.raises(ValueError, match="^recall needs at least one positive unit$"):
        us.recall_at_k(["a"], [])


@pytest.mark.parametrize("protocol", sorted(ur.RUNNERS))
def test_every_featurizer_names_exactly_the_units_of_the_runner(protocol):
    runner = ur.RUNNERS[protocol]
    data = runner.make(np.random.default_rng(3))
    train, test = us._featurize(protocol, data, data, False)
    units = sorted(str(u) for u in runner.units(data))
    if protocol == "P-NEST":  # the featurizer covers every leaf path, the runner one path
        assert set(units) < set(test.index)
    else:
        assert sorted(test.index) == units
    assert list(train.columns) == list(test.columns)
    assert not test.isna().any().any() and test.shape[1] >= 1


def test_the_window_features_describe_each_window():
    wide = pd.DataFrame({"s": np.arange(20, dtype=float)})
    out = us.window_features(wide, window=10)
    assert list(out.index) == ["('s', 0)", "('s', 1)"]
    first = out.loc["('s', 0)"]
    assert first["mean"] == 4.5 and first["min"] == 0 and first["max"] == 9
    assert first["slope"] == pytest.approx(1.0) and first["mean_abs_diff"] == 1.0
    assert first["std"] == pytest.approx(np.arange(10).std())


def test_unseen_bigrams_are_counted_against_the_training_vocabulary():
    train = {"t1": ["a", "b", "c"], "t2": ["a", "b", "c"]}
    featurizer = us.SequenceFeaturizer().fit(train)
    out = featurizer.transform({"x": ["a", "c", "b"], "y": ["a", "b", "c"]})
    assert list(out.columns) == ["length", "unseen_bigrams", "a>b", "b>c"]
    assert out.loc["x"].tolist() == [3.0, 2.0, 0.0, 0.0]
    assert out.loc["y"].tolist() == [3.0, 0.0, 1.0, 1.0]


def test_the_reference_check_feature_is_the_foreign_key_test_itself():
    tables = {
        "parent": pd.DataFrame({"parent_id": [1, 2]}),
        "child": pd.DataFrame({"parent_id": [1, 9, 2]}),
    }
    plain = us.relationship_features(tables)
    checked = us.relationship_features(tables, reference_check=True)
    assert list(plain.columns) == ["parent_id"] and "reference_present" not in plain
    assert checked["reference_present"].tolist() == [1.0, 0.0, 1.0]
    assert list(checked.index) == ["0", "1", "2"] and "foreign-key check" in us.REFERENCE_CHECK_NOTE


def test_nested_paths_are_units_and_a_removed_field_is_an_absent_path_not_a_dropped_row():
    train = [{"a": {"b": 1, "c": "xy"}, "t": [1, 2]}, {"a": {"b": 2, "c": "z"}, "t": []}]
    featurizer = us.PathFeaturizer().fit(train)
    assert featurizer.paths == ["a.b", "a.c", "t"]
    out = featurizer.transform([{"a": {"b": 5}, "t": [1]}])
    assert list(out.index) == ["(0, 'a.b')", "(0, 'a.c')", "(0, 't')"]
    assert out.loc["(0, 'a.b')"].tolist() == [1.0, 2.0, 2.0, 5.0, 0.0]
    assert out.loc["(0, 'a.c')"].tolist() == [0.0, 0.0, 2.0, 0.0, 0.0]
    assert out.loc["(0, 't')"].tolist() == [1.0, 4.0, 1.0, 0.0, 1.0]


def test_the_synthetic_validation_contract_holds_for_every_protocol():
    for protocol in sorted(ur.RUNNERS):
        run = us.synthetic_validation(protocol, ZScoreDetector, seed=1, faults=3, budget=0.1)
        assert run["synthetic"] is True and run["protocol"] == protocol
        assert run["positives"] == 3 and len(run["alerts"]) == run["k"] == us.alert_count(
            run["units"], 0.1
        )
        assert 0.0 <= run["recall"] <= run["max_recall"] <= 1.0
        assert run == us.synthetic_validation(
            protocol, ZScoreDetector, seed=1, faults=3, budget=0.1
        )


class _FailsCheck(Stub):
    """Alerts on the units that fail the declared foreign-key check."""

    def __init__(self):
        super().__init__("reference_present")

    def score(self, frame):
        return 1.0 - frame["reference_present"]


def test_a_constraint_feature_finds_every_injected_reference_by_construction():
    run = us.synthetic_validation("P-REL", _FailsCheck, 1, 3, 0.1, reference_check=True)
    # k = 6 covers the 3 injected units and the fixture's 2 natural orphans (the baseline)
    assert run["recall"] == 1.0 and run["k"] == 6


def test_an_unknown_protocol_has_no_featurizer():
    with pytest.raises(ValueError, match="^no featurizer for protocol 'P-X'$"):
        us._featurize("P-X", None, None, False)


def test_path_features_pin_every_type_depth_number_and_size():
    records = [
        {
            "flag": True,
            "n": 7,
            "x": 2.5,
            "s": "abc",
            "l": [1, 2],
            "o": {},
            "d": {"e": {"f": 1}},
            "z": None,
        }
    ]
    featurizer = us.PathFeaturizer().fit(records)
    assert featurizer.paths == ["d.e.f", "flag", "l", "n", "o", "s", "x", "z"]
    out = featurizer.transform(records)
    expected = {
        "d.e.f": [1.0, 2.0, 3.0, 1.0, 0.0],
        "flag": [1.0, 1.0, 1.0, 1.0, 0.0],
        "l": [1.0, 4.0, 1.0, 0.0, 2.0],
        "n": [1.0, 2.0, 1.0, 7.0, 0.0],
        "o": [1.0, 5.0, 1.0, 0.0, 0.0],
        "s": [1.0, 3.0, 1.0, 0.0, 3.0],
        "x": [1.0, 2.0, 1.0, 2.5, 0.0],
        "z": [1.0, 6.0, 1.0, 0.0, 0.0],
    }
    assert {k: out.loc[f"(0, '{k}')"].tolist() for k in expected} == expected
    assert list(out.columns) == ["present", "type", "depth", "number", "size"]
    missing = us.PathFeaturizer().fit(records).transform([{}])
    assert missing.loc["(0, 'd.e.f')"].tolist() == [0.0, 0.0, 3.0, 0.0, 0.0]
    assert us.PathFeaturizer().paths == []


def test_window_features_pin_a_noisy_window_and_the_window_count():
    wide = pd.DataFrame({"a": [1.0, 3.0, 2.0, 6.0, 4.0, 0.0], "b": range(6)})
    out = us.window_features(wide, window=3)
    assert list(out.index) == ["('a', 0)", "('a', 1)", "('b', 0)", "('b', 1)"]
    assert out.loc["('a', 0)"].tolist() == pytest.approx([2.0, np.sqrt(2 / 3), 1.0, 3.0, 0.5, 1.5])
    assert out.loc["('a', 1)"].tolist() == pytest.approx(
        [
            10 / 3,
            np.sqrt(((6 - 10 / 3) ** 2 + (4 - 10 / 3) ** 2 + (10 / 3) ** 2) / 3),
            0.0,
            6.0,
            -3.0,
            3.0,
        ]
    )
    assert us.window_features(pd.DataFrame({"a": [1.0] * 7}), window=3).shape == (2, 6)


def test_tab_features_keep_numeric_columns_only_and_index_by_position():
    frame = pd.DataFrame({"n": [1, 2], "t": ["a", "b"], "f": [0.5, 1.5]}, index=[10, 20])
    out = us.tab_features(frame)
    assert list(out.index) == ["0", "1"] and list(out.columns) == ["n", "f"]
    assert out["n"].dtype == float and frame["n"].dtype != float


def test_sequence_features_use_sorted_bigrams_and_count_repeats():
    featurizer = us.SequenceFeaturizer()
    assert featurizer.bigrams == []
    featurizer.fit({"a": ["x", "y", "x", "y"], "b": ["y", "z"]})
    assert featurizer.bigrams == [("x", "y"), ("y", "x"), ("y", "z")]
    out = featurizer.transform({"q": ["x", "y", "x", "y"], "p": ["z"]})
    assert list(out.index) == ["p", "q"]
    assert out.loc["q"].tolist() == [4.0, 0.0, 2.0, 1.0, 0.0]
    assert out.loc["p"].tolist() == [1.0, 0.0, 0.0, 0.0, 0.0]
    assert us.SequenceFeaturizer().fit({"a": ["x"]}).bigrams == []


def test_the_relationship_features_keep_numeric_child_columns_and_the_key_name_is_configurable():
    tables = {
        "parent": pd.DataFrame({"pid": [1]}),
        "child": pd.DataFrame({"pid": [1, 5], "v": [2.0, 3.0], "t": ["a", "b"]}),
    }
    out = us.relationship_features(tables, key="pid", reference_check=True)
    assert list(out.columns) == ["pid", "v", "reference_present"]
    assert out["reference_present"].tolist() == [1.0, 0.0] and out["pid"].dtype == float


def test_a_budget_of_one_alerts_every_unit_and_the_validation_reports_its_budget():
    assert us.alert_count(7, 1.0) == 7 and us.alert_count(7, 0.5) == 3
    run = us.synthetic_validation("P-TAB", ZScoreDetector, seed=2, faults=2, budget=1.0)
    assert run["k"] == run["units"] == 80 and run["recall"] == 1.0 and run["max_recall"] == 1.0
    assert set(run) == {
        "protocol",
        "unit",
        "synthetic",
        "units",
        "positives",
        "k",
        "recall",
        "max_recall",
        "alerts",
    }
    assert run["unit"] == "row"


def test_the_validation_trains_on_another_fixture_than_the_one_it_scores():
    seen = {}

    class Spy(Stub):
        def __init__(self):
            super().__init__("amount")

        def fit(self, frame):
            seen["train"] = frame.copy()
            return self

        def score(self, frame):
            seen["test"] = frame.copy()
            return frame["amount"]

    us.synthetic_validation("P-TAB", Spy, seed=4, faults=2, budget=0.1)
    assert not seen["train"]["amount"].equals(seen["test"]["amount"])
    clean = ur.RUNNERS["P-TAB"].make(np.random.default_rng(5))
    assert seen["train"]["amount"].tolist() == list(clean["amount"])
