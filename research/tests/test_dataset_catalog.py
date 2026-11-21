"""The logical catalog: identities, duplicate representations, independent sources, checksums."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coverage_matrix as cm  # noqa: E402
import dataset_catalog as dc  # noqa: E402


def test_the_committed_catalog_is_consistent_with_the_pool_manifest():
    assert dc.problems() == []


def test_historical_files_resolve_to_the_pool_sources_they_duplicate():
    by_id = {e["id"]: e for e in dc.legacy_entries()}
    assert by_id["legacy:cardio"]["source_identity"] == dc.source_key("adbench:cardio") == "uci:193"
    assert by_id["legacy:credit_card"]["source_identity"] == dc.source_key("adbench:fraud")
    # the ADBench twin of the UCI table shares the source, so the file adds nothing
    assert dc.source_key("adbench:cardio") == dc.source_key("adbench:Cardiotocography")


def test_duplicates_and_synthetic_data_add_no_independent_source_but_water_does():
    pool = {dc.source_key("adbench:cardio"), "adbench:fraud"}
    counts = dc.independent_source_count(pool)
    assert counts == {"pool": 2, "added_by_supplementary": 1}


def _catalog(tmp_path, **override):
    entry = {
        "id": "legacy:x", "role": "duplicate_representation", "same_as": "adbench:cardio",
        "source_identity": "uci:193", "path": "data/x.csv", "sha256": dc.sha256(_file(tmp_path)),
    }  # fmt: skip
    entry.update(override)
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps({"roles": json.loads(dc.CATALOG.read_text())["roles"], "entries": [entry]})
    )
    return path


def _file(tmp_path):
    target = tmp_path / "data" / "x.csv"
    target.parent.mkdir(exist_ok=True)
    target.write_text("a,b\n1,2\n")
    return target


def test_a_wrong_source_identity_a_missing_target_and_a_reused_identity_are_reported(tmp_path):
    assert dc.problems(_catalog(tmp_path)) == []
    assert "differs" in dc.problems(_catalog(tmp_path, source_identity="uci:1"))[0]
    assert "not in the pool" in dc.problems(_catalog(tmp_path, same_as="adbench:nope"))[0]
    assert "not unique" in dc.problems(_catalog(tmp_path, id="adbench:cardio"))[0]
    assert "unknown role" in dc.problems(_catalog(tmp_path, role="mystery"))[0]
    bad = _catalog(tmp_path, role="supplementary")
    assert "only a duplicate" in dc.problems(bad)[0]


def test_file_checks_distinguish_ok_missing_and_changed(tmp_path):
    catalog = _catalog(tmp_path)
    assert dc.check_files(tmp_path, catalog) == {"legacy:x": "ok"}
    (tmp_path / "data" / "x.csv").write_text("changed")
    assert dc.check_files(tmp_path, catalog) == {"legacy:x": "checksum differs"}
    (tmp_path / "data" / "x.csv").unlink()
    assert dc.check_files(tmp_path, catalog) == {"legacy:x": "missing"}


@pytest.mark.skipif(not (dc.ROOT / "data" / "cardio.csv").exists(), reason="local data not present")
def test_the_local_historical_files_match_their_recorded_checksums():
    assert set(dc.check_files().values()) == {"ok"}


def test_coverage_lists_the_outside_entries_without_changing_the_active_count(tmp_path):
    results = tmp_path / "natural_temporal" / "results"
    results.mkdir(parents=True)
    done = {"id": "a/1", "group": "g1", "chronological": {"zscore": {}, "iqr": {}}}
    (results / "a.json").write_text(json.dumps(done))
    (results / "b.json").write_text(
        json.dumps({"id": "a/2", "group": "g1", "excluded": "0 anomalies"})
    )
    block = cm.supplementary(tmp_path, dc.CATALOG, {"uci:193"})
    assert [a["id"] for a in block["aliases"]] == ["legacy:cardio", "legacy:credit_card"]
    assert block["independent_sources"] == {"pool": 1, "added_by_supplementary": 1}
    assert block["natural_temporal"] == {
        "series_catalogued": 2, "evaluated": 1, "excluded": 1, "source_groups": {"g1": ["a/1"]},
        "exclusion_reasons": {"0 anomalies": 1}, "detectors": 2,
    }  # fmt: skip
    assert cm.supplementary(tmp_path / "none", None, set()) == {}


def test_strata_follow_time_then_categorical_then_flat_and_never_infer_logs_or_relational():
    assert dc.stratum_of({"time_verified": True, "schema_kind": "categorical"}) == "C3"
    assert dc.stratum_of({"schema_kind": "mixed"}) == "C2"
    assert dc.stratum_of({"tags": ["transactional"]}) == "C2"
    assert dc.stratum_of({"schema_kind": "numeric"}) == "C1"
    assert dc.stratum_of({"schema_kind": "numeric", "stratum": "C5"}) == "C5"


def test_the_gap_report_counts_each_source_family_once_and_reports_what_is_missing():
    rows = [
        {"source": "a", "schema_kind": "numeric"},
        {"source": "a", "schema_kind": "numeric"},  # twin: same source, counted once
        {"source": "b", "schema_kind": "mixed"},
        {"source": "c", "time_verified": True},
        {"source": "d", "time_candidate": True, "tags": ["time_series"]},
    ]
    report = dc.gap_report(rows)
    # "d" has only a time-column candidate: until verified it is not C3 and falls to C1
    assert report["strata"]["C1"]["sources"] == 2
    assert report["strata"]["C2"]["sources"] == 1
    assert report["strata"]["C3"]["sources"] == 1
    assert report["strata"]["C4"]["sources"] == 0
    assert report["strata"]["C4"]["missing_to_recommended"] == 28
    assert report["strata"]["C1"]["missing_to_minimum"] == 13
    assert report["time_candidates_not_yet_verified"] == ["d"]
    assert report["total_sources"] == 4
    assert "C4 logs and event sequences | 0 |" in dc.render_gap(report)


def test_the_rows_read_the_three_evidence_sources_and_skip_retired_tables(tmp_path):
    import json

    def cell(status):
        return {"status": status}

    matrix = {
        "datasets": [
            {
                "id": "uci:1", "independent_source": "uci:1", "schema_kind": "numeric",
                "decision": "retained",
                "protocols": {"chronological": cell("executed"),
                              "chronological_injected_classical": cell("not_evaluated")},
            },
            {
                "id": "uci:2", "independent_source": "uci:2", "schema_kind": "numeric",
                "decision": "retired",
                "protocols": {"chronological": cell("executed"),
                              "chronological_injected_classical": cell("executed")},
            },
        ]
    }  # fmt: skip
    (tmp_path / "m.json").write_text(json.dumps(matrix))
    (tmp_path / "w.json").write_text(
        json.dumps({"tables": [{"uci_id": 9, "tags": ["sequential"], "time_candidates": ["t"]}]})
    )
    nat = tmp_path / "nat"
    nat.mkdir()
    (nat / "a.json").write_text(json.dumps({"id": "x/1", "group": "g", "chronological": {}}))
    (nat / "b.json").write_text(json.dumps({"id": "x/2", "group": "g", "excluded": "none"}))
    (tmp_path / "t.json").write_text(json.dumps({"uci:9": {"verified": True}}))
    rows = dc.stratum_rows(tmp_path / "m.json", tmp_path / "w.json", nat, tmp_path / "t.json")
    assert [r["id"] for r in rows] == ["uci:1", "uci:9", "x/1"]
    assert (
        rows[0]["time_verified"] and rows[1]["time_candidate"] and rows[2]["source"] == "natural:g"
    )


def test_licence_classified_manifests_become_explicit_stratum_rows_and_a_class_breakdown(tmp_path):
    import json

    manifest = {
        "licence_class": "research_only",
        "tables": [
            {"id": "loghub:Apache", "system": "Apache"},
            {"id": "loghub:HDFS", "system": "HDFS"},
        ],
    }
    path = tmp_path / "loghub.json"
    path.write_text(json.dumps(manifest))
    rows = dc.licence_rows([(path, "C4")])
    assert [(r["id"], r["stratum"], r["licence_class"]) for r in rows] == [
        ("loghub:Apache", "C4", "research_only"),
        ("loghub:HDFS", "C4", "research_only"),
    ]
    assert rows[0]["source"] == "loghub:Apache" and dc.stratum_of(rows[0]) == "C4"
    report = dc.gap_report([*rows, {"id": "u", "source": "u", "schema_kind": "numeric"}])
    assert report["strata"]["C4"]["sources"] == 2
    assert report["licence_classes"] == {"open": 1, "research_only": 2}


def test_acquired_entries_count_only_when_eligible_with_three_independence_levels(
    tmp_path,
):
    import json

    entries = {
        "entries": [
            {"id": "a:1", "family": "fa", "system": "s1", "publisher": "p", "stratum": "C5",
             "licence_class": "open", "eligible": True},
            {"id": "a:2", "family": "fa", "system": "s2", "publisher": "p", "stratum": "C5",
             "licence_class": "open", "eligible": True},
            {"id": "b:1", "family": "fb", "system": "s3", "publisher": "q", "stratum": "C3",
             "licence_class": "open", "eligible": False, "reason": "simulated"},
        ]
    }  # fmt: skip
    path = tmp_path / "acq.json"
    path.write_text(json.dumps(entries))
    rows = dc.acquired_rows(path)
    assert [r["id"] for r in rows] == ["a:1", "a:2"]  # the ineligible entry adds nothing
    assert rows[0]["source"] == "fa" and rows[0]["stratum"] == "C5"
    report = dc.gap_report(rows)
    c5 = report["strata"]["C5"]
    assert (c5["sources"], c5["systems"], c5["publishers"]) == (1, 2, 1)
    assert dc.acquired_rows(tmp_path / "none.json") == []


def test_transactional_needs_a_repeated_entity_key_and_an_event_signal_not_just_categories():
    import pandas as pd

    n = 60
    retail = pd.DataFrame(
        {
            "InvoiceNo": [i // 2 for i in range(n)],
            "CustomerID": [i // 3 for i in range(n)],
            "Quantity": range(n),
            "Country": ["a", "b"] * (n // 2),
        }
    )
    sig = dc.transactional_signals(retail)
    assert sig["keys"] == ["CustomerID", "InvoiceNo"] and sig["event_columns"] == ["Quantity"]
    assert dc.is_transactional(sig)
    toy = pd.DataFrame({"colour": list("abcab") * 12, "shape": list("xyzxy") * 12})
    assert not dc.is_transactional(dc.transactional_signals(toy))
    row_ids = pd.DataFrame({"id": range(n), "amount": range(n)})
    assert dc.transactional_signals(row_ids)["keys"] == []  # an id that never repeats is a row id
    few = pd.DataFrame({"user": [1, 1, 2, 2] * 5, "amount": range(20)})
    assert dc.transactional_signals(few)["keys"] == []  # two entities are a category, not a key
    measure = pd.DataFrame({"customer_value": [0.5, 0.5] * 30, "amount": range(n)})
    assert dc.transactional_signals(measure)["keys"] == []  # a float is a measure, not a key
    timed = pd.DataFrame({"user": [i // 2 for i in range(n)], "when": range(n)})
    assert dc.is_transactional(dc.transactional_signals(timed, time_columns=["when"]))
    assert dc.transactional_signals(timed)["event_columns"] == []


def test_the_audit_splits_c2_and_leaves_unreadable_tables_unassigned():
    import pandas as pd

    tables = {
        "uci:1": pd.DataFrame({"customer": [i // 2 for i in range(60)], "amount": range(60)}),
        "uci:2": pd.DataFrame({"colour": list("abca"), "shape": list("xyzx")}),
    }
    rows = [
        {"id": "uci:1", "source": "uci:1", "schema_kind": "mixed"},
        {"id": "uci:2", "source": "uci:2", "schema_kind": "categorical"},
        {"id": "uci:3", "source": "uci:3", "schema_kind": "mixed"},
        {"id": "uci:4", "source": "uci:4", "schema_kind": "numeric"},
    ]
    audit = dc.transactional_audit(rows, lambda r: tables.get(r["id"]))
    assert list(audit["transactional"]) == ["uci:1"]
    assert list(audit["not_transactional"]) == ["uci:2"]
    assert audit["not_audited"] == ["uci:3", "uci:4"]
    assert audit["numeric_arrays_without_schema"] == []
    assert audit["counts"]["not_audited"] == 2 and audit["counts"]["transactional"] == 1


def test_adbench_arrays_are_recorded_as_numeric_without_schema_not_as_unaudited():
    rows = [{"id": "adbench:cardio", "source": "uci:193", "schema_kind": "numeric"}]
    audit = dc.transactional_audit(rows, lambda r: None)
    assert audit["numeric_arrays_without_schema"] == ["adbench:cardio"]
    assert audit["not_audited"] == [] and audit["counts"]["numeric_arrays_without_schema"] == 1
