"""Unit-level pilot panel: seeded draw over metadata only; synthetic registry."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import target_framework as tf  # noqa: E402
import unit_pilot_plan as upp  # noqa: E402

GROUPS = [f"g{i:02d}" for i in range(12)]


def _setup(tmp_path, units=None, partitions=None, exposed=("g00",)):
    ev = tmp_path / "ev"
    ev.mkdir()
    units = units or {}
    partitions = partitions or {}
    facts, datasets, ready = {}, [], {"C1": [], "C3": []}
    for i, g in enumerate(GROUPS):
        category = "C1" if i < 8 else "C3"
        facts[f"f{i}"] = {
            "independent_group": g,
            "protocol_id": "P-TAB" if category == "C1" else "P-TS",
            "units": units.get(g, 10000),
            "min_units": 1000,
            "partitions": partitions.get(g, "hash of the case id 70/15/15, whole cases"),
        }
        datasets.append({"id": f"f{i}", "stratum": category})
        ready[category].append(g)
    registry = {"datasets": datasets, "ready_groups": ready}
    (ev / "readiness_facts.json").write_text(json.dumps({"facts": facts}))
    (ev / "readiness.json").write_text(json.dumps(registry))
    attributes = {
        g: {"domain": f"d{i % 4}", "schema_family": f"s{i % 3}", "curator": "c"}
        for i, g in enumerate(GROUPS)
    }
    (ev / "source_attributes.json").write_text(json.dumps(attributes))
    linked = {
        "linked_sets": [{"groups": ["g02", "g03"]}],
        "exposed_groups": dict.fromkeys(exposed, "seen"),
    }
    (ev / "linked_sets.json").write_text(json.dumps(linked))
    return ev


def test_the_plan_is_deterministic_for_a_seed_and_reads_metadata_files_only(tmp_path):
    ev = _setup(tmp_path)
    assert sorted(p.name for p in ev.iterdir()) == [
        "linked_sets.json",
        "readiness.json",
        "readiness_facts.json",
        "source_attributes.json",
    ]
    first = upp.plan(ev, 4, 1, 7)
    assert first == upp.plan(ev, 4, 1, 7)
    assert first["seed"] == 7 and first["total"] == 4 and first["minimum"] == 1
    assert len(first["pilot"]) == 4


def test_pilot_holdout_and_exposed_groups_are_disjoint_and_linked_groups_stay_together(tmp_path):
    ev = _setup(tmp_path)
    for seed in range(1, 8):
        result = upp.plan(ev, 4, 1, seed)
        pilot, holdout, exposed = (set(result[k]) for k in ("pilot", "holdout", "exposed"))
        assert not pilot & holdout and not pilot & exposed and not holdout & exposed
        assert exposed == {"g00"}
        linked = {"g02", "g03"}
        assert linked <= pilot or linked <= holdout or not linked & (pilot | holdout)


def test_every_category_gets_its_minimum_in_the_pilot(tmp_path):
    ev = _setup(tmp_path)
    result = upp.plan(ev, 4, 2, 3)
    assert result["per_category"]["C1"]["pilot"] >= 2 and result["per_category"]["C3"]["pilot"] >= 2


def test_the_floor_needs_the_recorded_hash_split_and_enough_test_units(tmp_path):
    ev = _setup(
        tmp_path,
        units={"g01": 6666, "g02": 6667, "g03": 10000},
        partitions={"g03": "first 70 percent of lines for reference, rest for validation"},
    )
    table = upp.group_table(ev)
    assert table["g01"]["floor"] is False  # int(6666 * 0.15) = 999
    assert table["g02"]["floor"] is True  # int(6667 * 0.15) = 1000
    assert table["g03"]["floor"] is None  # another partition: unknown, never met
    assert table["g00"]["exposed"] is True and table["g01"]["exposed"] is False
    assert table["g02"]["cluster"] == table["g03"]["cluster"] == "g02"
    assert table["g04"]["categories"] == ["C1"] and table["g09"]["categories"] == ["C3"]
    assert table["g05"]["domain"] == "d1" and table["g05"]["schema_family"] == "s2"


def test_holdout_adequacy_counts_floor_met_groups_and_clusters(tmp_path):
    ev = _setup(tmp_path, units={g: 100 for g in GROUPS[:6]})
    result = upp.plan(ev, 4, 1, 5)
    holdout = set(result["holdout"])
    table = upp.group_table(ev)
    met = {g for g in holdout if table[g]["floor"]}
    assert result["holdout_clusters"] == len({table[g]["cluster"] for g in holdout})
    assert result["holdout_clusters_floor_met"] == len({table[g]["cluster"] for g in met})
    counted = sum(c["holdout_floor_met"] for c in result["per_category"].values())
    assert counted == len(met)


def test_required_sources_follow_the_design_figures():
    assert {str(k): tf.paired_sources(0.10, 0.05, comparisons=k) for k in (1, 3, 5)} == {
        "1": 34,
        "3": 45,
        "5": 51,
    }
    assert upp.FAMILIES == (1, 3, 5, 11) and (upp.SIGMA, upp.DELTA) == (0.10, 0.05)


def test_build_records_the_proposal_status_one_plan_per_size_and_the_group_table(tmp_path):
    ev = _setup(tmp_path)
    built = upp.build(ev, [3, 4], 1, 9)
    assert built["status"].startswith("proposal")
    assert sorted(built["plans"]) == ["3", "4"] and sorted(built["table"]) == GROUPS
    assert built["plans"]["3"]["required_sources"] == {"1": 34, "3": 45, "5": 51, "11": 59}


def test_main_writes_or_prints_the_same_text_and_needs_every_decision(tmp_path, capsys):
    ev = _setup(tmp_path)
    argv = ["--evidence", str(ev), "--sizes", "3", "--minimum", "1", "--seed", "4"]
    assert upp.main(argv) == 0
    printed = capsys.readouterr().out
    out = tmp_path / "panel.json"
    assert upp.main([*argv, "--output", str(out)]) == 0
    assert out.read_text() == printed and json.loads(printed)["plans"]["3"]["seed"] == 4
    with pytest.raises(SystemExit):
        upp.main(["--evidence", str(ev), "--sizes", "3", "--minimum", "1"])  # no seed


def test_a_plan_is_exactly_the_documented_record(tmp_path):
    ev = _setup(tmp_path)
    assert upp.plan(ev, 4, 1, 7) == {
        "seed": 7,
        "total": 4,
        "minimum": 1,
        "reuse_exposed": False,
        "pilot": ["g01", "g04", "g07", "g10"],
        "holdout": ["g02", "g03", "g05", "g06", "g08", "g09", "g11"],
        "exposed": ["g00"],
        "clusters": {"pilot": 4, "holdout": 6},
        "per_category": {
            "C1": {
                "ready": 8,
                "pilot": 3,
                "holdout": 4,
                "holdout_floor_met": 4,
                "holdout_floor_unknown": 0,
                "exposed_not_confirming": 1,
            },
            "C3": {
                "ready": 4,
                "pilot": 1,
                "holdout": 3,
                "holdout_floor_met": 3,
                "holdout_floor_unknown": 0,
                "exposed_not_confirming": 0,
            },
        },
        "holdout_clusters": 6,
        "holdout_clusters_floor_met": 6,
        "required_sources": {"1": 34, "3": 45, "5": 51, "11": 59},
    }


def test_the_domain_labels_steer_the_draw_as_in_the_batch_pilot(tmp_path):
    ev = _setup(tmp_path)
    registry = json.loads((ev / "readiness.json").read_text())
    links = upp.bs.load_links(ev / "linked_sets.json")
    attributes = json.loads((ev / "source_attributes.json").read_text())
    domains = {g: a["domain"] for g, a in attributes.items()}

    def draw(labels):
        return upp.bs.draw_clustered_pilot(
            registry["ready_groups"],
            [s["groups"] for s in links["linked_sets"]],
            sorted(links["exposed_groups"]),
            4,
            1,
            2,
            labels,
        )["pilot"]

    assert draw(domains) != draw(None)  # seed 2 is one where the labels change the draw
    assert upp.plan(ev, 4, 1, 2)["pilot"] == draw(domains)


def test_exposed_groups_fill_the_pilot_only_when_asked(tmp_path):
    ev = _setup(tmp_path)
    reused = upp.plan(ev, 4, 1, 7, reuse_exposed=True)
    assert reused["reuse_exposed"] is True and "g00" in reused["pilot"]
    assert "g00" not in upp.plan(ev, 4, 1, 7)["pilot"]


def test_a_holdout_group_with_another_partition_is_counted_as_floor_unknown(tmp_path):
    ev = _setup(tmp_path, partitions={"g05": "first 70 percent of lines for reference"})
    c1 = upp.plan(ev, 4, 1, 7)["per_category"]["C1"]
    assert (c1["holdout_floor_met"], c1["holdout_floor_unknown"]) == (3, 1)


def test_the_parser_requires_every_decision_and_defaults_to_the_registry_evidence():
    args = upp.build_parser().parse_args(["--sizes", "16", "24", "--minimum", "2", "--seed", "5"])
    assert args.evidence == upp.EVIDENCE and args.output is None
    assert (args.sizes, args.minimum, args.seed) == ([16, 24], 2, 5)
    full = ["--sizes", "16", "--minimum", "2", "--seed", "5"]
    for flag in ("--sizes", "--minimum", "--seed"):
        at = full.index(flag)
        rest = full[:at] + full[at + 1 :]
        rest = [x for i, x in enumerate(rest) if not (i == at and not x.startswith("--"))]
        with pytest.raises(SystemExit):
            upp.build_parser().parse_args(rest)


def test_main_prints_json_indented_by_one(tmp_path, capsys):
    ev = _setup(tmp_path)
    assert upp.main(["--evidence", str(ev), "--sizes", "3", "--minimum", "1", "--seed", "4"]) == 0
    text = capsys.readouterr().out
    assert text == json.dumps(json.loads(text), indent=1) + "\n"


def test_facts_of_other_groups_repeats_and_a_missing_partition_are_read_correctly(tmp_path):
    ev = _setup(tmp_path)
    facts = json.loads((ev / "readiness_facts.json").read_text())
    registry = json.loads((ev / "readiness.json").read_text())
    first = {"independent_group": "ghost", "protocol_id": "P-TAB", "units": 99999, "min_units": 1}
    repeat = {**facts["facts"]["f4"], "units": 20000}  # g04 again, in C1, with more units
    nopart = {k: v for k, v in facts["facts"]["f5"].items() if k != "partitions"}
    facts["facts"] = {"f0a": first, **facts["facts"], "f4b": repeat, "f5": nopart}
    registry["datasets"] += [{"id": "f0a", "stratum": "C1"}, {"id": "f4b", "stratum": "C1"}]
    (ev / "readiness_facts.json").write_text(json.dumps(facts))
    (ev / "readiness.json").write_text(json.dumps(registry))
    table = upp.group_table(ev)
    assert "ghost" not in table  # not ready in C1: its fact is skipped, later facts still read
    assert table["g04"] == {
        "categories": ["C1"],
        "units": 20000,
        "split": [True],
        "floor": True,
        "domain": "d0",
        "schema_family": "s1",
        "curator": "c",
        "cluster": "g04",
        "exposed": False,
    }
    assert table["g05"]["floor"] is None and table["g05"]["split"] == [False]
    assert table["g00"]["units"] == 10000 and table["g11"]["categories"] == ["C3"]


def test_the_unknown_floor_count_covers_the_holdout_of_the_category_only(tmp_path):
    ev = _setup(tmp_path, partitions={"g05": "other", "g01": "other", "g00": "other"})
    c1 = upp.plan(ev, 4, 1, 7)["per_category"]["C1"]
    assert (c1["holdout"], c1["holdout_floor_unknown"], c1["holdout_floor_met"]) == (4, 1, 3)
