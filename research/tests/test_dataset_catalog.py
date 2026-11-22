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


def test_c2b_is_a_stratum_and_audited_transactional_tables_are_its_rows(tmp_path):
    import json

    assert "C2b" in dc.STRATA and "C2b" in dc.TARGETS
    path = tmp_path / "audit.json"
    path.write_text(json.dumps({"transactional": {"uci:352": {"keys": ["k"]}}}))
    rows = dc.transactional_rows(path)
    assert rows == [{"id": "uci:352", "source": "uci:352", "stratum": "C2b", "origin": "audit"}]
    assert dc.transactional_rows(tmp_path / "none.json") == []
    report = dc.gap_report(rows)
    assert report["strata"]["C2b"]["sources"] == 1


# --- exact contracts of every function ----------------------------------------------------------


def test_the_strata_and_targets_are_the_documented_ones():
    assert dc.STRATA == {
        "C1": "flat tabular",
        "C2": "transactional and categorical (historical)",
        "C2a": "categorical and mixed tables",
        "C2b": "transactional events",
        "C3": "time series",
        "C4": "logs and event sequences",
        "C5": "relational",
        "C6": "nested",
    }
    assert dc.TARGETS == {
        "C1": (15, 36, 50),
        "C2": (15, 30, 45),
        "C2a": (15, 30, 45),
        "C2b": (15, 30, 45),
        "C3": (15, 40, 55),
        "C4": (15, 28, 40),
        "C5": (15, 36, 55),
        "C6": (15, 30, 45),
    }
    assert set(dc.TARGETS) == set(dc.STRATA)
    assert dc.NOT_INDEPENDENT == ("synthetic", "duplicate_representation")
    assert (dc.MIN_KEY_ENTITIES, dc.MIN_REPEATED_ROWS) == (20, 0.2)


def test_sha256_reads_in_blocks_and_matches_hashlib(tmp_path):
    import hashlib

    empty = tmp_path / "e"
    empty.write_bytes(b"")
    assert dc.sha256(empty) == hashlib.sha256(b"").hexdigest()
    small = tmp_path / "s"
    small.write_bytes(b"abc")
    assert dc.sha256(small) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    big = tmp_path / "b"
    payload = bytes(range(256)) * 10_000 + b"tail"  # more than one 1 MiB block
    payload = payload * 1 + payload
    big.write_bytes(payload)
    assert dc.sha256(big) == hashlib.sha256(payload).hexdigest()
    assert len(payload) > (1 << 20)


def test_source_keys_map_adbench_twins_and_keep_everything_else():
    assert dc.source_key("adbench:cardio") == "uci:193"
    assert dc.source_key("adbench:nonexistent-table") == "adbench:nonexistent-table"
    assert dc.source_key("uci:5") == "uci:5"
    assert dc.source_key("natural:g") == "natural:g"
    assert dc.source_key("plain") == "plain"
    assert dc.source_key("uci:cardio") == "uci:cardio"  # only the adbench prefix is a twin


def test_catalog_problems_have_exact_messages_in_order(tmp_path):
    import json

    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps([{"id": "adbench:cardio"}, {"id": "uci:9"}]))
    catalog = tmp_path / "c.json"
    entries = [
        {"id": "legacy:a", "role": "mystery", "source_identity": "x"},
        {"id": "legacy:a", "role": "supplementary", "source_identity": "x", "same_as": "uci:9"},
        {"id": "uci:9", "role": "supplementary", "source_identity": "uci:9"},
        {
            "id": "legacy:d",
            "role": "duplicate_representation",
            "same_as": "nowhere",
            "source_identity": "y",
        },
        {
            "id": "legacy:e",
            "role": "duplicate_representation",
            "same_as": "adbench:cardio",
            "source_identity": "z",
        },
    ]
    catalog.write_text(
        json.dumps({"roles": ["supplementary", "duplicate_representation"], "entries": entries})
    )
    assert dc.problems(catalog, pool) == [
        "legacy:a: unknown role mystery",
        "legacy:a: identity is not unique",
        "legacy:a: only a duplicate representation may name same_as",
        "uci:9: identity is not unique",
        "legacy:d: same_as nowhere is not in the pool",
        "legacy:e: source identity differs from that of adbench:cardio",
    ]


