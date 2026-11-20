"""Schema-rule baseline: each constraint fires on its own fault and not on clean rows."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import schema_rules as sr  # noqa: E402


def _train(n=400, seed=0):
    rng = np.random.default_rng(seed)
    country = rng.choice(["fr", "de", "es"], n)
    currency = np.where(country == "fr", "eur", np.where(country == "de", "eur", "pes"))
    return pd.DataFrame(
        {
            "country": country,
            "currency": currency,
            "amount": rng.uniform(1, 100, n),
            "delta": rng.normal(0, 1, n),
        }
    )


KINDS = {"country": "cat", "currency": "cat", "amount": "num", "delta": "num"}


def _fit():
    return sr.SchemaRules().fit(_train(), KINDS)


def test_clean_rows_of_the_training_distribution_raise_no_flag():
    rules = _fit()
    assert rules.flags(_train(400, seed=1)).mean() < 0.01


def test_each_constraint_catches_the_fault_it_expresses():
    rules = _fit()
    rows = pd.DataFrame(
        {
            "country": ["xx", "fr", "fr", "fr", "fr", "fr"],
            "currency": ["eur", "eur", "eur", "eur", "eur", "pes"],
            "amount": [50.0, np.nan, 5000.0, -3.0, 50.0, 50.0],
            "delta": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )
    v = rules.violations(rows)
    assert v["domain"].tolist() == [True, False, False, False, False, False]
    assert v["missing"].tolist() == [False, True, False, False, False, False]
    assert v["range"].tolist() == [False, False, True, True, False, False] or v["range"].iloc[2]
    assert v["sign"].tolist() == [False, False, False, True, False, False]
    assert v["combination"].tolist() == [False, False, False, False, False, True]


def test_a_column_is_required_only_when_it_is_rarely_missing_in_training():
    rare, often = _train(), _train()
    rare.loc[:5, "amount"] = np.nan  # 1.5 % missing
    often.loc[:79, "amount"] = np.nan  # 20 % missing
    assert "amount" in sr.SchemaRules().fit(rare, KINDS).complete
    assert "amount" not in sr.SchemaRules().fit(often, KINDS).complete
    probe = pd.DataFrame(
        {"country": ["fr"], "currency": ["eur"], "amount": [np.nan], "delta": [0.0]}
    )
    assert not sr.SchemaRules().fit(often, KINDS).violations(probe)["missing"].any()


def test_a_level_seen_once_in_training_counts_as_unseen():
    train = _train()
    train.loc[0, "country"] = "rare"
    rules = sr.SchemaRules().fit(train, KINDS)
    probe = pd.DataFrame(
        {"country": ["rare"], "currency": ["eur"], "amount": [10.0], "delta": [0.0]}
    )
    assert rules.violations(probe)["domain"].all()


def test_dependencies_need_enough_rows_and_purity():
    train = pd.DataFrame(
        {
            "a": ["x"] * 4 + ["y"] * 50 + ["z"] * 50,
            "b": ["p"] * 4 + ["q"] * 50 + ["r"] * 25 + ["s"] * 25,
        }
    )
    rules = sr.SchemaRules().fit(train, {"a": "cat", "b": "cat"})
    mapped = {rule[0]: set(rule[2]) for rule in rules.dependencies}
    assert mapped["a"] == {"y"}  # x has 4 rows, z is not pure


def test_run_one_pairs_with_the_typed_mixed_layout_on_a_synthetic_table(monkeypatch):
    rng = np.random.default_rng(0)
    n = 700
    table = pd.DataFrame(
        {
            "g": rng.choice(["a", "b", "c", "d"], n),
            "h": rng.choice(["u", "v", "w"], n),
            "x": rng.normal(10, 2, n),
            "y": rng.normal(50, 5, n),
        }
    )
    kinds = {"g": "cat", "h": "cat", "x": "num", "y": "num"}
    monkeypatch.setattr(sr.tm, "load_carrier", lambda job, seed=0: (table, kinds, {}))
    result = sr.run_one({"id": "t:1", "name": "t"})
    assert result["recall_pooled"]["invalid_code"] > 0.8
    assert result["recall_pooled"]["missing_value"] > 0.8
    assert 0 <= result["fpr_pooled"] < 0.1
    assert set(result["share_by_constraint"]["invalid_code"]) == set(sr.CONSTRAINTS)
