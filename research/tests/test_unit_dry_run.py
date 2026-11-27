"""Structural dry run of the unit-level protocols on synthetic views (#135, #137, #138, #139)."""

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unit_dry_run as udr  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_view(root: Path, name: str, tables: dict[str, pd.DataFrame], relations=()):
    view = root / name
    view.mkdir(parents=True)
    files = {}
    for file, frame in tables.items():
        frame.to_csv(view / file, index=False)
        files[file] = {"rows": len(frame), "sha256": sha(view / file)}
    return view, {"files": files, "relations": list(relations)}


def verdict(protocol, unit, root, name, entry, min_units=10, fact_id=None):
    fact = {"view": name, "min_units": min_units}
    return udr.dry_run(
        "g", "C", protocol, unit, fact_id or name, fact, root, {name: entry}, shared=False
    )


def series(rows=50):
    return pd.DataFrame(
        {"ts": pd.date_range("2024-01-01", periods=rows, freq="h").astype(str), "v": range(rows)}
    )


def test_a_numeric_table_passes_the_row_unit_and_reports_counts_only(tmp_path):
    _, entry = make_view(tmp_path, "t", {"a.csv": pd.DataFrame({"x": range(30), "y": range(30)})})
    result = verdict("P-TAB", "row", tmp_path, "t", entry)
    assert result.ok and result.facts["rows"] == 30 and result.facts["continuous_columns"] == 2
    assert "values" not in json.dumps(result.facts)


def test_a_table_with_too_few_rows_names_the_shortfall(tmp_path):
    _, entry = make_view(tmp_path, "t", {"a.csv": pd.DataFrame({"x": range(3)})})
    result = verdict("P-TAB", "row", tmp_path, "t", entry)
    assert (result.ok, result.code) == (False, "too_few_units") and "3 rows" in result.reason


def test_a_missing_view_is_a_reason_not_an_error(tmp_path):
    result = verdict("P-TAB", "row", tmp_path, "absent", {})
    assert (result.ok, result.code) == (False, "view_missing")


def test_a_file_that_differs_from_the_manifest_digest_is_refused(tmp_path):
    view, entry = make_view(tmp_path, "t", {"a.csv": pd.DataFrame({"x": range(30)})})
    (view / "a.csv").write_text("x\n1\n2\n")
    assert verdict("P-TAB", "row", tmp_path, "t", entry).code == "digest_mismatch"


def test_ground_truth_named_columns_are_withheld_and_never_read(tmp_path):
    frame = pd.DataFrame({"x": range(30), "is_anomaly": [0, 1] * 15, "label": [1] * 30})
    _, entry = make_view(tmp_path, "t", {"a.csv": frame})
    result = verdict("P-TAB", "row", tmp_path, "t", entry)
    assert result.ok and result.facts["withheld_columns"] == ["is_anomaly", "label"]
    assert result.facts["columns"] == 1


def test_a_time_series_needs_a_parseable_axis_and_a_numeric_column(tmp_path):
    _, entry = make_view(tmp_path, "ok", {"a.csv": series()})
    good = verdict("P-TS", "time_window", tmp_path, "ok", entry)
    assert good.ok and good.facts["time_column"] == "ts" and good.facts["time_ordered_in_probe"]
    _, entry = make_view(tmp_path, "flat", {"a.csv": pd.DataFrame({"v": range(50)})})
    assert verdict("P-TS", "time_window", tmp_path, "flat", entry).code == "no_time_axis"
    _, entry = make_view(tmp_path, "novalue", {"a.csv": series().drop(columns=["v"])})
    assert verdict("P-TS", "time_window", tmp_path, "novalue", entry).code == "no_value_column"