def test_independent_source_counting_ignores_duplicates_synthetic_and_pool_sources(tmp_path):
    import json

    catalog = tmp_path / "c.json"
    entries = [
        {"id": "a", "role": "supplementary", "source_identity": "new1"},
        {"id": "b", "role": "supplementary", "source_identity": "new1"},  # the same source twice
        {"id": "c", "role": "supplementary", "source_identity": "in-pool"},
        {"id": "d", "role": "synthetic", "source_identity": "synth"},
        {"id": "e", "role": "duplicate_representation", "source_identity": "dup", "same_as": "x"},
    ]
    catalog.write_text(json.dumps({"roles": [], "entries": entries}))
    assert dc.independent_source_count({"in-pool", "other"}, catalog) == {
        "pool": 2,
        "added_by_supplementary": 1,
    }
    assert dc.resolve({"path": "data/x.csv"}, tmp_path) == tmp_path / "data" / "x.csv"


def test_a_stratum_follows_the_documented_priority_and_triggers():
    assert dc.stratum_of({"stratum": "C5", "time_verified": True}) == "C5"
    assert dc.stratum_of({"time_verified": True, "tags": ["transactional"]}) == "C3"
    for kind in ("categorical", "mixed"):
        assert dc.stratum_of({"schema_kind": kind}) == "C2"
    for tag in ("transactional", "categorical_only"):
        assert dc.stratum_of({"tags": [tag]}) == "C2"
    assert dc.stratum_of({"tags": ["time_series"], "schema_kind": "numeric"}) == "C1"
    assert dc.stratum_of({"tags": None}) == "C1" and dc.stratum_of({}) == "C1"
    assert (
        dc.stratum_of({"stratum": "", "schema_kind": "mixed"}) == "C2"
    )  # an empty stratum is no stratum
    assert dc.stratum_of({"time_verified": False, "schema_kind": "numeric"}) == "C1"


def _coverage_file(tmp_path):
    import json

    def cell(status):
        return {"status": status}

    def entry(i, source, decision, chrono, injected, kind="numeric"):
        return {
            "id": i,
            "independent_source": source,
            "decision": decision,
            "schema_kind": kind,
            "protocols": {
                "chronological": cell(chrono),
                "chronological_injected_classical": cell(injected),
            },
        }

    data = {
        "datasets": [
            entry("uci:1", "s1", "retained", "executed", "not_evaluated"),
            entry("uci:2", "s2", "retained", "not_evaluated", "executed", "mixed"),
            entry("uci:3", "s3", "retained", "not_evaluated", "not_evaluated"),
            entry("uci:4", "s4", "retired", "executed", "executed"),
        ]
    }
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(data))
    return path


