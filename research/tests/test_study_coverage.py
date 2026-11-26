"""Coverage rows join existing evidence only; synthetic registry."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import study_coverage as sc  # noqa: E402


def _fact(group, view, protocol="P-TS", units=2000, minimum=1000, labels=False):
    fact = {
        "independent_group": group,
        "view": view,
        "protocol_id": protocol,
        "anomaly_origin": "controlled_injection",
        "units": units,
        "min_units": minimum,
    }
    return fact | ({"natural_labels": ["x"]} if labels else {})


def _setup(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    facts = {
        "a": _fact("ga", "va"),
        "b": _fact("gb", "vb", "P-TAB", units=10),
        "c": _fact("gc", "vc", "P-REL", labels=True),
        "d": _fact("gd", "vd"),
        "z": _fact("gz", "vz"),  # not ready: never counted
    }
    (ev / "readiness_facts.json").write_text(json.dumps({"facts": facts}))
    (ev / "readiness.json").write_text(
        json.dumps({"ready_groups": {"C3": ["ga", "gd"], "C1": ["gb", "gc"], "C5": ["gc"]}})
    )
    ok = {"eligible": True, "reasons": [], "view": "va", "views": ["va"], "table": {}}
    no = {"eligible": False, "reasons": ["no parseable time column"], "views": [], "table": None}
    audit = {"ga": ok, "gb": no, "gc": no, "gd": ok, "gz": ok}
    (ev / "batch_eligibility.json").write_text(json.dumps({"groups": audit}))
    protocols = {p: {"mechanisms": [f"m-{p}"]} for p in ("P-TS", "P-TAB", "P-REL")}
    (ev / "anomaly_protocols.json").write_text(json.dumps({"protocols": protocols}))
    manifest = {n: {"files": {"t.csv": {}}} for n in ("va", "vb", "vc", "vd")}
    (ev / "experimental_views.json").write_text(json.dumps(manifest))
    (ev / "linked_sets.json").write_text(
        json.dumps({"linked_sets": [{"groups": ["ga", "gd"]}], "exposed_groups": {"ga": "seen"}})
    )
    views = tmp_path / "views"
    for v in ("va", "vb", "vd"):  # vc is not built
        (views / v).mkdir(parents=True)
        (views / v / "t.csv").write_text("x\n1\n")
    return ev, views


def test_rows_join_availability_protocol_units_batch_clusters_and_exposure(tmp_path):
    ev, views = _setup(tmp_path)
    manifest = json.loads((ev / "experimental_views.json").read_text())
    links = json.loads((ev / "linked_sets.json").read_text())
    rows = sc.group_rows(ev, views, links, manifest)
    assert sorted(rows) == ["ga", "gb", "gc", "gd"]
    assert rows["ga"]["cluster"] == rows["gd"]["cluster"] == "ga" and rows["ga"]["exposed"]
    assert rows["ga"]["batch_approved"]["eligible"] and rows["ga"]["unit_level"]["compatible"]
    assert rows["gb"]["unit_level"] == {
        "mechanisms": ["m-P-TAB"],
        "compatible": False,
        "reason": "fewer units than the minimum",
    }
    assert rows["gc"]["unit_level"]["reason"] == "view not built locally"
    assert rows["gc"]["categories"] == ["C1", "C5"] and rows["gc"]["labels"]["natural_labels"]
    assert [p["unit"] for p in rows["gc"]["batch_provisional"]] == ["relational_load"]
    assert rows["gc"]["batch_provisional"][0]["reason"].startswith("unsupported")
    assert rows["ga"]["batch_provisional"] == []


def test_the_summary_counts_groups_clusters_and_categories_not_participations(tmp_path):
    ev, views = _setup(tmp_path)
    manifest = json.loads((ev / "experimental_views.json").read_text())
    links = json.loads((ev / "linked_sets.json").read_text())
    summary = sc.summarise(sc.group_rows(ev, views, links, manifest))
    assert summary["groups"] == 4 and summary["clusters"] == 3
    assert summary["batch_approved"] == 2 and summary["batch_approved_clusters"] == 1
    assert summary["unit_level"] == 2 and summary["natural_labels"] == 1
    assert summary["protocols"] == {"P-REL": 1, "P-TAB": 1, "P-TS": 2}
    assert summary["per_category"]["C3"] == {
        "groups": 2, "local_view": 2, "unit_level": 2, "batch_approved": 2,
        "batch_approved_clusters": 1, "exposed": 1,
    }  # fmt: skip
    assert summary["per_category"]["C1"]["local_view"] == 1


def test_main_is_deterministic_and_prints_without_an_output(tmp_path, capsys):
    ev, views = _setup(tmp_path)
    argv = ["--evidence", str(ev), "--views", str(views)]
    assert sc.main(argv) == 0
    first = capsys.readouterr().out
    out = tmp_path / "c.json"
    assert sc.main([*argv, "--output", str(out)]) == 0
    assert out.read_text() == first and list(json.loads(first)) == ["groups", "summary"]


def test_a_view_is_available_through_its_directory_or_the_flat_folder(tmp_path):
    manifest = {"v": {"files": {"t.csv": {}}}, "e": {"files": {}}}
    assert not sc.view_available(manifest, tmp_path, "v") and not sc.view_available(
        manifest, tmp_path, "e"
    )
    (tmp_path / "flat").mkdir()
    (tmp_path / "flat" / "t.csv").write_text("x")
    assert sc.view_available(manifest, tmp_path, "v")
    assert not sc.view_available(manifest, tmp_path, "missing")


def test_a_group_with_several_facts_joins_their_views_origins_labels_and_unit_checks(tmp_path):
    ev, views = _setup(tmp_path)
    facts = json.loads((ev / "readiness_facts.json").read_text())
    facts["facts"]["a2"] = _fact("ga", "vd", units=1000, minimum=1000, labels=True) | {
        "anomaly_origin": "natural"
    }
    facts["facts"]["a3"] = _fact("ga", "vb", units=5, minimum=1000)
    (ev / "readiness_facts.json").write_text(json.dumps(facts))
    manifest = json.loads((ev / "experimental_views.json").read_text())
    rows = sc.group_rows(ev, views, json.loads((ev / "linked_sets.json").read_text()), manifest)
    row = rows["ga"]
    assert row["views"] == ["va", "vb", "vd"]
    assert row["labels"] == {"natural_labels": True, "origin": ["controlled_injection", "natural"]}
    assert row["unit_level"]["compatible"] and row["unit_level"]["reason"] == ""
    assert row["batch_approved"] == {"eligible": True, "reasons": []}
    assert rows["gb"]["batch_approved"] == {
        "eligible": False,
        "reasons": ["no parseable time column"],
    }
    assert rows["gb"]["views"] == ["vb"] and rows["gb"]["labels"]["natural_labels"] is False


def test_exactly_the_minimum_number_of_units_is_enough(tmp_path):
    ev, views = _setup(tmp_path)
    facts = json.loads((ev / "readiness_facts.json").read_text())
    facts["facts"]["b"] = _fact("gb", "vb", "P-TAB", units=1000, minimum=1000)
    (ev / "readiness_facts.json").write_text(json.dumps(facts))
    manifest = json.loads((ev / "experimental_views.json").read_text())
    rows = sc.group_rows(ev, views, json.loads((ev / "linked_sets.json").read_text()), manifest)
    assert rows["gb"]["unit_level"]["compatible"]


def test_the_parser_defaults_and_description():
    args = sc.build_parser().parse_args([])
    assert (args.evidence, args.views, args.output) == (sc.EVIDENCE, sc.VIEWS, None)
    assert sc.build_parser().description == sc.__doc__
    assert sc.EVIDENCE.name == "dataset_registry_v2"