def test_an_event_log_needs_an_order_and_an_event_type(tmp_path):
    log = pd.DataFrame(
        {"case": [1, 1, 2, 2] * 5, "pos": range(20), "activity": ["a", "b", "a", "c"] * 5}
    )
    _, entry = make_view(tmp_path, "log", {"e.csv": log})
    good = verdict("P-SEQ", "event_sequence", tmp_path, "log", entry)
    assert good.ok and good.facts["order_column"] == "pos"
    _, entry = make_view(tmp_path, "noorder", {"e.csv": log.drop(columns=["pos", "case"])})
    assert verdict("P-SEQ", "event_sequence", tmp_path, "noorder", entry).code == "no_event_order"
    _, entry = make_view(tmp_path, "notype", {"e.csv": log[["pos"]]})
    assert verdict("P-SEQ", "event_sequence", tmp_path, "notype", entry).code == "no_event_type"


def test_relational_units_follow_declared_keys_whose_columns_exist(tmp_path):
    parent = pd.DataFrame({"id": range(5)})
    child = pd.DataFrame({"pid": [0, 1, 1, 2], "v": range(4)})
    relation = {"child": "child.pid", "parent": "parent.id", "rows_checked": 4, "orphans": 0}
    _, entry = make_view(tmp_path, "r", {"parent.csv": parent, "child.csv": child}, [relation])
    good = verdict("P-REL", "relationship", tmp_path, "r", entry)
    assert good.ok and good.facts == {"tables": 2, "relationships": 1}
    _, entry = make_view(tmp_path, "none", {"parent.csv": parent, "child.csv": child})
    assert verdict("P-REL", "relationship", tmp_path, "none", entry).code == "no_relationship"
    broken = dict(relation, child="child.missing")
    _, entry = make_view(tmp_path, "gone", {"parent.csv": parent, "child.csv": child}, [broken])
    assert verdict("P-REL", "relationship", tmp_path, "gone", entry).code == "no_relationship"


def test_a_flat_view_is_one_table_even_when_a_view_is_named_flat(tmp_path):
    (tmp_path / "flat").mkdir()
    series().to_csv(tmp_path / "flat" / "solo.csv", index=False)
    entry = {"files": {"solo.csv": {"rows": 50, "sha256": sha(tmp_path / "flat" / "solo.csv")}}}
    result = verdict("P-TS", "time_window", tmp_path, "solo", entry)
    assert result.ok and result.facts["table"] == "solo.csv"
    _, entry = make_view(tmp_path, "sub", {"a.csv": series()})
    assert verdict("P-TS", "time_window", tmp_path, "sub", entry).ok


def jsonl_view(root, name, lines):
    view = root / name
    view.mkdir(parents=True)
    path = view / "d.jsonl"
    path.write_text("\n".join(lines) + "\n")
    return {"files": {"d.jsonl": {"rows": len(lines), "sha256": sha(path)}}}


def test_nested_documents_keep_their_paths_and_flat_ones_are_refused(tmp_path):
    entry = jsonl_view(tmp_path, "n", ['{"a": {"b": [{"c": 1}]}, "d": 2}', '{"a": {"b": []}}'])
    good = verdict("P-NEST", "nested_path", tmp_path, "n", entry)
    assert good.ok and good.facts["nested_paths"] == 3 and good.facts["paths"] == 5
    flat = jsonl_view(tmp_path, "f", ['{"a": 1}', '{"a": 2, "b": "x"}'])
    assert verdict("P-NEST", "nested_path", tmp_path, "f", flat).code == "no_nesting"
    bad = jsonl_view(tmp_path, "m", ["not json", "{broken"])
    assert verdict("P-NEST", "nested_path", tmp_path, "m", bad).code == "malformed_document"


def test_a_view_with_the_wrong_file_kind_is_a_no_table_reason(tmp_path):
    entry = jsonl_view(tmp_path, "n", ['{"a": {"b": 1}}'])
    assert verdict("P-TAB", "row", tmp_path, "n", entry).code == "no_table"
    _, entry = make_view(tmp_path, "t", {"a.csv": series()})
    assert verdict("P-NEST", "nested_path", tmp_path, "t", entry).code == "no_table"