def test_stratum_rows_have_exact_fields_for_every_origin(tmp_path):
    import json

    coverage = _coverage_file(tmp_path)
    wave2 = tmp_path / "wave2.json"
    wave2.write_text(
        json.dumps(
            {
                "tables": [
                    {"uci_id": 7, "tags": ["sequential"], "time_candidates": ["t"]},
                    {"uci_id": 8, "tags": [], "time_candidates": []},
                ]
            }
        )
    )
    times = tmp_path / "times.json"
    times.write_text(json.dumps({"uci:7": {"verified": True}, "uci:8": {"verified": False}}))
    natural = tmp_path / "nat"
    natural.mkdir()
    (natural / "b.json").write_text(json.dumps({"id": "n/2", "group": "g2", "chronological": {}}))
    (natural / "a.json").write_text(json.dumps({"id": "n/1", "group": "g1", "chronological": {}}))
    (natural / "c.json").write_text(json.dumps({"id": "n/3", "group": "g3", "excluded": "x"}))
    rows = dc.stratum_rows(coverage, wave2, natural, times)
    assert rows == [
        {
            "id": "uci:1",
            "source": "s1",
            "schema_kind": "numeric",
            "time_verified": True,
            "origin": "first_pool",
        },
        {
            "id": "uci:2",
            "source": "s2",
            "schema_kind": "mixed",
            "time_verified": True,
            "origin": "first_pool",
        },
        {
            "id": "uci:3",
            "source": "s3",
            "schema_kind": "numeric",
            "time_verified": False,
            "origin": "first_pool",
        },
        {
            "id": "uci:7",
            "source": "uci:7",
            "tags": ["sequential"],
            "time_verified": True,
            "time_candidate": True,
            "origin": "wave2",
        },
        {
            "id": "uci:8",
            "source": "uci:8",
            "tags": [],
            "time_verified": False,
            "time_candidate": False,
            "origin": "wave2",
        },
        {"id": "n/1", "source": "natural:g1", "time_verified": True, "origin": "natural_temporal"},
        {"id": "n/2", "source": "natural:g2", "time_verified": True, "origin": "natural_temporal"},
    ]
    no_times = dc.stratum_rows(
        tmp_path / "none.json", wave2, tmp_path / "none", tmp_path / "none2.json"
    )
    assert [r["id"] for r in no_times] == ["uci:7", "uci:8"]
    assert all(r["time_verified"] is False for r in no_times)


def test_licence_and_acquired_rows_have_exact_fields_and_skip_missing_or_ineligible(tmp_path):
    import json

    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps({"licence_class": "research_only", "tables": [{"id": "log:1"}, {"id": "log:2"}]})
    )
    assert dc.licence_rows([(manifest, "C4"), (tmp_path / "none.json", "C9")]) == [
        {
            "id": "log:1",
            "source": "log:1",
            "stratum": "C4",
            "licence_class": "research_only",
            "publisher": "logpai",
            "origin": "licence_manifest",
        },
        {
            "id": "log:2",
            "source": "log:2",
            "stratum": "C4",
            "licence_class": "research_only",
            "publisher": "logpai",
            "origin": "licence_manifest",
        },
    ]
    entries = {
        "entries": [
            {
                "id": "a:1",
                "family": "fam",
                "system": "sys",
                "publisher": "pub",
                "stratum": "C5",
                "licence_class": "open",
                "eligible": True,
            },
            {
                "id": "a:2",
                "family": "fam2",
                "system": "s2",
                "publisher": "p2",
                "stratum": "C6",
                "licence_class": "open",
                "eligible": False,
            },
        ]
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(entries))
    assert dc.acquired_rows(path) == [
        {
            "id": "a:1",
            "source": "fam",
            "system": "sys",
            "publisher": "pub",
            "stratum": "C5",
            "licence_class": "open",
            "origin": "acquired",
        }
    ]
    assert dc.transactional_rows(tmp_path / "none.json") == []
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"transactional": {"uci:1": {}, "uci:2": {}}}))
    assert [r["id"] for r in dc.transactional_rows(audit)] == ["uci:1", "uci:2"]


def _frame(n=60, **columns):
    import pandas as pd

    return pd.DataFrame({k: v(n) if callable(v) else v for k, v in columns.items()})


