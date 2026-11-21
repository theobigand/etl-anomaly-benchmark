"""Exact tests of the provenance audit for the flat tabular and categorical strata."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import provenance_audit as pa  # noqa: E402


def test_people_names_are_normalised_so_that_spelling_variants_match():
    assert pa.person_key(" Ronny  Kohavi ") == "ronny kohavi"
    assert pa.person_key("R. Kohavi") == "kohavi r"
    assert pa.person_key("Kohavi, Ronny") == "kohavi ronny"
    assert pa.person_key("") == ""


def test_sources_sharing_a_creator_form_one_group_transitively():
    meta = {
        "uci:1": {"creators": ["Ann Lee", "Bo Chan"]},
        "uci:2": {"creators": ["bo chan", "Cy Dunn"]},
        "uci:3": {"creators": ["Cy Dunn"]},
        "uci:4": {"creators": ["Eve Fox"]},
        "uci:5": {"creators": []},
    }
    groups = pa.group_sources(meta)
    assert groups["uci:1"] == groups["uci:2"] == groups["uci:3"] != groups["uci:4"]
    assert groups["uci:5"] == "uci:5"  # no creator listed: the source is its own group
    assert groups["uci:4"] == "uci:4"
    assert groups["uci:1"] == "uci:1"  # a group is named by its smallest member


def test_areas_map_to_generating_mechanisms_by_a_fixed_documented_table():
    assert pa.mechanism("Health and Medicine") == "clinical or biological records"
    assert pa.mechanism("Physics and Chemistry") == "instrument measurement"
    assert pa.mechanism("Business") == "administrative or survey records"
    assert pa.mechanism("Something Else") == "other"
    assert pa.mechanism(None) == "other"


def _rows():
    return [
        {"id": "uci:1", "source": "uci:1", "schema_kind": "numeric"},
        {"id": "adbench:x", "source": "uci:1", "schema_kind": "numeric"},  # a twin of uci:1
        {"id": "uci:2", "source": "uci:2", "schema_kind": "categorical"},
        {"id": "uci:3", "source": "uci:3", "schema_kind": "numeric"},
        {"id": "uci:4", "source": "uci:4", "schema_kind": "mixed"},
        {"id": "uci:9", "source": "uci:9", "time_verified": True},
    ]


META = {
    "uci:1": {"creators": ["Ann Lee"], "area": "Biology"},
    "uci:2": {"creators": ["Ann Lee"], "area": "Business"},
    "uci:3": {"creators": ["Bo Chan"], "area": "Physics and Chemistry"},
    "uci:4": {"creators": ["Cy Dunn"], "area": "Business"},
    "uci:9": {"creators": ["Zed"], "area": "Biology"},
}


def test_the_audit_counts_tables_sources_groups_domains_and_mechanisms_per_stratum():
    out = pa.audit(_rows(), META)
    assert sorted(out) == [
        "ALL",
        "C1",
        "C2a",
    ]  # the time-series row belongs to C3 and is not audited here
    c1 = out["C1"]
    assert c1 == {
        "tables": 3, "sources": 2, "groups": 2, "domains": 2, "mechanisms": 2,
        "domain_list": ["Biology", "Physics and Chemistry"],
        "mechanism_list": ["clinical or biological records", "instrument measurement"],
        "largest_group_share": 0.5, "target": 36,
    }  # fmt: skip
    c2a = out["C2a"]
    assert (
        c2a["tables"] == 2 and c2a["sources"] == 2 and c2a["groups"] == 2
    )  # uci:2 joins uci:1 only across strata
    assert c2a["domains"] == 1 and c2a["target"] == 30


def test_groups_are_counted_per_stratum_but_defined_over_all_audited_sources():
    out = pa.audit(_rows(), META)
    assert (
        out["C1"]["groups"] == 2 and out["C2a"]["groups"] == 2
    )  # uci:1 (C1) and uci:2 (C2a) share a creator
    assert out["ALL"] == {"sources": 4, "groups": 3, "tables": 5}


def test_guardrail_status_names_what_is_missing():
    status = pa.guardrails({"groups": 4, "domains": 2, "mechanisms": 1, "target": 6})
    assert status["exploratory"] is False and status["missing"][0] == "groups: 4 of 6"
    full = pa.guardrails(
        {"groups": 40, "domains": 5, "mechanisms": 3, "target": 36}, domains=5, mechanisms=3
    )
    assert full == {"exploratory": True, "generalisation": True, "missing": []}
    partial = pa.guardrails(
        {"groups": 20, "domains": 3, "mechanisms": 2, "target": 36}, domains=5, mechanisms=3
    )
    assert partial["exploratory"] is True and partial["generalisation"] is False
    assert partial["missing"] == ["groups: 20 of 36", "domains: 3 of 5", "mechanisms: 2 of 3"]


def test_fetch_uses_the_cache_and_the_injected_opener_for_missing_ids(tmp_path):
    cache = tmp_path / "c.json"
    cache.write_text(json.dumps({"1": {"creators": ["A"], "area": "Biology"}}))
    calls = []

    def opener(url):
        calls.append(url)
        return json.dumps(
            {"data": {"creators": ["B C", "D"], "area": "Business", "name": "x"}}
        ).encode()

    out = pa.fetch_metadata([1, 2], cache, opener=opener, sleep=lambda s: None)
    assert calls == ["https://archive.ics.uci.edu/api/dataset?id=2"]
    assert out == {
        "1": {"creators": ["A"], "area": "Biology"},
        "2": {"creators": ["B C", "D"], "area": "Business"},
    }
    assert json.loads(cache.read_text()) == out


def test_run_fetches_only_uci_sources_that_are_not_time_series_and_adds_guardrails(tmp_path):
    seen = []

    def opener(url):
        seen.append(url)
        number = int(url.rsplit("=", 1)[1])
        return json.dumps({"data": {"creators": [f"Person {number}"], "area": "Biology"}}).encode()

    rows = [
        {"id": "uci:1", "source": "uci:1", "schema_kind": "numeric"},
        {"id": "adbench:t", "source": "uci:1", "schema_kind": "numeric"},
        {"id": "uci:2", "source": "uci:2", "schema_kind": "mixed"},
        {"id": "uci:3", "source": "uci:3", "time_verified": True},
        {"id": "natural:x", "source": "natural:grp", "time_verified": True},
    ]
    out = pa.run(rows, tmp_path / "cache.json", opener=opener, sleep=lambda s: None)
    assert seen == [
        "https://archive.ics.uci.edu/api/dataset?id=1",
        "https://archive.ics.uci.edu/api/dataset?id=2",
    ]
    assert out["C1"]["groups"] == 1 and out["C2a"]["groups"] == 1
    assert out["C1"]["guardrails"]["generalisation"] is False
    assert out["C1"]["guardrails"]["missing"] == [
        "groups: 1 of 36",
        "domains: 1 of 5",
        "mechanisms: 1 of 3",
    ]
    assert out["C1"]["guardrails"]["exploratory"] is False