def test_an_unknown_protocol_and_an_adapter_fault_are_reported(tmp_path):
    _, entry = make_view(tmp_path, "t", {"a.csv": series()})
    assert verdict("P-XYZ", "row", tmp_path, "t", entry).code == "unsupported_protocol"
    (tmp_path / "t" / "a.csv").write_bytes(b"\xff\xfe\x00bad")
    entry["files"]["a.csv"]["sha256"] = sha(tmp_path / "t" / "a.csv")
    result = verdict("P-TAB", "row", tmp_path, "t", entry)
    assert not result.ok and result.code == "adapter_error"


def test_every_protocol_has_an_adapter_and_no_scientific_run_is_available():
    protocols = {"P-TAB": "row", "P-TS": "time_window", "P-SEQ": "event_sequence"}
    protocols |= {"P-REL": "relationship", "P-NEST": "nested_path"}
    assert set(udr.ADAPTERS) == set(protocols)
    for protocol, unit in protocols.items():
        info = udr.availability(protocol, unit)
        assert info["scientific_execution"] is False and "freeze" in info["reason"]


def test_provisional_units_are_labelled_provisional(tmp_path):
    _, entry = make_view(tmp_path, "t", {"a.csv": series()})
    assert verdict("P-TS", "time_window", tmp_path, "t", entry).unit_status == "protocol_defined"
    assert udr.availability("P-X", "document_batch")["unit_status"] == "provisional"


def test_the_verdict_is_deterministic(tmp_path):
    _, entry = make_view(tmp_path, "t", {"a.csv": series()})
    assert verdict("P-TS", "time_window", tmp_path, "t", entry) == verdict(
        "P-TS", "time_window", tmp_path, "t", entry
    )


def test_the_summary_counts_participations_by_category_and_reason():
    rows = {
        "g1": [{"category": "C1", "ok": True, "code": ""}],
        "g2": [
            {"category": "C1", "ok": False, "code": "no_table"},
            {"category": "C2a", "ok": False, "code": "no_table"},
        ],
    }
    summary = udr.summarise(rows)
    assert summary["by_category"]["C1"] == {"participations": 2, "passed": 1}
    assert summary["failure_codes"] == {"no_table": 2}


def test_the_module_names_no_dataset_or_group():
    text = Path(udr.__file__).read_text()
    registry = json.loads((udr.EVIDENCE / "readiness_facts.json").read_text())["facts"]
    views = {f["view"] for f in registry.values() if len(f["view"]) > 6}
    assert [v for v in sorted(views) if v in text] == []


def facts_of(result):
    assert result.ok, result
    return result.facts


def test_the_tabular_adapter_reports_exact_counts_and_its_boundary(tmp_path):
    frame = pd.DataFrame({"x": range(10), "y": range(10), "kind": list("ab") * 5})
    _, entry = make_view(tmp_path, "t", {"a.csv": frame})
    assert facts_of(verdict("P-TAB", "row", tmp_path, "t", entry, min_units=10)) == {
        "table": "a.csv",
        "rows": 10,
        "columns": 3,
        "continuous_columns": 2,
        "withheld_columns": [],
    }
    bad = verdict("P-TAB", "row", tmp_path, "t", entry, min_units=11)
    assert (bad.code, bad.reason) == ("too_few_units", "10 rows, 11 needed")


def test_a_text_only_table_is_usable_and_a_table_of_withheld_columns_is_not(tmp_path):
    _, entry = make_view(tmp_path, "t", {"a.csv": pd.DataFrame({"kind": list("abcdefghij")})})
    assert facts_of(verdict("P-TAB", "row", tmp_path, "t", entry))["continuous_columns"] == 0
    gt = pd.DataFrame({"label": range(20), "is_anomaly": range(20)})
    _, entry = make_view(tmp_path, "g", {"a.csv": gt})
    result = verdict("P-TAB", "row", tmp_path, "g", entry)
    assert (result.code, result.reason) == ("no_value_column", "no table has a usable column")