def test_transactional_signals_follow_their_thresholds_exactly():
    import pandas as pd

    def table(distinct, rows, name="user_id"):
        return pd.DataFrame({name: [i % distinct for i in range(rows)], "amount": range(rows)})

    assert dc.transactional_signals(table(20, 60))["keys"] == ["user_id"]
    assert dc.transactional_signals(table(19, 60))["keys"] == []  # fewer than 20 distinct values
    assert dc.transactional_signals(table(30, 30))["keys"] == []  # no value repeats
    assert (
        dc.transactional_signals(table(30, 31))["keys"] == []
    )  # 2 of 31 rows share a value: below 0.2
    assert dc.transactional_signals(table(30, 36))["keys"] == [
        "user_id"
    ]  # 12 of 36 share: above 0.2
    boundary = pd.DataFrame(
        {"user_id": [i % 10 for i in range(20)] + list(range(100, 180)), "amount": range(100)}
    )
    assert dc.transactional_signals(boundary)["keys"] == [
        "user_id"
    ]  # 20 of 100 rows share: exactly 0.2
    below = pd.DataFrame(
        {"user_id": [i % 10 for i in range(20)] + list(range(100, 185)), "amount": range(105)}
    )
    assert dc.transactional_signals(below)["keys"] == []  # 20 of 105 rows: under 0.2
    for name in (
        "CustomerID",
        "invoiceNo",
        "txn_id",
        "patient_nbr",
        "SESSION",
        "card-id",
        "merchant",
    ):
        assert dc.transactional_signals(table(20, 60, name))["keys"] == [name], name
    for name in ("country", "identifier", "bid", "customerValue_x"):
        keys = dc.transactional_signals(table(20, 60, name))["keys"]
        assert keys == ([name] if name == "customerValue_x" else []), name
    floats = pd.DataFrame({"user_id": [float(i % 20) for i in range(60)], "amount": range(60)})
    assert dc.transactional_signals(floats)["keys"] == []  # a float is a measure
    with_nan = pd.DataFrame(
        {"user_id": [None] * 10 + [i % 20 for i in range(50)], "amount": range(60)}
    )
    assert dc.transactional_signals(with_nan)["keys"] == []  # float because of the missing values
    text = pd.DataFrame({"user_id": [f"u{i % 20}" for i in range(60)], "amount": range(60)})
    assert dc.transactional_signals(text)["keys"] == ["user_id"]
    assert dc.transactional_signals(pd.DataFrame({"user_id": []}))["keys"] == []


def test_transactional_signals_events_and_times_are_exact():
    import pandas as pd

    frame = pd.DataFrame(
        {
            "Price": [1.0, 2.0],
            "quantity_ordered": [1, 2],
            "payment_type": ["a", "b"],  # not numeric: not an event column
            "Fare": [1, 2],
            "revenue": [1, 2],
            "Balance": [1, 2],
            "qty": [1, 2],
            "debit": [1, 2],
            "credit": [1, 2],
            "other": [1, 2],
        }
    )
    assert dc.transactional_signals(frame)["event_columns"] == [
        "Balance",
        "Fare",
        "Price",
        "credit",
        "debit",
        "qty",
        "quantity_ordered",
        "revenue",
    ]
    assert dc.transactional_signals(frame, ["b", "a"])["time_columns"] == ["a", "b"]
    assert dc.transactional_signals(frame)["time_columns"] == []
    assert dc.transactional_signals(frame, None)["time_columns"] == []


def test_is_transactional_needs_a_key_and_an_event_or_a_time_column():
    base = {"keys": ["k"], "event_columns": [], "time_columns": []}
    assert dc.is_transactional({**base, "event_columns": ["e"]}) is True
    assert dc.is_transactional({**base, "time_columns": ["t"]}) is True
    assert dc.is_transactional(base) is False
    assert dc.is_transactional({"keys": [], "event_columns": ["e"], "time_columns": ["t"]}) is False


def test_the_audit_has_exact_sections_counts_and_uses_verified_time_columns():
    import pandas as pd

    n = 60
    retail = pd.DataFrame({"customer_id": [i % 20 for i in range(n)], "note": range(n)})
    plain = pd.DataFrame({"x": range(n)})
    tables = {"uci:1": retail, "uci:2": plain, "uci:9": retail}
    rows = [
        {"id": "uci:1", "source": "1", "schema_kind": "mixed"},
        {"id": "uci:2", "source": "2", "schema_kind": "numeric"},
        {"id": "adbench:cardio", "source": "3", "schema_kind": "numeric"},
        {"id": "nab/x", "source": "4", "time_verified": True},
        {"id": "skab/x", "source": "5", "time_verified": True},
        {"id": "uci:3", "source": "6", "schema_kind": "mixed"},
        {"id": "uci:9", "source": "7", "stratum": "C4"},  # not audited: not in C1 to C3
    ]
    audit = dc.transactional_audit(
        rows, lambda r: tables.get(r["id"]), {"uci:1": {"verified": True, "column": "when"}}
    )
    assert audit["transactional"] == {
        "uci:1": {"keys": ["customer_id"], "event_columns": [], "time_columns": ["when"]}
    }
    assert audit["not_transactional"] == {
        "uci:2": {"keys": [], "event_columns": [], "time_columns": []}
    }
    assert audit["numeric_arrays_without_schema"] == ["adbench:cardio", "nab/x", "skab/x"]
    assert audit["not_audited"] == ["uci:3"]
    assert audit["counts"] == {
        "transactional": 1,
        "not_transactional": 1,
        "numeric_arrays_without_schema": 3,
        "not_audited": 1,
    }
    unverified = dc.transactional_audit(
        rows[:1], lambda r: retail, {"uci:1": {"verified": False, "column": "when"}}
    )
    assert unverified["counts"]["transactional"] == 0  # a key alone is not enough
    assert dc.transactional_audit(rows[:1], lambda r: retail)["counts"]["transactional"] == 0


