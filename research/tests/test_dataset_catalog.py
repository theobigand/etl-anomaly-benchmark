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