def test_the_tabular_adapter_takes_the_first_table_that_is_long_enough(tmp_path):
    short, long = pd.DataFrame({"x": range(3)}), pd.DataFrame({"y": range(20)})
    _, entry = make_view(tmp_path, "t", {"a.csv": short, "b.csv": long})
    assert facts_of(verdict("P-TAB", "row", tmp_path, "t", entry))["table"] == "b.csv"
    _, entry = make_view(tmp_path, "s", {"a.csv": short, "b.csv": short.iloc[:2]})
    assert verdict("P-TAB", "row", tmp_path, "s", entry).reason == "3 rows, 10 needed"


def test_the_time_series_adapter_reports_order_counts_and_reasons(tmp_path):
    frame = series(30)
    _, entry = make_view(tmp_path, "t", {"a.csv": frame})
    entry_t = entry
    assert facts_of(verdict("P-TS", "time_window", tmp_path, "t", entry, min_units=30)) == {
        "table": "a.csv",
        "rows": 30,
        "time_column": "ts",
        "time_ordered_in_probe": True,
        "numeric_columns": 1,
        "withheld_columns": [],
    }
    back = frame.iloc[::-1]
    _, entry = make_view(tmp_path, "r", {"a.csv": back})
    assert (
        facts_of(verdict("P-TS", "time_window", tmp_path, "r", entry))["time_ordered_in_probe"]
        is False
    )
    short = verdict("P-TS", "time_window", tmp_path, "t", entry_t, min_units=99)
    assert (short.code, short.reason) == ("too_few_units", "30 rows, 99 needed")
    _, entry = make_view(tmp_path, "m", {"a.csv": frame.drop(columns=["v"]), "b.csv": frame})
    assert facts_of(verdict("P-TS", "time_window", tmp_path, "m", entry))["table"] == "b.csv"
    _, entry = make_view(tmp_path, "n", {"a.csv": frame[["v"]]})
    assert verdict("P-TS", "time_window", tmp_path, "n", entry).reason == (
        "a.csv has no parseable instant column; " + udr.NUMERIC_AXIS
    )


def test_the_sequence_adapter_picks_the_order_and_counts_event_type_candidates(tmp_path):
    log = pd.DataFrame(
        {
            "pos": range(40),
            "when": pd.date_range("2024-01-01", periods=40, freq="min").astype(str),
            "activity": ["a", "b", "c", "d"] * 10,
            "constant": ["x"] * 40,
            "score": [0.5] * 40,
        }
    )
    _, entry = make_view(tmp_path, "l", {"e.csv": log})
    entry_l = entry
    assert facts_of(verdict("P-SEQ", "event_sequence", tmp_path, "l", entry, min_units=40)) == {
        "table": "e.csv",
        "events": 40,
        "order_column": "when",
        "event_type_candidates": 1,
        "withheld_columns": [],
    }
    no_time = log.drop(columns=["when"])
    _, entry = make_view(tmp_path, "o", {"e.csv": no_time})
    assert (
        facts_of(verdict("P-SEQ", "event_sequence", tmp_path, "o", entry))["order_column"] == "pos"
    )
    shuffled = no_time.assign(pos=[1, 0] + list(range(2, 40)))
    _, entry = make_view(tmp_path, "s", {"e.csv": shuffled})
    assert verdict("P-SEQ", "event_sequence", tmp_path, "s", entry).code == "no_event_order"
    _, entry = make_view(tmp_path, "c", {"e.csv": log[["pos", "when", "constant", "score"]]})
    assert verdict("P-SEQ", "event_sequence", tmp_path, "c", entry).reason == (
        "e.csv has no event-type column"
    )
    short = verdict("P-SEQ", "event_sequence", tmp_path, "l", entry_l, min_units=41)
    assert (short.code, short.reason) == ("too_few_units", "40 rows, 41 needed")