def test_read_row_chooses_the_folder_by_origin_and_ignores_other_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "ROOT", tmp_path)
    (tmp_path / "data" / "pool").mkdir(parents=True)
    (tmp_path / "data" / "uci_wave2").mkdir()
    (tmp_path / "data" / "pool" / "5.csv").write_text("a,b\n1,2\n")
    (tmp_path / "data" / "uci_wave2" / "5.csv").write_text("a,b\n7,8\n")
    first = dc._read_row({"id": "uci:5", "origin": "first_pool"})
    wave = dc._read_row({"id": "uci:5", "origin": "wave2"})
    assert first["a"].tolist() == [1] and wave["a"].tolist() == [7]
    assert dc._read_row({"id": "uci:5"})["a"].tolist() == [1]  # no origin: the pool
    assert dc._read_row({"id": "uci:6", "origin": "wave2"}) is None  # no such file
    assert dc._read_row({"id": "adbench:5"}) is None and dc._read_row({"id": "nab/5"}) is None


def _report_rows():
    return [
        {"id": "a", "source": "s1", "schema_kind": "numeric"},
        {"id": "b", "source": "s1", "schema_kind": "numeric", "system": "sy", "publisher": "p1"},
        {
            "id": "c",
            "source": "s2",
            "stratum": "C4",
            "system": "sy",
            "publisher": "p1",
            "licence_class": "research_only",
        },
        {"id": "d", "source": "s3", "tags": ["x"], "time_candidate": True, "time_verified": False},
        {"id": "e", "source": "s4", "time_candidate": True, "time_verified": True},
    ]


def test_the_gap_report_is_exact():
    report = dc.gap_report(_report_rows())
    assert report["total_sources"] == 4
    assert report["licence_classes"] == {"open": 3, "research_only": 1}
    assert report["time_candidates_not_yet_verified"] == ["s3"]
    c1 = report["strata"]["C1"]
    assert c1 == {
        "stratum": "flat tabular",
        "sources": 2,
        "systems": 3,
        "publishers": 3,
        "minimum": 15,
        "recommended": 36,
        "ambitious": 50,
        "missing_to_minimum": 13,
        "missing_to_recommended": 34,
    }
    c4 = report["strata"]["C4"]
    assert (c4["sources"], c4["systems"], c4["publishers"]) == (1, 1, 1)
    assert report["strata"]["C3"]["sources"] == 1
    assert (
        report["strata"]["C2"]["sources"] == 0
        and report["strata"]["C2"]["missing_to_minimum"] == 15
    )
    big = [{"id": str(i), "source": f"s{i}", "schema_kind": "numeric"} for i in range(60)]
    capped = dc.gap_report(big)["strata"]["C1"]
    assert capped["missing_to_minimum"] == 0 and capped["missing_to_recommended"] == 0
    assert list(report["strata"]) == list(dc.STRATA)
    exactly = [{"id": str(i), "source": f"s{i}", "schema_kind": "numeric"} for i in range(15)]
    assert dc.gap_report(exactly)["strata"]["C1"]["missing_to_minimum"] == 0
    assert dc.gap_report(exactly)["strata"]["C1"]["missing_to_recommended"] == 21
    assert dc.gap_report([])["total_sources"] == 0


