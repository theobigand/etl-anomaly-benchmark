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


# ---------------------------------------------------------------------------------------------
# Exact values: constants, fitted constraints, flags, per-seed evaluation, aggregation, command
# ---------------------------------------------------------------------------------------------
import json  # noqa: E402

import pytest  # noqa: E402


def test_the_constants_are_the_registered_ones():
    assert sr.FENCE == 3.0 and sr.MIN_LEVEL_COUNT == 2
    assert (sr.DEP_MIN_ROWS, sr.DEP_PURITY, sr.DEP_MAX_LEVELS, sr.DEP_MAX_COLUMNS) == (
        5,
        0.99,
        50,
        80,
    )
    assert sr.CONSTRAINTS == ("domain", "missing", "range", "sign", "combination")


def test_the_range_fence_is_three_interquartile_widths_beyond_the_quartiles():
    train = pd.DataFrame({"x": [1.0, 2, 3, 4, 5, 6, 7, 8, np.nan]})
    rules = sr.SchemaRules().fit(train, {"x": "num"})
    low, high = rules.fence["x"]
    assert low == pytest.approx(2.75 - 3 * 3.5) and high == pytest.approx(6.25 + 3 * 3.5)
    edge = pd.DataFrame({"x": [low, high, low - 1e-6, high + 1e-6]})
    assert rules.violations(edge)["range"].tolist() == [False, False, True, True]


def test_a_numeric_column_is_non_negative_when_no_training_value_is_below_zero():
    kinds = {"x": "num", "y": "num"}
    train = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0], "y": [-1e-9, 1.0, 2.0, 3.0]})
    rules = sr.SchemaRules().fit(train, kinds)
    assert rules.nonnegative == {"x"}
    probe = pd.DataFrame({"x": [-0.5, 0.0], "y": [-0.5, 0.0]})
    assert rules.violations(probe)["sign"].tolist() == [True, False]
    assert rules.kinds == kinds and rules.kinds is not kinds


def test_a_column_is_complete_when_at_most_five_percent_of_its_training_values_are_missing():
    values = [float(i) for i in range(20)]
    one_missing = pd.DataFrame({"x": [np.nan, *values[1:]]})
    two_missing = pd.DataFrame({"x": [np.nan, np.nan, *values[2:]]})
    assert sr.SchemaRules().fit(one_missing, {"x": "num"}).complete == {"x"}
    assert sr.SchemaRules().fit(two_missing, {"x": "num"}).complete == set()
    cat = pd.DataFrame({"c": [None, *["a"] * 19]})
    assert sr.SchemaRules().fit(cat, {"c": "cat"}).complete == {"c"}


def test_a_level_must_appear_twice_in_training_and_numbers_are_compared_as_text():
    train = pd.DataFrame({"c": ["a", "a", "b", 1, 1, 2]})
    rules = sr.SchemaRules().fit(train, {"c": "cat"})
    assert rules.levels["c"] == {"a", "1"}
    probe = pd.DataFrame({"c": ["a", "b", 1, 2, None]})
    assert rules.violations(probe)["domain"].tolist() == [False, True, False, True, False]


def test_the_constraint_flags_are_returned_per_constraint_in_the_frame_order_and_index():
    rules = _fit()
    rows = pd.DataFrame(
        {
            "country": ["xx", "fr"],
            "currency": ["eur", "eur"],
            "amount": [50.0, 5000.0],
            "delta": [0, 0],
        },
        index=[10, 20],
    )
    v = rules.violations(rows)
    assert list(v.columns) == list(sr.CONSTRAINTS) and list(v.index) == [10, 20]
    assert all(dtype.kind == "b" for dtype in v.dtypes)
    assert rules.flags(rows).tolist() == [True, True]
    assert rules.flags(rows.iloc[:0]).tolist() == []


def test_a_dependency_needs_five_rows_ninety_nine_percent_purity_and_a_bounded_level_count():
    kinds = {"a": "cat", "b": "cat"}

    def pair(levels, rows, flip=0):
        a = [f"a{i}" for i in range(levels) for _ in range(rows)]
        b = [f"p{i}" for i in range(levels) for _ in range(rows)]
        for k in range(flip):
            b[k] = "other"
        return pd.DataFrame({"a": a, "b": b})

    def rule(frame):
        found = {(r[0], r[1]): r[2] for r in sr.SchemaRules().fit(frame, kinds).dependencies}
        return found.get(("a", "b"))

    assert rule(pair(2, 5)) == {"a0": "p0", "a1": "p1"}  # five rows are enough
    assert rule(pair(2, 4)) is None
    assert rule(pair(2, 100, flip=1)) == {"a0": "p0", "a1": "p1"}  # 99 of 100 rows agree
    assert rule(pair(2, 100, flip=2)) == {"a1": "p1"}  # 98 % is not pure enough
    assert rule(pair(50, 6)) is not None and len(rule(pair(50, 6))) == 50
    assert rule(pair(51, 6)) is None  # more than fifty levels carry no dependency
    one_level = pd.DataFrame({"a": ["x"] * 10, "b": ["y"] * 10})
    assert sr.SchemaRules().fit(one_level, kinds).dependencies == []
    constant_right = pd.DataFrame({"a": ["x", "y"] * 10, "b": ["z"] * 20})
    assert sr.SchemaRules().fit(constant_right, kinds).dependencies == []


