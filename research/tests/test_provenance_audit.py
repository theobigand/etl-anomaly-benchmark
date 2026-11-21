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


def test_unclassified_areas_are_not_counted_as_domains_or_mechanisms():
    rows = [{"id": f"uci:{i}", "source": f"uci:{i}", "schema_kind": "numeric"} for i in (1, 2, 3)]
    meta = {"uci:1": {"creators": ["A"], "area": "Other"}, "uci:2": {"creators": ["B"], "area": None},  # noqa: E501
            "uci:3": {"creators": ["C"], "area": "Biology"}}  # fmt: skip
    out = pa.audit(rows, meta)["C1"]
    assert out["domains"] == 1 and out["domain_list"] == ["Biology"]
    assert out["mechanisms"] == 1 and out["mechanism_list"] == ["clinical or biological records"]


def test_person_keys_handle_initials_surnames_and_multiple_names():
    assert pa.person_key("J Smith") == "smith j" and pa.person_key("J. Smith") == "smith j"
    assert (
        pa.person_key("Smith, J.") == "smith j." and pa.person_key("Mary Ann Lee") == "mary ann lee"
    )
    assert pa.person_key("  A.  B.  Lee ") == "lee a" or pa.person_key("  A.  B.  Lee ") == "lee a"
    assert pa.person_key("Lee") == "lee" and pa.person_key("  ") == ""


def test_guardrails_boundaries_for_the_exploratory_tier_and_the_three_minima():
    entry = {"groups": 36, "domains": 3, "mechanisms": 2, "target": 36}
    assert pa.guardrails(entry)["exploratory"] is True
    assert pa.guardrails({**entry, "domains": 2})["exploratory"] is False
    assert pa.guardrails({**entry, "mechanisms": 1})["exploratory"] is False
    assert (
        pa.guardrails({"groups": 36, "domains": 5, "mechanisms": 3, "target": 36})["generalisation"]
        is True
    )
    assert pa.guardrails({"groups": 35, "domains": 5, "mechanisms": 3, "target": 36})[
        "missing"
    ] == ["groups: 35 of 36"]
    assert pa.guardrails({"groups": 36, "domains": 4, "mechanisms": 3, "target": 36})[
        "missing"
    ] == ["domains: 4 of 5"]
    assert pa.guardrails({"groups": 36, "domains": 5, "mechanisms": 2, "target": 36})[
        "missing"
    ] == ["mechanisms: 2 of 3"]


def test_audit_assigns_tagged_and_mixed_tables_to_c2a_and_ignores_stratum_and_time_series_rows():
    rows = [
        {"id": "a", "source": "uci:1", "schema_kind": "numeric"},
        {"id": "b", "source": "uci:2", "schema_kind": "mixed"},
        {"id": "c", "source": "uci:3", "tags": ["categorical_only"]},
        {"id": "d", "source": "uci:4", "tags": ["transactional"]},
        {"id": "e", "source": "uci:5", "stratum": "C4"},
        {"id": "f", "source": "uci:6", "time_verified": True},
    ]
    meta = {f"uci:{i}": {"creators": [f"P{i}"], "area": "Biology"} for i in range(1, 7)}
    out = pa.audit(rows, meta)
    assert (
        out["C1"]["tables"] == 2 and out["C2a"]["tables"] == 2
    )  # uci:1 and uci:4 flat; uci:2 and uci:3 categorical
    assert out["ALL"] == {"sources": 4, "groups": 4, "tables": 4}
    assert out["C1"]["target"] == 36 and out["C2a"]["target"] == 30
    assert out["C1"]["largest_group_share"] == 0.5 and out["C1"]["domain_list"] == ["Biology"]


def test_audit_counts_a_missing_metadata_source_as_an_unknown_domain_and_names_groups_by_the_smallest_member():  # noqa: E501
    rows = [
        {"id": "a", "source": "uci:2", "schema_kind": "numeric"},
        {"id": "b", "source": "uci:1", "schema_kind": "numeric"},
    ]
    out = pa.audit(
        rows, {"uci:1": {"creators": ["X"], "area": "Business"}, "uci:2": {"creators": ["X"]}}
    )
    assert out["C1"]["groups"] == 1 and out["C1"]["largest_group_share"] == 1.0
    assert out["C1"]["domain_list"] == ["Business"] and out["C1"]["domains"] == 1


def test_the_opener_requests_the_url_with_a_user_agent_and_reads_at_most_two_megabytes(monkeypatch):
    seen = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            seen["read"] = n
            return b"{}"

    def fake(request, timeout):
        seen["url"] = request.full_url
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return Reply()

    monkeypatch.setattr(pa.urllib.request, "urlopen", fake)
    assert pa._open("https://archive.ics.uci.edu/api/dataset?id=5") == b"{}"
    assert seen == {"url": "https://archive.ics.uci.edu/api/dataset?id=5",
                    "agent": "etl-benchmark-acquisition (academic research)", "timeout": 60, "read": 2_000_000}  # fmt: skip  # noqa: E501


def test_fetch_waits_before_each_request_and_writes_a_canonical_cache(tmp_path):
    waits = []

    def opener(url):
        return json.dumps({"data": {"creators": None, "area": None}}).encode()

    out = pa.fetch_metadata([3, 1], tmp_path / "c.json", opener=opener, sleep=waits.append)
    assert waits == [0.5, 0.5] and out == {
        "3": {"creators": [], "area": None},
        "1": {"creators": [], "area": None},
    }
    text = (tmp_path / "c.json").read_text()
    assert text == json.dumps(out, indent=1, sort_keys=True) + "\n"
    again = pa.fetch_metadata(
        [3, 1], tmp_path / "c.json", opener=lambda u: 1 / 0, sleep=waits.append
    )
    assert again == out and waits == [0.5, 0.5]  # a cached id is not requested again


def test_main_runs_the_audit_on_the_catalogue_rows_and_writes_the_evidence_file(
    tmp_path, monkeypatch, capsys
):
    import dataset_catalog as dc

    rows = [{"id": "uci:1", "source": "uci:1", "schema_kind": "numeric"}]
    monkeypatch.setattr(dc, "stratum_rows", lambda: rows)
    seen = {}

    def fake_run(given, cache):
        seen["rows"], seen["cache"] = given, cache
        return {
            "C1": {"tables": 1, "sources": 1, "groups": 1},
            "ALL": {"tables": 1, "sources": 1, "groups": 1},
        }

    monkeypatch.setattr(pa, "run", fake_run)
    assert pa.main(["--dir", str(tmp_path)]) == 0
    assert seen == {"rows": rows, "cache": tmp_path / "uci_metadata_cache.json"}
    text = (tmp_path / "provenance_audit_c1_c2a.json").read_text()
    assert json.loads(text)["C1"]["groups"] == 1 and text.endswith("}\n")
    assert (
        capsys.readouterr().out
        == "{'C1': {'tables': 1, 'sources': 1, 'groups': 1}, 'ALL': {'tables': 1, 'sources': 1, 'groups': 1}}\n"  # noqa: E501
    )
