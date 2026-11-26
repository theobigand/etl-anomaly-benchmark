"""Registry-driven units: compatibility, loading, planning and the authorization guard."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch_panel as bp  # noqa: E402
import pipeline_batch as pb  # noqa: E402
import registry_units as ru  # noqa: E402


def _frame(n=2400, columns=4, seed=0):
    rng = np.random.default_rng(seed)
    times = pd.date_range("2021-01-01", periods=n, freq="h")
    # shuffled on purpose: the loader must restore the time order
    data = {f"x{i}": rng.normal(size=n) for i in range(columns)}
    frame = pd.DataFrame({"when": times.strftime("%Y-%m-%d %H:%M:%S"), **data})
    return frame.sample(frac=1.0, random_state=1).reset_index(drop=True)


def _entry(eligible, reasons=()):
    return {"eligible": eligible, "reasons": list(reasons)}


def test_every_protocol_has_a_registered_or_proposed_unit_and_only_one_is_registered():
    assert set(ru.PROTOCOL_UNITS) == {"P-TS", "P-TAB", "P-SEQ", "P-REL", "P-NEST"}
    registered = [u for u, (s, _) in ru.UNITS.items() if s == ru.REGISTERED]
    assert registered == ["temporal_batch"]
    assert ru.UNITS["temporal_batch"][1] == tuple(pb.MECHANISMS)
    for units in ru.PROTOCOL_UNITS.values():
        assert all(u in ru.UNITS for u in units)


def test_the_batch_unit_is_runnable_exactly_when_the_audit_is_eligible():
    (row,) = ru.compatibility("P-TS", _entry(True))
    assert row["runnable"] and row["reason"] == "" and row["detectors"]
    (row,) = ru.compatibility("P-TS", _entry(False, ["only 3 continuous columns", "b"]))
    assert not row["runnable"]
    assert row["reason"] == "only 3 continuous columns; b"  # a missing table, not an invalid group


def test_a_proposed_unit_is_never_runnable_and_has_no_detector_profile():
    rows = ru.compatibility("P-REL", _entry(True))
    batch, relational = rows
    assert batch["runnable"] and not relational["runnable"]
    assert relational["status"] == ru.PROPOSED
    assert relational["reason"] == "unsupported: the unit has no approved definition"
    assert not relational["detectors"]
    assert "referential_integrity" in relational["mechanisms"]
    (document,) = ru.compatibility("P-NEST", _entry(True))
    assert not document["runnable"] and document["unit"] == "document_batch"


def test_group_protocols_take_the_first_fact_of_each_group_in_identifier_order():
    facts = {
        "b": {"independent_group": "g", "protocol_id": "P-REL"},
        "a": {"independent_group": "g", "protocol_id": "P-TS"},
        "c": {"independent_group": "h", "protocol_id": "P-SEQ"},
        "d": {"protocol_id": "P-TAB"},
    }
    assert ru.group_protocols(facts) == {"g": "P-TS", "h": "P-SEQ"}


def test_clean_table_orders_by_time_and_keeps_continuous_columns_and_naive_time():
    table, info = ru.clean_table(_frame())
    assert info == {"time_column": "when", "columns": ["x0", "x1", "x2", "x3"]}
    assert list(table.columns) == ["x0", "x1", "x2", "x3", pb.TIME]
    assert table[pb.TIME].is_monotonic_increasing
    assert table[pb.TIME].dt.tz is None
    assert len(table) == 2400
    assert table[pb.TIME].iloc[0] == pd.Timestamp("2021-01-01 00:00:00")


def test_clean_table_drops_incomplete_and_repeated_rows_and_trend_columns():
    frame = _frame().assign(counter=lambda f: pd.to_datetime(f["when"]).rank())
    frame.loc[:9, "x0"] = np.nan
    table, info = ru.clean_table(frame)
    assert "counter" not in info["columns"] and len(table) == 2390
    repeated = pd.concat([_frame(), _frame().iloc[:5]], ignore_index=True)
    assert len(ru.clean_table(repeated)[0]) == 2400


def test_clean_table_refuses_an_ineligible_table_with_the_audit_reason():
    with pytest.raises(ValueError, match="only 3 continuous columns"):
        ru.clean_table(_frame(columns=3))


def _views(tmp_path, n=2400):
    folder = tmp_path / "views" / "v"
    folder.mkdir(parents=True)
    _frame(n).to_csv(folder / "t.csv", index=False)
    return tmp_path / "views"


def test_load_group_reads_the_table_the_audit_chose(tmp_path):
    views = _views(tmp_path)
    entry = bp.audit_groups({"f": {"independent_group": "g", "view": "v"}}, views)["g"]
    table, info = ru.load_group("g", entry, views)
    assert len(table) == 2400
    assert info == {
        "group": "g",
        "view": "v",
        "file": "t.csv",
        "time_column": "when",
        "columns": ["x0", "x1", "x2", "x3"],
    }


def test_load_group_refuses_an_ineligible_group(tmp_path):
    entry = {"eligible": False, "reasons": ["view v is not built locally"]}
    with pytest.raises(ValueError, match="g is not eligible: view v is not built locally"):
        ru.load_group("g", entry, tmp_path)


def test_evaluations_follow_the_protocol_grid():
    assert ru.cells(1, seeds=1) == 2 * 8 * 3
    assert ru.cells(10) == 2 * 5 * 8 * 3 * 10


def test_plan_group_counts_batches_and_detectors_for_either_profile():
    entry = {"table": {"batches": 100, "batch_rows": 24}}
    full = ru.plan_group(entry)
    assert full["batches"] == {"reference": 40, "validation": 20, "test": 40}
    assert full["batch_rows"] == 24
    assert full["evaluations"] == ru.cells(len(pb.DETECTORS) - len(pb.COMPACT))
    compact = ru.plan_group(entry, compact=True)
    assert compact["evaluations"] == ru.cells(len(pb.DETECTORS) - len(pb.LEARNED))


def test_authorization_must_exist_name_the_step_and_cover_every_group(tmp_path):
    with pytest.raises(PermissionError, match="needs --authorization"):
        ru.check_authorization(None, "s", ["g"])
    record = tmp_path / "auth.json"
    record.write_text(json.dumps({"step": "s", "groups": ["g", "h"]}))
    ru.check_authorization(record, "s", ["g", "h"])
    with pytest.raises(PermissionError, match="for step 's', not 't'"):
        ru.check_authorization(record, "t", ["g"])
    with pytest.raises(PermissionError, match=r"\['z'\]"):
        ru.check_authorization(record, "s", ["g", "z"])
    record.write_text(json.dumps({"step": "s"}))
    with pytest.raises(PermissionError, match=r"\['g'\]"):
        ru.check_authorization(record, "s", ["g"])


def _setup(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    facts = {
        "f1": {"independent_group": "g1", "view": "v", "protocol_id": "P-TS"},
        "f2": {"independent_group": "g2", "view": "w", "protocol_id": "P-NEST"},
    }
    (evidence / "readiness_facts.json").write_text(json.dumps({"facts": facts}))
    views = _views(tmp_path)
    audit = bp.audit_groups(facts, views)
    path = tmp_path / "audit.json"
    path.write_text(json.dumps({"groups": audit}))
    return evidence, views, path


def test_cli_compatibility_and_plan_write_deterministic_reports(tmp_path, capsys):
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    assert ru.main(["compatibility", *base]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["g1"][0]["runnable"] and not report["g2"][0]["runnable"]
    assert report["g2"][0]["reason"] == "unsupported: the unit has no approved definition"
    out = tmp_path / "plan.json"
    assert ru.main(["plan", *base, "--output", str(out)]) == 0
    plan = json.loads(out.read_text())
    assert list(plan["groups"]) == ["g1"]  # only eligible groups are planned
    assert plan["totals"] == {"groups": 1, "evaluations": plan["groups"]["g1"]["evaluations"]}
    assert out.read_text() == json.dumps(plan, indent=1, sort_keys=True) + "\n"
    with pytest.raises(SystemExit, match="unknown groups"):
        ru.main(["plan", *base, "--groups", "nope"])


def test_run_refuses_without_authorization_and_never_calls_a_detector(tmp_path, monkeypatch):
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    monkeypatch.setattr(pb, "run_source", lambda *a, **k: pytest.fail("a detector ran"))
    with pytest.raises(PermissionError):
        ru.main(["run", *base, "--step", "s", "--output", str(tmp_path / "o")])
    record = tmp_path / "auth.json"
    record.write_text(json.dumps({"step": "s", "groups": []}))
    with pytest.raises(PermissionError):
        ru.main(["run", *base, "--step", "s", "--authorization", str(record)])


def test_an_authorized_run_writes_one_result_per_group_with_both_arms(tmp_path, monkeypatch):
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    seen = []

    def fake(table, seeds=None, contaminated=False, learned=pb.LEARNED, **_):
        seen.append((len(table), contaminated, learned))
        return {"contaminated": contaminated}

    monkeypatch.setattr(pb, "run_source", fake)
    record = tmp_path / "auth.json"
    record.write_text(json.dumps({"step": "s", "groups": ["g1"]}))
    out = tmp_path / "o"
    argv = ["run", *base, "--step", "s", "--authorization", str(record), "--output", str(out)]
    assert ru.main([*argv, "--compact"]) == 0
    result = json.loads((out / "g1.json").read_text())
    assert result["id"] == "g1" and result["view"] == "v"
    assert result["arms"] == {
        "clean_reference": {"contaminated": False},
        "contaminated_reference": {"contaminated": True},
    }
    assert seen == [(2400, False, pb.COMPACT), (2400, True, pb.COMPACT)]
    result = json.loads((out / "g1.json").read_text())
    assert result["group"] == "g1"
    with pytest.raises(SystemExit, match="^--output is required to run$"):
        ru.main(["run", *base, "--step", "s", "--authorization", str(record)])


def test_the_parser_defaults_choices_and_description():
    parser = ru.build_parser()
    assert parser.description == ru.__doc__
    args = parser.parse_args(["plan"])
    assert vars(args) == {
        "command": "plan",
        "evidence": ru.EVIDENCE,
        "views": bp.VIEWS,
        "audit": ru.EVIDENCE / "batch_eligibility.json",
        "groups": [],
        "step": "",
        "authorization": None,
        "output": None,
        "compact": False,
        "seeds": [42, 1, 2, 3, 4],
    }
    assert ru.EVIDENCE / "batch_eligibility.json" == bp.EVIDENCE / "batch_eligibility.json"
    assert parser.parse_args(["run", "--groups", "a", "b", "--compact"]).groups == ["a", "b"]
    assert parser.parse_args(["run", "--compact"]).compact is True
    with pytest.raises(SystemExit):
        parser.parse_args(["bogus"])


def test_compact_changes_the_planned_evaluations(tmp_path, capsys):
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    ru.main(["plan", *base])
    full = json.loads(capsys.readouterr().out)
    ru.main(["plan", *base, "--compact"])
    compact = json.loads(capsys.readouterr().out)
    assert full["totals"]["evaluations"] == ru.cells(len(pb.DETECTORS) - len(pb.COMPACT))
    assert compact["totals"]["evaluations"] == ru.cells(len(pb.DETECTORS) - len(pb.LEARNED))
    assert capsys.readouterr().out == ""
    ru.main(["plan", *base])
    assert capsys.readouterr().out == json.dumps(full, indent=1, sort_keys=True) + "\n"


def test_a_run_creates_nested_output_announces_each_group_and_may_repeat(
    tmp_path, monkeypatch, capsys
):
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    monkeypatch.setattr(pb, "run_source", lambda table, *a, **k: {"rows": len(table)})
    record = tmp_path / "auth.json"
    record.write_text(json.dumps({"step": "s", "groups": ["g1"]}))
    out = tmp_path / "a" / "b"
    argv = ["run", *base, "--step", "s", "--authorization", str(record), "--output", str(out)]
    assert ru.main(argv) == 0 and ru.main(argv) == 0  # a rerun overwrites, it does not fail
    assert capsys.readouterr().out == "g1\ng1\n"
    text = (out / "g1.json").read_text()
    assert text == json.dumps(json.loads(text), sort_keys=True) + "\n"
    assert list(json.loads(text)) == sorted(json.loads(text))


def test_clean_table_keeps_file_order_among_equal_times_and_drops_repeats_across_times():
    frame = _frame(2400).sort_values("when", kind="stable").reset_index(drop=True)
    frame["when"] = frame["when"].str[:10]  # many rows share one day
    first, _ = ru.clean_table(frame.sample(frac=1.0, random_state=3).reset_index(drop=True))
    shuffled = frame.sample(frac=1.0, random_state=3).reset_index(drop=True)
    expected = shuffled.assign(_t=pd.to_datetime(shuffled["when"])).sort_values("_t", kind="stable")
    assert first["x0"].tolist() == expected["x0"].tolist()  # stable on the file order
    twin = _frame(2400)
    twin.loc[1, ["x0", "x1", "x2", "x3"]] = twin.loc[0, ["x0", "x1", "x2", "x3"]].to_numpy()
    assert len(ru.clean_table(twin)[0]) == 2399  # same values at two different times: one row


def test_clean_table_returns_floats_even_for_integer_columns():
    frame = _frame().assign(count=lambda f: (f["x0"] * 100).astype(int))
    table, info = ru.clean_table(frame)
    assert "count" in info["columns"] and table["count"].dtype == float


def test_error_messages_are_exact():
    with pytest.raises(ValueError, match="^only 3 continuous columns$"):
        ru.clean_table(_frame(columns=3))
    entry = {"eligible": False, "reasons": ["r1", "r2"]}
    with pytest.raises(ValueError, match="^g is not eligible: r1; r2$"):
        ru.load_group("g", entry, Path("."))
    with pytest.raises(
        PermissionError,
        match="^a detector run needs --authorization naming the step and groups$",
    ):
        ru.check_authorization(None, "s", [])


def test_the_full_profile_is_the_default_learned_arm(tmp_path, monkeypatch):
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    seen = []
    monkeypatch.setattr(pb, "run_source", lambda t, s=None, learned=None, **k: seen.append(learned))
    record = tmp_path / "auth.json"
    record.write_text(json.dumps({"step": "s", "groups": ["g1"]}))
    argv = ["run", *base, "--step", "s", "--authorization", str(record), "--output", str(tmp_path)]
    ru.main(argv)
    assert seen == [pb.LEARNED, pb.LEARNED]


def test_seeds_are_passed_to_both_arms(tmp_path, monkeypatch):
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    seen = []
    monkeypatch.setattr(pb, "run_source", lambda t, seeds=None, **k: seen.append(seeds))
    record = tmp_path / "auth.json"
    record.write_text(json.dumps({"step": "s", "groups": ["g1"]}))
    argv = ["run", *base, "--step", "s", "--authorization", str(record), "--output", str(tmp_path)]
    ru.main([*argv, "--seeds", "7", "8"])
    assert seen == [(7, 8), (7, 8)]


def test_a_synthetic_group_runs_end_to_end_through_the_real_harness(tmp_path):
    pytest.importorskip("pyod")
    evidence, views, audit = _setup(tmp_path)
    base = ["--evidence", str(evidence), "--views", str(views), "--audit", str(audit)]
    record = tmp_path / "auth.json"
    record.write_text(json.dumps({"step": "synthetic", "groups": ["g1"]}))
    out = tmp_path / "out"
    argv = ["run", *base, "--step", "synthetic", "--authorization", str(record)]
    assert ru.main([*argv, "--output", str(out), "--compact", "--seeds", "1"]) == 0
    result = json.loads((out / "g1.json").read_text())
    clean, dirty = result["arms"]["clean_reference"], result["arms"]["contaminated_reference"]
    assert clean["protocol"] == pb.PROTOCOL and clean["seeds"] == [1]
    assert not clean["contaminated_reference"] and dirty["contaminated_reference"]
    assert set(clean["results"]["constraint_rules"]) == set(pb.MECHANISMS)
    assert "isolation_forest_compact" in clean["results"]
    assert clean["results"]["constraint_rules"]["partial_load"]["2"]["recall"] > 0.5