def test_the_sequence_adapter_applies_the_unit_floor_and_the_alphabet_bound(tmp_path):
    log = pd.DataFrame({"pos": range(30), "activity": ["a", "b"] * 15})
    _, entry = make_view(tmp_path, "l", {"e.csv": log})
    short = verdict("P-SEQ", "event_sequence", tmp_path, "l", entry, min_units=31)
    assert (short.code, short.reason) == ("too_few_units", "30 rows, 31 needed")
    wide = pd.DataFrame({"pos": range(200), "activity": [f"a{i}" for i in range(200)]})
    _, entry = make_view(tmp_path, "w", {"e.csv": wide})
    assert verdict("P-SEQ", "event_sequence", tmp_path, "w", entry).code == "no_event_type"


def test_paths_of_lists_objects_arrays_and_scalar_arrays():
    assert udr.paths_of({"a": {"b": [{"c": 1}]}, "d": [1, 2], "e": 3}) == {
        "a",
        "a.b",
        "a.b[]",
        "a.b[].c",
        "d",
        "d[]",
        "e",
    }
    assert udr.paths_of([[1]]) == {"[]", "[][]"}
    assert udr.paths_of("x") == set() and udr.paths_of({}) == set()


def test_the_nested_adapter_counts_probed_documents_and_stops_at_the_probe(tmp_path, monkeypatch):
    lines = ['{"a": [1, 2]}', "oops", '{"a": [3], "b": {"c": 1}}'] * 5
    entry = jsonl_view(tmp_path, "n", lines)
    assert facts_of(verdict("P-NEST", "nested_path", tmp_path, "n", entry)) == {
        "file": "d.jsonl",
        "documents_probed": 10,
        "malformed_probed": 5,
        "paths": 4,
        "nested_paths": 2,
    }
    monkeypatch.setattr(udr, "PROBE", 4)
    got = facts_of(verdict("P-NEST", "nested_path", tmp_path, "n", entry))
    assert got["documents_probed"] + got["malformed_probed"] == 4
    only_arrays = jsonl_view(tmp_path, "arr", ['{"a": [1]}'])
    assert (
        facts_of(verdict("P-NEST", "nested_path", tmp_path, "arr", only_arrays))["nested_paths"]
        == 1
    )
    no_doc = verdict("P-NEST", "nested_path", tmp_path, "t", {})
    assert no_doc.code == "view_missing"


def test_reasons_of_the_relational_adapter_are_exact(tmp_path):
    parent, child = pd.DataFrame({"id": range(3)}), pd.DataFrame({"pid": range(3)})
    _, entry = make_view(tmp_path, "a", {"p.csv": parent, "c.csv": child})
    assert verdict("P-REL", "relationship", tmp_path, "a", entry).reason == (
        "the view manifest declares no foreign key"
    )
    relation = {"child": "c.pid", "parent": "p.id", "rows_checked": 3, "orphans": 0}
    _, entry = make_view(tmp_path, "b", {"p.csv": parent}, [relation])
    assert verdict("P-REL", "relationship", tmp_path, "b", entry).reason == (
        "no declared foreign key has its tables and columns in the view"
    )
    _, entry = make_view(tmp_path, "d", {"p.csv": parent, "c.csv": child}, [relation])
    assert facts_of(verdict("P-REL", "relationship", tmp_path, "d", entry)) == {
        "tables": 2,
        "relationships": 1,
    }
    bad_parent = dict(relation, parent="p.nope")
    _, entry = make_view(tmp_path, "e", {"p.csv": parent, "c.csv": child}, [bad_parent])
    assert verdict("P-REL", "relationship", tmp_path, "e", entry).code == "no_relationship"