def test_the_gap_report_renders_exactly():
    text = dc.render_gap(dc.gap_report(_report_rows()))
    lines = text.split("\n")
    assert lines[0] == "# Independent source families per stratum against the targets"
    assert lines[1] == ""
    assert lines[2] == (
        "| Stratum | Families | Systems | Publishers | Minimum | Recommended | Ambitious "
        "| Missing to recommended |"
    )
    assert lines[3] == "|---|---:|---:|---:|---:|---:|---:|---:|"
    assert lines[4] == "| C1 flat tabular | 2 | 3 | 3 | 15 | 36 | 50 | 34 |"
    assert lines[5].startswith(
        "| C2 transactional and categorical (historical) | 0 | 0 | 0 | 15 | 30 | 45 | 30 |"
    )
    assert lines[6] == "| C2a categorical and mixed tables | 0 | 0 | 0 | 15 | 30 | 45 | 30 |"
    assert lines[11] == "| C6 nested | 0 | 0 | 0 | 15 | 30 | 45 | 30 |"
    assert lines[12] == ""
    assert lines[13] == "Licence classes (sources): open 3, research_only 1."
    assert lines[14] == ""
    assert lines[15] == (
        "Distinct source families: 4. Wave-2 tables with a time-column candidate that is not yet "
        "verified as a single chronological series: 1."
    )
    assert text.endswith("\n") and len(lines) == 17 and lines[16] == ""
    assert len([line for line in lines if line.startswith("| C")]) == 8


def test_c2a_acquired_entries_count_in_the_gap_report_without_error(tmp_path, monkeypatch):
    rows = [
        {
            "id": "flat:uci:19:C2a",
            "source": "uci:19",
            "system": "uci:19",
            "publisher": "uci:19",
            "stratum": "C2a",
            "licence_class": "open",
            "origin": "acquired",
        },
        {
            "id": "dft_stats19_2023",
            "source": "dft_stats19",
            "system": "gb_police_collision_reporting",
            "publisher": "uk_dft_road_safety",
            "stratum": "C2a",
            "licence_class": "open",
            "origin": "acquired",
        },
        {
            "id": "dft_stats19_2024",
            "source": "dft_stats19",
            "system": "gb_police_collision_reporting_2024",
            "publisher": "uk_dft_road_safety_alt",
            "stratum": "C2a",
            "licence_class": "open",
            "origin": "acquired",
        },
    ]
    report = dc.gap_report(rows)
    c2a = report["strata"]["C2a"]
    assert c2a == {
        "stratum": "categorical and mixed tables",
        "sources": 2,
        "systems": 3,
        "publishers": 3,
        "minimum": 15,
        "recommended": 30,
        "ambitious": 45,
        "missing_to_minimum": 13,
        "missing_to_recommended": 28,
    }
    assert "| C2a categorical and mixed tables | 2 | 3 | 3 | 15 | 30 | 45 | 28 |" in dc.render_gap(
        report
    )
    monkeypatch.setattr(dc, "stratum_rows", lambda: [])
    monkeypatch.setattr(dc, "licence_rows", lambda manifests: [])
    monkeypatch.setattr(dc, "acquired_rows", lambda: rows)
    monkeypatch.setattr(dc, "transactional_rows", lambda: [])
    out = tmp_path / "gap_c2a"
    assert dc.main(["gap", "--out", str(out)]) == 0
    written = json.loads((out / "stratum_gap.json").read_text())
    assert written["strata"]["C2a"]["sources"] == 2