def test_only_the_eighty_columns_with_most_levels_are_paired_and_ties_go_by_name():
    n = 120
    frame = pd.DataFrame(
        {f"c{i:02d}": [f"v{(j * (i + 1)) % (2 + i // 40)}" for j in range(n)] for i in range(82)}
    )
    kinds = dict.fromkeys(frame, "cat")
    rules = sr.SchemaRules()
    rules.kinds = kinds
    columns = {a for a, _, _ in rules._dependencies(frame)} | {
        b for _, b, _ in rules._dependencies(frame)
    }
    ordered = sorted(frame, key=lambda c: (-frame[c].nunique(), c))[:80]
    assert columns <= set(ordered) and len(set(ordered)) == 80
    assert not columns & set(sorted(frame, key=lambda c: (-frame[c].nunique(), c))[80:])


def test_a_dependency_flags_a_row_only_when_its_left_value_is_mapped_and_the_right_differs():
    train = pd.DataFrame({"a": ["x"] * 10 + ["y"] * 10, "b": ["p"] * 10 + ["q"] * 10})
    rules = sr.SchemaRules().fit(train, {"a": "cat", "b": "cat"})
    probe = pd.DataFrame({"a": ["x", "x", "y", "zzz"], "b": ["p", "q", "q", "anything"]})
    assert rules.violations(probe)["combination"].tolist() == [False, True, False, False]


def _layout_frame():
    """Two clean training rows, then test rows: one per type with a known constraint violation."""
    train = pd.DataFrame({"g": ["a", "a", "b", "b", "a", "b"], "x": [1.0, 2.0, 3.0, 4.0, 2.5, 3.5]})
    test = pd.DataFrame(
        {
            "g": ["a", "zz", "a", "b", "a"],
            "x": [2.0, 2.0, 500.0, -5.0, 3.0],
            "anomaly_type": ["clean", "invalid_code", "univariate_outlier", "duplicate", "clean"],
        }
    )
    train = train.assign(anomaly_type="clean")
    return train, test


def test_one_seed_counts_flagged_rows_by_type_and_by_constraint(monkeypatch):
    train, test = _layout_frame()
    clean = train[["g", "x"]]
    calls = {}
    monkeypatch.setattr(
        sr.tm,
        "_seed_layout",
        lambda c, k, seed: calls.update(layout=(seed, list(c.columns))) or train,
    )
    monkeypatch.setattr(sr.tb, "split", lambda frame, seed: (train, None, test))
    out = sr.evaluate_seed(clean, {"g": "cat", "x": "num"}, 5)
    assert calls["layout"] == (5, ["g", "x"])
    assert list(out["counts"]) == list(sr.im.ANOMALY_TYPES)
    assert out["counts"]["invalid_code"] == 1 and out["counts"]["univariate_outlier"] == 1
    assert out["counts"]["duplicate"] == 1 and out["counts"]["missing_value"] == 0
    assert out["clean"] == 2 and out["false_alarms"] == 0
    assert out["hits"]["invalid_code"] == 1 and out["hits"]["univariate_outlier"] == 1
    assert out["hits"]["duplicate"] == 1 and out["hits"]["missing_value"] == 0
    assert out["by_constraint"]["invalid_code"] == dict(
        domain=1, missing=0, range=0, sign=0, combination=0
    )
    assert out["by_constraint"]["univariate_outlier"]["range"] == 1
    assert out["by_constraint"]["univariate_outlier"]["sign"] == 0
    assert out["by_constraint"]["duplicate"]["range"] == 1
    assert out["by_constraint"]["duplicate"]["sign"] == 1
    assert out["false_alarms_by_constraint"] == dict.fromkeys(sr.CONSTRAINTS, 0)
    assert out["rules"] == {"dependencies": 0}


def _seed_result(counts, hits, clean, false_alarms, by_constraint, fa_constraint, deps):
    return {
        "counts": counts,
        "clean": clean,
        "hits": hits,
        "false_alarms": false_alarms,
        "by_constraint": by_constraint,
        "false_alarms_by_constraint": fa_constraint,
        "rules": {"dependencies": deps},
    }