def test_a_relational_fact_with_a_subset_reads_only_that_folder(tmp_path):
    root = tmp_path / "v"
    for site in ("one", "two"):
        (root / site).mkdir(parents=True)
        pd.DataFrame({"id": [1]}).to_csv(root / site / "T.csv", index=False)
    (root / "top.csv").write_text("a\n1\n")
    names = lambda ps: sorted(p.relative_to(root).as_posix() for p in ps)  # noqa: E731
    pick = udr.select_paths
    assert names(pick("P-REL", "v:one", "v", root, False, False)) == ["one/T.csv"]
    assert names(pick("P-REL", "v:none", "v", root, False, False)) == [
        "one/T.csv",
        "top.csv",
        "two/T.csv",
    ]
    assert names(pick("P-REL", "v", "v", root, False, False)) == [
        "one/T.csv",
        "top.csv",
        "two/T.csv",
    ]
    (root / "d.jsonl").write_text("{}\n")
    assert names(pick("P-NEST", "v:nested", "v", root, False, False)) == ["d.jsonl"]
    assert names(pick("P-TAB", "v", "v", root, False, False)) == ["top.csv"]


def test_a_shared_view_gives_a_fact_its_own_table_or_falls_back_to_the_view(tmp_path):
    root = tmp_path / "v"
    root.mkdir()
    for name in ("alpha", "beta"):
        pd.DataFrame({"x": [1]}).to_csv(root / f"{name}.csv", index=False)
    pick = udr.select_paths
    assert [p.name for p in pick("P-TAB", "v_alpha", "v", root, True, False)] == ["alpha.csv"]
    assert [p.name for p in pick("P-TAB", "v:derived", "v", root, True, False)] == [
        "alpha.csv",
        "beta.csv",
    ]
    assert [p.name for p in pick("P-TAB", "v_alpha", "v", root, False, False)] == [
        "alpha.csv",
        "beta.csv",
    ]