def test_main_writes_the_gap_report_and_the_audit_and_prints_them(tmp_path, monkeypatch, capsys):
    import json

    monkeypatch.setattr(dc, "stratum_rows", lambda: _report_rows()[:2])
    monkeypatch.setattr(
        dc, "licence_rows", lambda manifests: [{"id": "l", "source": "l", "stratum": "C4"}]
    )
    monkeypatch.setattr(dc, "acquired_rows", lambda: [{"id": "q", "source": "q", "stratum": "C5"}])
    monkeypatch.setattr(
        dc, "transactional_rows", lambda: [{"id": "t", "source": "t", "stratum": "C2b"}]
    )
    out = tmp_path / "o" / "deep"
    assert dc.main(["gap", "--out", str(out)]) == 0
    data = json.loads((out / "stratum_gap.json").read_text())
    assert data["total_sources"] == 4 and data["strata"]["C2b"]["sources"] == 1
    text = (out / "stratum_gap.json").read_text()
    assert text == json.dumps(data, indent=1, sort_keys=True) + "\n"
    assert (out / "stratum_gap.md").read_text() == dc.render_gap(data)
    assert capsys.readouterr().out == dc.render_gap(data) + "\n"
    times = tmp_path / "times.json"
    times.write_text(json.dumps({"uci:1": {"verified": True, "column": "when"}}))
    monkeypatch.setattr(dc, "WAVE2_TIME", times)
    seen = {}

    def fake_audit(rows, read, wave2_time):
        seen.update(rows=rows, read=read, times=wave2_time)
        return {"counts": {"transactional": 1}, "transactional": {}}

    monkeypatch.setattr(dc, "transactional_audit", fake_audit)
    out2 = tmp_path / "o2"
    assert dc.main(["transactional", "--out", str(out2)]) == 0
    assert seen["read"] is dc._read_row and seen["times"] == {
        "uci:1": {"verified": True, "column": "when"}
    }
    assert (out2 / "transactional_audit.json").read_text() == json.dumps(
        {"counts": {"transactional": 1}, "transactional": {}}, indent=1, sort_keys=True
    ) + "\n"
    assert capsys.readouterr().out.strip().endswith("{'transactional': 1}")
    monkeypatch.setattr(dc, "WAVE2_TIME", tmp_path / "absent.json")
    assert dc.main(["transactional", "--out", str(out2)]) == 0
    assert seen["times"] == {}
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        dc.main(["nonsense"])


def test_skipped_inputs_do_not_stop_the_scan_of_later_ones(tmp_path):
    import json

    import pandas as pd

    coverage = tmp_path / "coverage.json"
    base = {"independent_source": "s", "schema_kind": "numeric"}
    cell = {"status": "not_evaluated"}
    protocols = {"chronological": cell, "chronological_injected_classical": cell}
    coverage.write_text(json.dumps({"datasets": [
        {**base, "id": "r", "decision": "retired", "protocols": protocols},  # a retired table first
        {**base, "id": "k", "decision": "retained", "protocols": protocols},
    ]}))  # fmt: skip
    natural = tmp_path / "nat"
    natural.mkdir()
    (natural / "0.json").write_text(json.dumps({"id": "skip", "group": "g", "excluded": "x"}))
    (natural / "1.json").write_text(json.dumps({"id": "n/1", "group": "g", "chronological": {}}))
    rows = dc.stratum_rows(coverage, tmp_path / "none.json", natural, tmp_path / "none2.json")
    assert [r["id"] for r in rows] == ["k", "n/1"]
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"licence_class": "open", "tables": [{"id": "x"}]}))
    assert [
        r["id"] for r in dc.licence_rows([(tmp_path / "gone.json", "C4"), (manifest, "C4")])
    ] == ["x"]
    n = 60
    frame = pd.DataFrame(
        {
            "note": range(n),
            "country": ["a"] * n,
            "user_id": [i % 20 for i in range(n)],
            "amount": range(n),
        }
    )  # key columns after non-key columns
    assert dc.transactional_signals(frame)["keys"] == ["user_id"]
    floats = pd.DataFrame(
        {"fl": [0.5] * n, "empty_id": [None] * n, "user_id": [i % 20 for i in range(n)]}
    )
    assert dc.transactional_signals(floats)["keys"] == [
        "user_id"
    ]  # a float and an empty column first
    audit = dc.transactional_audit(
        [
            {"id": "x", "source": "x", "stratum": "C5"},
            {"id": "uci:1", "source": "1", "schema_kind": "numeric"},
        ],
        lambda r: frame,
    )
    assert list(audit["not_transactional"]) + list(audit["transactional"]) == ["uci:1"]


