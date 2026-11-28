"""Historical exposure inventory: file-name based, deduplicated by group and cluster."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import exposure_inventory as ei  # noqa: E402


def _row(cluster, category="C1", floor=True, exposed=False, curator="uci"):
    return {
        "categories": [category],
        "floor": floor,
        "domain": f"d-{cluster}",
        "schema_family": f"s-{cluster}",
        "curator": curator,
        "cluster": cluster,
        "exposed": exposed,
    }


TABLE = {
    "uci:1": _row("uci:1"),
    "uci:2": _row("uci:2"),
    "seoul": _row("seoul", "C3"),
    "linkedb": _row("linkeda"),
    "linkeda": _row("linkeda"),
    "free": _row("free", "C2a"),
    "abcd7": _row("abcd7"),
}
FACTS = {
    "uci:560": {"independent_group": "seoul"},
    "uci:99": {"independent_group": "not_in_table"},
    "other:1": {"independent_group": "free"},
    "zzzz12": {"independent_group": "free"},
}


def test_file_names_yield_uci_identifiers():
    assert ei.uci_ids(["uci_851.json", "601.json", "run_849_851.log", "adbench_cardio.json"]) == {
        851,
        601,
        849,
    }
    assert ei.uci_ids(["uci:12.json", "notes.md", "12345.json"]) == {12}
    assert ei.uci_ids([]) == set()


def test_ids_map_to_groups_by_name_or_readiness_fact_and_unknown_groups_are_dropped():
    assert ei.id_to_group(TABLE, FACTS) == {560: "seoul", 1: "uci:1", 2: "uci:2"}


def test_study_ids_read_names_recursively_and_missing_folders_are_empty(tmp_path):
    (tmp_path / "labelled_pool/runs").mkdir(parents=True)
    (tmp_path / "labelled_pool/runs/uci_1.json").write_text("{}")
    (tmp_path / "pool_partitions").mkdir()
    (tmp_path / "pool_partitions/uci_2.json").write_text("{}")
    out = ei.study_ids(tmp_path)
    assert out["labelled_pool"] == {1}
    assert out["pool_partitions"] == {2}
    assert out["typed_injection"] == set()


def test_the_inventory_counts_each_group_once_and_separates_structure_from_outcomes():
    ids = {"labelled_pool": {1, 560}, "typed_injection": {1}, "pool_partitions": {2}}
    inv = ei.inventory(TABLE, FACTS, ids, ["seoul"])
    assert inv["classes"] == {"plumbing": ["seoul"], "outcome": ["uci:1"], "structure": ["uci:2"]}
    assert inv["groups"]["uci:1"]["studies"] == {"outcome": ["labelled_pool", "typed_injection"]}
    assert inv["groups"]["seoul"] == {
        "studies": {"outcome": ["labelled_pool"]},
        "plumbing": True,
        "class": "plumbing",
        "cluster": "seoul",
    }
    assert inv["outcome_exposed_groups"] == ["seoul", "uci:1"]
    assert inv["overlap_plumbing_and_outcome_studies"] == ["seoul"]
    assert inv["unmatched_ids"]["pool_partitions"] == []


def test_unmatched_identifiers_are_reported_and_a_plumbing_group_without_studies_is_kept():
    inv = ei.inventory(TABLE, FACTS, {"labelled_pool": {1, 777}}, ["free"])
    assert inv["unmatched_ids"]["labelled_pool"] == [777]
    assert inv["groups"]["free"]["studies"] == {} and inv["classes"]["plumbing"] == ["free"]
    assert inv["overlap_plumbing_and_outcome_studies"] == []


def test_clusters_are_counted_once_when_a_cluster_has_several_exposed_groups():
    inv = ei.inventory(TABLE, FACTS, {"labelled_pool": set()}, ["linkeda", "linkedb"])
    assert inv["outcome_exposed_groups"] == ["linkeda", "linkedb"]
    assert inv["outcome_exposed_clusters"] == ["linkeda"]


def _evidence(tmp_path):
    v2 = tmp_path / "dataset_registry_v2"
    v2.mkdir()
    table = {
        f"g{i:02d}": _row(f"g{i:02d}", ("C1", "C2a")[i % 2], curator=f"c{i % 7}") for i in range(80)
    }
    table["uci:1"] = _row("uci:1")
    table["mixed"] = _row("mixedc", floor=False)
    table["mixed2"] = _row("mixedc", floor=True)
    plans = {str(n): {"pilot": []} for n in (16, 24, 32)}
    (v2 / "unit_pilot_panel.json").write_text(json.dumps({"table": table, "plans": plans}))
    (v2 / "readiness_facts.json").write_text(
        json.dumps({"facts": {"uci:5": {"independent_group": "g05"}}})
    )
    (v2 / "linked_sets.json").write_text(json.dumps({"exposed_groups": {"g00": "plumbing"}}))
    (tmp_path / "labelled_pool").mkdir()
    (tmp_path / "labelled_pool/uci_5.json").write_text("{}")
    (tmp_path / "labelled_pool/uci_1.json").write_text("{}")
    return tmp_path


def test_the_build_compares_the_registry_rule_with_the_wider_outcome_rule(tmp_path):
    evidence = _evidence(tmp_path)
    panel = json.loads((evidence / "dataset_registry_v2/unit_pilot_panel.json").read_text())
    facts = json.loads((evidence / "dataset_registry_v2/readiness_facts.json").read_text())["facts"]
    out = ei.build(panel, facts, evidence, ["g00"], 7)
    assert out["floor_met_unexposed_clusters"] == {"every_member": 81, "any_member": 82}
    narrow, wide = (
        out["scenarios"]["registry_exposed_only"],
        out["scenarios"]["plus_outcome_studies"],
    )
    assert (narrow["exposed_clusters"], wide["exposed_clusters"]) == (1, 3)
    assert (
        wide["balanced"]["16"]["holdout_floor_met"]
        == narrow["balanced"]["16"]["holdout_floor_met"] - 2
    )
    assert out["seed"] == 7 and out["note"].startswith("accounting only")


def test_the_command_line_writes_sorted_indented_json(tmp_path, capsys):
    evidence = _evidence(tmp_path)
    assert ei.main(["--evidence", str(evidence)]) == 0
    text = capsys.readouterr().out
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    target = tmp_path / "o.json"
    assert ei.main(["--evidence", str(evidence), "--seed", "3", "--output", str(target)]) == 0
    assert json.loads(target.read_text())["seed"] == 3


def test_the_build_has_the_documented_keys_and_uses_the_given_seed(tmp_path):
    import pilot_panel_design as ppd

    evidence = _evidence(tmp_path)
    panel = json.loads((evidence / "dataset_registry_v2/unit_pilot_panel.json").read_text())
    facts = json.loads((evidence / "dataset_registry_v2/readiness_facts.json").read_text())["facts"]
    out = ei.build(panel, facts, evidence, ["g00"], 7)
    assert set(out) == {"note", "seed", "inventory", "floor_met_unexposed_clusters", "scenarios"}
    marked = ppd.with_exposure(panel["table"], ["g00"])
    expected = ppd.panel_profile(marked, ppd.balanced_panel(marked, 16, 7)["groups"])
    assert out["scenarios"]["registry_exposed_only"]["balanced"]["16"] == expected
