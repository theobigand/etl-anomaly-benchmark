"""Deterministic constraint baselines on synthetic fixtures (#137, #138, #139)."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rule_baselines as rb  # noqa: E402

TRAIN_TRACES = {
    "a": ["start", "work", "end"],
    "b": ["start", "work", "work", "end"],
    "c": ["start", "work", "end"],
}


def test_a_trace_equal_to_training_has_no_violation():
    scores = rb.SequenceConstraints().fit(TRAIN_TRACES).score(TRAIN_TRACES)
    assert scores.to_dict() == {"a": 0.0, "b": 0.0, "c": 0.0}


def test_each_sequence_constraint_counts_one_violation():
    rule = rb.SequenceConstraints().fit(TRAIN_TRACES)
    test = {
        "swap": ["start", "end", "work"],  # pairs start>end, end>work; last event work
        "first": ["work", "work", "end"],  # first event only
        "short": ["start", "end"],  # pair work>end is seen, start>end is not; length 2 < 3
        "long": ["start", "work", "work", "work", "work", "end"],  # length 6 > 4
    }
    scores = rule.score(test)
    assert scores["swap"] == 3.0
    assert scores["first"] == 1.0
    assert scores["short"] == 2.0
    assert scores["long"] == 1.0


def test_sequence_rule_rejects_unusable_training_and_unfitted_scoring():
    training = "^training needs at least one trace and no empty trace$"
    with pytest.raises(rb.RuleError, match=training):
        rb.SequenceConstraints().fit({})
    with pytest.raises(rb.RuleError, match=training):
        rb.SequenceConstraints().fit({"a": []})
    with pytest.raises(rb.RuleError, match="^the baseline is not fitted$"):
        rb.SequenceConstraints().score(TRAIN_TRACES)
    with pytest.raises(rb.RuleError, match="^trace 'x' is empty$"):
        rb.SequenceConstraints().fit(TRAIN_TRACES).score({"x": []})


def test_scores_are_floats_even_when_there_is_no_unit():
    assert rb.SequenceConstraints().fit(TRAIN_TRACES).score({}).dtype == float
    assert rb.SchemaPathRules().fit(TRAIN_RECORDS).score([]).dtype == float
    tables = {"parent": pd.DataFrame({"parent_id": [1]}), "child": pd.DataFrame({"parent_id": [1]})}
    assert rb.ForeignKeyIntegrity().score(tables).dtype == float


def test_foreign_key_flags_missing_and_unknown_keys_only():
    tables = {
        "parent": pd.DataFrame({"parent_id": [1, 2, None]}),
        "child": pd.DataFrame({"parent_id": [1, 2, 9, None, 2]}),
    }
    scores = rb.ForeignKeyIntegrity().fit(tables).score(tables)
    assert scores.to_dict() == {"0": 0.0, "1": 0.0, "2": 1.0, "3": 1.0, "4": 0.0}


def test_a_null_parent_key_does_not_validate_a_null_child_key():
    tables = {
        "parent": pd.DataFrame({"parent_id": [None, 1]}),
        "child": pd.DataFrame({"parent_id": [None]}),
    }
    assert rb.ForeignKeyIntegrity().score(tables).tolist() == [1.0]


def test_foreign_key_names_the_missing_declared_information():
    ok = pd.DataFrame({"parent_id": [1]})
    with pytest.raises(rb.RuleError, match="parent.parent_id"):
        rb.ForeignKeyIntegrity().score({"child": ok})
    with pytest.raises(rb.RuleError, match="child.parent_id"):
        rb.ForeignKeyIntegrity().fit({"parent": ok, "child": pd.DataFrame({"other": [1]})})
    with pytest.raises(rb.RuleError, match="parent.id"):
        rb.ForeignKeyIntegrity("id").fit({"parent": ok, "child": ok})


def test_foreign_key_uses_the_declared_column():
    tables = {"parent": pd.DataFrame({"id": [1]}), "child": pd.DataFrame({"id": [1, 2]})}
    assert rb.ForeignKeyIntegrity("id").score(tables).tolist() == [0.0, 1.0]


TRAIN_RECORDS = [
    {"id": 1, "meta": {"owner": {"name": "a"}}},
    {"id": 2, "meta": {"owner": {"name": "b"}}},
]


def test_schema_rules_give_one_unit_per_record_and_training_path():
    scores = rb.SchemaPathRules().fit(TRAIN_RECORDS).score(TRAIN_RECORDS)
    assert set(scores.index) == {
        "(0, 'id')",
        "(0, 'meta.owner.name')",
        "(1, 'id')",
        "(1, 'meta.owner.name')",
    }
    assert (scores == 0).all()


def test_schema_rules_flag_a_required_path_removed_and_a_changed_type():
    rule = rb.SchemaPathRules().fit(TRAIN_RECORDS)
    test = [{"id": 1, "meta": {}}, {"id": "x", "meta": {"owner": {"name": "b"}}}]
    scores = rule.score(test)
    assert scores["(0, 'meta.owner.name')"] == 1.0
    assert scores["(1, 'id')"] == 1.0
    assert scores["(0, 'id')"] == 0.0
    assert scores["(1, 'meta.owner.name')"] == 0.0


def test_an_optional_path_may_be_absent_but_not_of_a_new_type():
    train = [{"id": 1, "note": "x"}, {"id": 2}]
    rule = rb.SchemaPathRules().fit(train)
    scores = rule.score([{"id": 3}, {"id": 4, "note": 5}])
    assert scores["(0, 'note')"] == 0.0
    assert scores["(1, 'note')"] == 1.0


def test_schema_rules_reject_unusable_training_and_unfitted_scoring():
    with pytest.raises(rb.RuleError, match="^training needs at least one record$"):
        rb.SchemaPathRules().fit([])
    with pytest.raises(rb.RuleError, match="^the baseline is not fitted$"):
        rb.SchemaPathRules().score(TRAIN_RECORDS)


@pytest.mark.parametrize("protocol", ["P-SEQ", "P-REL", "P-NEST"])
def test_the_baseline_recovers_every_injected_unit_within_the_budget(protocol):
    result = rb.rule_validation(protocol, seed=7, faults=3, budget=0.2)
    assert result["synthetic"] is True
    assert result["baseline"] == rb.BASELINES[protocol][0]
    assert result["recall"] == result["max_recall"] == 1.0
    assert result["positives"] == 3


def test_the_validation_record_is_exact():
    result = rb.rule_validation("P-REL", seed=7, faults=3, budget=0.2)
    assert {key: value for key, value in result.items() if key != "alerts"} == {
        "protocol": "P-REL",
        "baseline": "fk_integrity",
        "unit": "relationship",
        "synthetic": True,
        "units": 60,
        "positives": 3,
        "k": 12,
        "recall": 1.0,
        "max_recall": 1.0,
    }
    assert len(result["alerts"]) == 12


def test_the_baseline_is_fitted_on_a_fixture_other_than_the_scored_one(monkeypatch):
    real = rb.ur.RUNNERS["P-SEQ"]
    seen = []

    def make(rng):
        seen.append(int(rng.integers(1 << 30)))
        return real.make(rng)

    fake = SimpleNamespace(unit=real.unit, units=real.units, inject=real.inject, make=make)
    monkeypatch.setitem(rb.ur.RUNNERS, "P-SEQ", fake)
    rb.rule_validation("P-SEQ", seed=7, faults=2, budget=0.2)
    assert seen == [int(np.random.default_rng(s).integers(1 << 30)) for s in (8, 7)]


def test_the_baseline_is_deterministic_for_a_seed():
    one = rb.rule_validation("P-SEQ", seed=3, faults=2, budget=0.2)
    assert one == rb.rule_validation("P-SEQ", seed=3, faults=2, budget=0.2)


def test_a_protocol_without_a_rule_baseline_is_refused():
    with pytest.raises(ValueError, match="P-TAB"):
        rb.rule_validation("P-TAB", seed=1, faults=1, budget=0.1)