def test_read_row_uses_exact_paths_and_reads_without_low_memory(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(dc, "ROOT", tmp_path)
    seen = []
    real = pd.read_csv

    def spy(path, *args, **kwargs):
        seen.append((str(path), kwargs))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", spy)
    for folder in ("pool", "uci_wave2"):
        (tmp_path / "data" / folder).mkdir(parents=True)
        (tmp_path / "data" / folder / "5.csv").write_text("a\n1\n".replace("\\\\n", "\\n"))
    (tmp_path / "data" / "pool" / "a:b.csv").write_text("a\n2\n")
    dc._read_row({"id": "uci:5", "origin": "wave2"})
    dc._read_row({"id": "uci:5", "origin": "first_pool"})
    assert dc._read_row({"id": "uci:a:b"})["a"].tolist() == [2]  # only the first colon splits
    assert seen[0] == (f"{tmp_path}/data/uci_wave2/5.csv", {"low_memory": False})
    assert seen[1] == (f"{tmp_path}/data/pool/5.csv", {"low_memory": False})
    assert seen[2][0] == f"{tmp_path}/data/pool/a:b.csv"


def test_main_creates_nested_output_directories_twice_names_its_files_and_describes_itself(
    tmp_path, monkeypatch, capsys
):
    import json
    from pathlib import Path

    monkeypatch.setattr(
        dc, "stratum_rows", lambda: [{"id": "a", "source": "a", "schema_kind": "numeric"}]
    )
    monkeypatch.setattr(dc, "licence_rows", lambda manifests: [])
    monkeypatch.setattr(dc, "acquired_rows", lambda: [])
    monkeypatch.setattr(dc, "transactional_rows", lambda: [])
    manifests = []
    monkeypatch.setattr(dc, "licence_rows", lambda m: manifests.append(m) or [])
    names = []
    real = Path.write_text

    def spy(self, data, *a, **k):
        names.append(self.name)
        return real(self, data, *a, **k)

    monkeypatch.setattr(Path, "write_text", spy)
    out = tmp_path / "a" / "b" / "c"
    assert dc.main(["gap", "--out", str(out)]) == 0
    assert dc.main(["gap", "--out", str(out)]) == 0  # an existing directory is fine
    assert names == ["stratum_gap.json", "stratum_gap.md"] * 2
    assert manifests == [dc.LICENCE_MANIFESTS, dc.LICENCE_MANIFESTS]
    text = (out / "stratum_gap.json").read_text()
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    names.clear()
    monkeypatch.setattr(dc, "WAVE2_TIME", tmp_path / "absent.json")
    rows = [{"id": "uci:z", "source": "z", "schema_kind": "numeric"}]
    monkeypatch.setattr(dc, "stratum_rows", lambda: rows)
    got = {}
    monkeypatch.setattr(
        dc,
        "transactional_audit",
        lambda r, read, t: got.update(rows=r) or {"counts": {}, "z": 1, "a": 2},
    )
    out2 = tmp_path / "x" / "y"
    assert dc.main(["transactional", "--out", str(out2)]) == 0
    assert dc.main(["transactional", "--out", str(out2)]) == 0
    assert got["rows"] is rows and names == ["transactional_audit.json"] * 2
    audit_text = (out2 / "transactional_audit.json").read_text()
    assert list(json.loads(audit_text)) == ["a", "counts", "z"]  # sorted keys
    assert audit_text.startswith('{\n "a": 2')  # one-space indent
    monkeypatch.setattr(dc, "GAP_DIR", tmp_path / "default")
    assert dc.main(["gap"]) == 0
    assert (tmp_path / "default" / "stratum_gap.json").exists()
    capsys.readouterr()
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        dc.main(["--help"])
    assert "One logical catalog" in capsys.readouterr().out