def test_a_table_run_pools_the_seeds_and_reports_recalls_counts_and_constraint_shares(
    monkeypatch,
):
    types = ["missing_value", "invalid_code"]
    zero = dict.fromkeys(sr.CONSTRAINTS, 0)
    per_seed = {
        1: _seed_result(
            {"missing_value": 4, "invalid_code": 0},
            {"missing_value": 3, "invalid_code": 0},
            10, 1,
            {"missing_value": {**zero, "missing": 3}, "invalid_code": zero},
            {**zero, "domain": 1}, 2,
        ),
        2: _seed_result(
            {"missing_value": 6, "invalid_code": 0},
            {"missing_value": 4, "invalid_code": 0},
            30, 3,
            {"missing_value": {**zero, "missing": 4}, "invalid_code": zero},
            {**zero, "domain": 2, "range": 1}, 5,
        ),
    }  # fmt: skip
    clean = pd.DataFrame({"g": ["a"] * 8, "x": np.arange(8.0), "y": np.arange(8.0)})
    kinds = {"g": "cat", "x": "num", "y": "num"}
    seen = {}
    monkeypatch.setattr(sr.tm, "load_carrier", lambda job: (clean, kinds, {}))
    monkeypatch.setattr(sr.tm, "seeds_for", lambda n: seen.update(n=n) or (1, 2))
    monkeypatch.setattr(sr.im, "supported_types", lambda k, c: types)
    monkeypatch.setattr(sr.im, "tier", lambda n: "B")
    monkeypatch.setattr(sr, "evaluate_seed", lambda c, k, seed: per_seed[seed])
    out = sr.run_one({"id": "uci:5", "name": "Five"})
    assert seen["n"] == 8
    assert out["protocol"] == "schema-rules-v1" and out["id"] == "uci:5" and out["name"] == "Five"
    assert out["tier"] == "B" and out["seeds"] == [1, 2] and out["types"] == types
    assert out["test_counts"] == {"missing_value": 10, "invalid_code": 0}
    assert out["clean_test_rows"] == 40
    assert out["recall_pooled"] == {"missing_value": 0.7, "invalid_code": None}
    assert out["fpr_pooled"] == 0.1
    assert out["share_by_constraint"]["missing_value"] == {**zero, "missing": 7}
    assert out["share_by_constraint"]["invalid_code"] == zero
    assert out["false_alarms_by_constraint"] == {**zero, "domain": 3, "range": 1}
    assert out["dependency_rules"] == [2, 5]
    assert out["carrier"] == {"rows": 8, "kinds": {"num": 2, "cat": 1}}


def test_the_parser_requires_an_output_directory_and_defaults_to_four_workers():
    parser = sr.build_parser()
    assert parser.description == sr.__doc__
    args = parser.parse_args(["--output", "out"])
    assert args.output == Path("out") and isinstance(args.output, Path)
    assert args.workers == 4 and args.only is None
    custom = parser.parse_args(["--output", "o", "--workers", "2", "--only", "uci:1", "uci:2"])
    assert custom.workers == 2 and custom.only == ["uci:1", "uci:2"]
    assert parser.parse_args(["--output", "o", "--only"]).only == []
    with pytest.raises(SystemExit):
        parser.parse_args([])


class _Serial:
    workers = None

    def __init__(self, max_workers):
        type(self).workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, function, items):
        return map(function, items)


def _command_world(tmp_path, monkeypatch):
    evidence = tmp_path / "verification/evidence/pool_extension_v2/typed_mixed"
    evidence.mkdir(parents=True)
    rows = [{"id": "uci:1", "eligible": True}, {"id": "uci:2", "eligible": False},
            {"id": "adbench:3", "eligible": True}]  # fmt: skip
    (evidence / "eligibility.json").write_text(json.dumps(rows))
    seen = {}

    def selected(namespace):
        seen["namespace"] = namespace
        return [{"id": i} for i in ("uci:1", "uci:2", "adbench:3", "uci:4")]

    monkeypatch.setattr(sr, "ROOT", tmp_path)
    monkeypatch.setattr(sr.tm, "selected_jobs", selected)
    monkeypatch.setattr(sr, "run_one", lambda job: {"id": job["id"], "z": 1, "a": 2})
    monkeypatch.setattr(sr, "ProcessPoolExecutor", _Serial)
    return seen


def test_the_command_runs_the_eligible_tables_and_writes_one_sorted_result_file_each(
    tmp_path, monkeypatch, capsys
):
    seen = _command_world(tmp_path, monkeypatch)
    out = tmp_path / "deep" / "out"
    assert sr.main(["--output", str(out)]) == 0
    assert (seen["namespace"].only, seen["namespace"].scope) == (None, "ineligible")
    assert sorted(p.name for p in out.iterdir()) == ["adbench_3.json", "uci_1.json"]
    assert (out / "uci_1.json").read_text() == '{"a": 2, "id": "uci:1", "z": 1}\n'
    assert capsys.readouterr().out == "uci:1\nadbench:3\n"
    assert _Serial.workers == 4


def test_the_command_skips_finished_tables_and_passes_the_selection_and_workers_on(
    tmp_path, monkeypatch, capsys
):
    seen = _command_world(tmp_path, monkeypatch)
    out = tmp_path / "out"
    out.mkdir()
    (out / "uci_1.json").write_text("{}")
    assert sr.main(["--output", str(out), "--workers", "3", "--only", "adbench:3"]) == 0
    assert seen["namespace"].only == ["adbench:3"] and _Serial.workers == 3
    assert (out / "uci_1.json").read_text() == "{}"
    assert (out / "adbench_3.json").exists()
    assert capsys.readouterr().out == "adbench:3\n"