def test_integrity_checks_use_the_path_in_the_view_and_skip_unrecorded_files(tmp_path):
    root = tmp_path / "v"
    (root / "sub").mkdir(parents=True)
    path = root / "sub" / "a.csv"
    path.write_text("x\n1\n")
    entry = {"files": {"sub/a.csv": {"sha256": udr.digest(path)}}}
    udr.check_files([path], entry, root)
    udr.check_files([path], {}, root)
    udr.check_files([path], {"files": {"sub/a.csv": {}}}, root)
    with pytest.raises(udr.Failure) as raised:
        udr.check_files([path], {"files": {"sub/a.csv": {"sha256": "0" * 64}}}, root)
    assert (raised.value.code, raised.value.reason) == (
        "digest_mismatch",
        "sub/a.csv differs from the manifest digest",
    )
    assert udr.digest(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_probe_is_bounded_and_withholds_ground_truth_columns(tmp_path, monkeypatch):
    path = tmp_path / "a.csv"
    pd.DataFrame({"x": range(20), "ground_truth": range(20), "y": range(20)}).to_csv(
        path, index=False
    )
    monkeypatch.setattr(udr, "PROBE", 7)
    frame, withheld = udr.probe(path)
    assert list(frame.columns) == ["x", "y"] and len(frame) == 7
    assert withheld == ["ground_truth"]
    assert udr.allowed_columns(path) == ["x", "y"]


def test_the_failure_and_the_verdict_carry_their_reason_and_unit_status(tmp_path):
    error = udr.Failure("no_table", "none")
    assert (error.code, error.reason, str(error)) == ("no_table", "none", "none")
    result = verdict("P-TAB", "row", tmp_path, "absent", {})
    assert result == udr.Verdict(
        group="g",
        category="C",
        protocol="P-TAB",
        unit="row",
        unit_status="protocol_defined",
        ok=False,
        code="view_missing",
        reason="view absent is not built locally",
        facts={},
    )
    assert udr.availability("P-X", "row") == {
        "protocol": "P-X",
        "unit": "row",
        "unit_status": "protocol_defined",
        "scientific_execution": False,
        "reason": udr.FREEZE_REASON,
    }
    assert set(udr.CODES) >= {"view_missing", "digest_mismatch", "adapter_error"}


def test_the_manifest_row_count_defaults_to_zero_and_files_without_a_table_are_refused(tmp_path):
    path = tmp_path / "a.csv"
    assert udr.rows_of({"files": {"a.csv": {"rows": 7}}}, path) == 7
    assert udr.rows_of({}, path) == 0 and udr.rows_of({"files": {"a.csv": {}}}, path) == 0
    with pytest.raises(udr.Failure) as raised:
        udr.csv_tables([tmp_path / "a.json"])
    assert raised.value.reason == "the view holds no CSV table"
    assert udr.csv_tables([path, tmp_path / "b.json"]) == [path]


def test_an_adapter_fault_is_reported_with_its_type_and_a_bounded_message(tmp_path, monkeypatch):
    def broken(paths, entry, fact, views):
        raise RuntimeError("x" * 500)

    monkeypatch.setitem(udr.ADAPTERS, "P-TAB", broken)
    _, entry = make_view(tmp_path, "t", {"a.csv": series()})
    result = verdict("P-TAB", "row", tmp_path, "t", entry)
    assert result.ok is False and result.code == "adapter_error"
    assert result.reason == "RuntimeError: " + "x" * 286 and len(result.reason) == 300
    unknown = verdict("P-XYZ", "row", tmp_path, "t", entry)
    assert (unknown.ok, unknown.reason) == (False, "no adapter for P-XYZ")


def test_the_access_record_states_that_no_value_is_returned_and_the_ledger_is_untouched():
    record = udr.access_record()
    assert set(record) == {"operations", "returned", "withheld", "not_done", "ledger_effect"}
    assert len(record["operations"]) == 3
    assert record["returned"].endswith("never a cell value")
    assert record["withheld"].startswith("columns whose name belongs to the ground-truth")
    assert record["not_done"].startswith("no detector fit or inference")
    assert record["ledger_effect"].startswith("none")
    assert [str(udr.PROBE) in operation for operation in record["operations"]] == [
        False,
        True,
        True,
    ]


def synthetic_registry(tmp_path):
    """Two groups: one in two categories under two protocols, one with a failing and a good fact."""
    views = tmp_path / "views"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    log = pd.DataFrame({"pos": range(20), "activity": ["a", "b"] * 10})
    manifest = {}
    for name, frame in (("tab", series(20)), ("log", log), ("good", series(20))):
        manifest[name] = make_view(views, name, {"x.csv": frame})[1]
    manifest["bad"] = make_view(views, "bad", {"x.csv": pd.DataFrame({"v": range(20)})})[1]
    facts = {
        "tab": {"independent_group": "g1", "protocol_id": "P-TS", "view": "tab", "min_units": 5},
        "log": {"independent_group": "g1", "protocol_id": "P-SEQ", "view": "log", "min_units": 5},
        "g2_bad": {"independent_group": "g2", "protocol_id": "P-TS", "view": "bad", "min_units": 5},
        "g2_good": {
            "independent_group": "g2",
            "protocol_id": "P-TS",
            "view": "good",
            "min_units": 5,
        },
    }
    registry = {
        "datasets": [
            {"id": "tab", "stratum": "C3"},
            {"id": "log", "stratum": "C4"},
            {"id": "g2_bad", "stratum": "C3"},
            {"id": "g2_good", "stratum": "C3"},
        ],
        "ready_groups": {"C3": ["g1", "g2"], "C4": ["g1"]},
    }
    protocols = {"protocols": {"P-TS": {"detection_unit": "time_window"}}}
    protocols["protocols"]["P-SEQ"] = {"detection_unit": "event_sequence"}
    for file, content in (
        ("readiness_facts.json", {"facts": facts}),
        ("readiness.json", registry),
        ("experimental_views.json", manifest),
        ("anomaly_protocols.json", protocols),
    ):
        (evidence / file).write_text(json.dumps(content))
    return evidence, views


def test_a_run_dispatches_every_participation_by_its_own_protocol(tmp_path):
    evidence, views = synthetic_registry(tmp_path)
    report = udr.run(evidence, views)
    g1 = {row["category"]: row for row in report["groups"]["g1"]}
    assert (g1["C3"]["protocol"], g1["C3"]["unit"]) == ("P-TS", "time_window")
    assert (g1["C4"]["protocol"], g1["C4"]["unit"]) == ("P-SEQ", "event_sequence")
    assert g1["C3"]["ok"] and g1["C4"]["ok"]
    (g2,) = report["groups"]["g2"]
    assert g2["ok"] and g2["facts"]["time_column"] == "ts"
    assert report["summary"]["by_category"] == {
        "C3": {"participations": 2, "passed": 2},
        "C4": {"participations": 1, "passed": 1},
    }
    assert set(report["availability"]) == {"P-TS", "P-SEQ"}
    assert report["access"] == udr.access_record()


def test_a_group_with_only_failing_facts_reports_the_first_reason(tmp_path):
    evidence, views = synthetic_registry(tmp_path)
    facts = json.loads((evidence / "readiness_facts.json").read_text())
    del facts["facts"]["g2_good"]
    (evidence / "readiness_facts.json").write_text(json.dumps(facts))
    (g2,) = udr.run(evidence, views)["groups"]["g2"]
    assert (g2["ok"], g2["code"]) == (False, "no_time_axis")
    assert udr.run(evidence, views)["summary"]["failure_codes"] == {"no_time_axis": 1}


def test_the_command_line_writes_the_report_or_prints_it(tmp_path, capsys):
    evidence, views = synthetic_registry(tmp_path)
    target = tmp_path / "out.json"
    argv = ["--evidence", str(evidence), "--views", str(views)]
    assert udr.main([*argv, "--output", str(target)]) == 0
    written = json.loads(target.read_text())
    assert udr.main(argv) == 0
    printed = capsys.readouterr().out
    assert json.loads(printed) == written
    assert printed == json.dumps(written, indent=1, sort_keys=True) + "\n" == target.read_text()
    defaults = udr.build_parser().parse_args([])
    assert (defaults.evidence, defaults.views, defaults.output) == (
        udr.EVIDENCE,
        udr.bp.VIEWS,
        None,
    )
    assert isinstance(udr.build_parser().parse_args(["--views", "x"]).views, Path)
    assert udr.build_parser().description == udr.__doc__


def test_a_shared_view_gives_each_fact_of_a_run_its_own_table(tmp_path):
    evidence, views = synthetic_registry(tmp_path)
    shared = views / "shared"
    shared.mkdir()
    for name, frame in (("fa", series(20)), ("fb", series(20).drop(columns=["v"]))):
        frame.to_csv(shared / f"{name}.csv", index=False)
    manifest = json.loads((evidence / "experimental_views.json").read_text())
    manifest["shared"] = {"files": {"fa.csv": {"rows": 20}, "fb.csv": {"rows": 20}}}
    (evidence / "experimental_views.json").write_text(json.dumps(manifest))
    facts = json.loads((evidence / "readiness_facts.json").read_text())
    for fid, group in (("fa", "g3"), ("fb", "g4")):
        facts["facts"][fid] = {
            "independent_group": group,
            "protocol_id": "P-TS",
            "view": "shared",
            "min_units": 5,
        }
    (evidence / "readiness_facts.json").write_text(json.dumps(facts))
    registry = json.loads((evidence / "readiness.json").read_text())
    registry["datasets"] += [{"id": "fa", "stratum": "C3"}, {"id": "fb", "stratum": "C3"}]
    registry["ready_groups"]["C3"] += ["g3", "g4"]
    (evidence / "readiness.json").write_text(json.dumps(registry))
    report = udr.run(evidence, views)["groups"]
    (own,), (other,) = report["g3"], report["g4"]
    assert own["ok"] and own["group"] == "g3" and own["facts"]["table"] == "fa.csv"
    assert (other["ok"], other["code"], other["group"]) == (False, "no_value_column", "g4")
