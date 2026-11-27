"""Balanced pilot-panel allocation, panel profile and planning-ratio coverage (design only)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pilot_panel_design as ppd  # noqa: E402
import target_framework as tf  # noqa: E402


def _row(cluster, category, curator, family, domain, floor=True, exposed=False):
    return {
        "categories": [category],
        "floor": floor,
        "domain": domain,
        "schema_family": family,
        "curator": curator,
        "cluster": cluster,
        "exposed": exposed,
    }


def _table():
    table = {}
    for i in range(24):
        category = ("C1", "C2a", "C5")[i % 3]
        table[f"g{i:02d}"] = _row(
            f"g{i:02d}", category, "uci" if i < 12 else f"cur{i}", f"f{i % 6}", f"d{i}"
        )
    table["g99"] = _row("g99", "C1", "x", "f0", "d99", floor=False)
    table["g98"] = _row("g98", "C1", "x", "f0", "d98", exposed=True)
    return table


def test_coverage_of_the_upper_bound_matches_the_independently_reproduced_values():
    expected = {
        (1.4, 16): 0.937,
        (1.55, 16): 0.975,
        (1.7, 16): 0.990,
        (1.4, 12): 0.898,
        (1.55, 12): 0.950,
        (1.7, 12): 0.975,
        (1.4, 8): 0.828,
        (1.55, 8): 0.893,
        (1.7, 8): 0.933,
    }
    for (ratio, n), value in expected.items():
        assert ppd.sd_upper_coverage(n, ratio) == pytest.approx(value, abs=0.0006)


def test_the_two_sided_level_is_below_the_one_sided_coverage_and_matches_the_interval():
    n, ratio = 16, 1.55
    one = ppd.sd_upper_coverage(n, ratio)
    assert ppd.two_sided_level(n, ratio) == pytest.approx(2 * one - 1)
    assert ppd.two_sided_level(n, ratio) < one
    level = ppd.two_sided_level(n, ratio)
    assert tf.sd_ratio_interval(n, level)[1] == pytest.approx(ratio, rel=1e-6)


def test_the_documented_bounds_are_multipliers_of_sigma_hat_not_its_reciprocal():
    low, high = tf.sd_ratio_interval(16, 0.95)
    assert low < 1.0 < high  # sigma / sigma-hat, so high is the planning ratio


def test_water_filling_equalises_then_gives_the_remainder_to_the_roomiest_categories():
    assert ppd.water_fill(16, {"A": 50, "B": 50, "C": 8}) == {"A": 6, "B": 5, "C": 5}
    assert ppd.water_fill(16, {"A": 50, "B": 50, "C": 2}) == {"A": 7, "B": 7, "C": 2}
    assert ppd.water_fill(7, {"A": 10, "B": 20, "C": 20}) == {"A": 2, "B": 3, "C": 2}
    assert ppd.water_fill(3, {"A": 1, "B": 1, "C": 9}) == {"A": 1, "B": 1, "C": 1}


def test_water_filling_rejects_a_size_beyond_the_capacity():
    with pytest.raises(ValueError, match="^size 5 exceeds the capacity 4$"):
        ppd.water_fill(5, {"A": 2, "B": 2})


def test_the_panel_has_the_requested_size_and_only_eligible_clusters():
    panel = ppd.balanced_panel(_table(), 6, seed=7)
    assert len(panel["clusters"]) == 6
    assert "g99" not in panel["groups"] and "g98" not in panel["groups"]
    assert set(panel["quotas"]) == {"C1", "C2a", "C5"}
    assert sum(panel["quotas"].values()) == 6


def test_the_technical_panel_may_use_clusters_below_the_floor():
    panel = ppd.balanced_panel(_table(), 1, seed=7, require_floor=False)
    assert panel["groups"] == ["g99"]
    assert ppd.eligible_clusters(ppd.cluster_table(_table()), require_floor=False) >= {"g99"}
    assert "g98" not in ppd.eligible_clusters(ppd.cluster_table(_table()), require_floor=False)


def test_the_same_seed_gives_the_same_panel_and_the_seed_matters_only_for_ties():
    one = ppd.balanced_panel(_table(), 6, seed=7)
    assert one == ppd.balanced_panel(_table(), 6, seed=7)
    assert one["seed"] == 7


def test_the_curator_cap_is_respected_when_alternatives_exist():
    panel = ppd.balanced_panel(_table(), 9, seed=3, curator_share=0.25)
    curators = ppd.panel_profile(_table(), panel["groups"])["max_per_curator"]
    assert curators <= 3


def test_domains_are_not_repeated_while_unused_domains_remain():
    table = _table()
    for i in range(0, 24, 2):
        table[f"g{i:02d}"]["domain"] = "shared"
    panel = ppd.balanced_panel(table, 6, seed=1)
    profile = ppd.panel_profile(table, panel["groups"])
    assert profile["domains"] >= 5


def test_a_linked_cluster_is_one_unit_with_all_its_categories():
    table = _table()
    table["g01"]["cluster"] = "g00"
    table["g01"]["categories"] = ["C2a"]
    clusters = ppd.cluster_table(table)
    assert clusters["g00"]["groups"] == ["g00", "g01"]
    assert clusters["g00"]["categories"] == ["C1", "C2a"]
    assert "g01" not in clusters


def test_a_cluster_is_exposed_or_below_the_floor_if_any_member_is():
    table = _table()
    table["g01"]["cluster"] = "g00"
    table["g01"]["exposed"] = True
    assert ppd.cluster_table(table)["g00"]["exposed"] is True
    table["g01"]["exposed"] = False
    table["g01"]["floor"] = None
    assert ppd.cluster_table(table)["g00"]["floor"] is None
    table["g01"]["floor"] = False
    assert ppd.cluster_table(table)["g00"]["floor"] is False


def test_the_profile_reports_remaining_floor_meeting_holdout_clusters():
    table = _table()
    panel = ppd.balanced_panel(table, 6, seed=7)
    profile = ppd.panel_profile(table, panel["groups"])
    assert profile["clusters"] == 6
    assert profile["floor_met"] == 6
    assert profile["holdout_clusters"] == 26 - 6 - 1  # g98 is exposed and never confirms
    assert profile["holdout_floor_met"] == 24 - 6
    assert sum(profile["category_clusters"].values()) == 6


def test_required_sources_use_the_upper_ratio_and_the_confirmatory_design_effect():
    base = ppd.required_sources(0.10, 1.55, 3, 1.0)
    assert base == tf.paired_sources(0.155, 0.05, comparisons=3)
    assert ppd.required_sources(0.10, 1.55, 3, 1.3) == tf.paired_sources(
        0.155, 0.05, comparisons=3, design_effect=1.3
    )
    assert ppd.required_sources(0.10, 1.55, 3, 1.3) > base


def _panel_file():
    table = _table()
    plan = {"pilot": ["g00", "g01", "g02", "g03"]}
    return {"table": table, "plans": {"4": plan}}


def test_the_evidence_compares_current_and_balanced_panels_with_capacity_and_stability():
    out = ppd.build(_panel_file(), 5, sizes=(4,))
    panel = out["panels"]["4"]
    assert panel["current"]["clusters"] == 4
    assert panel["balanced"]["clusters"] == 4 and len(panel["balanced"]["quotas"]) == 3
    assert set(panel["seed_stability"]) == {
        "max_per_curator",
        "max_per_schema_family",
        "domains",
        "uci_clusters",
    }
    assert len(panel["required_sources"]) == 3 * 3 * 3 * 2
    assert panel["pilot_upper_ratio_95"] == round(tf.effective_sd_interval(4)[1], 3)
    assert out["technical_validation_panel"]["clusters"] == ["g99"]
    assert {row["effective_n"] for row in out["coverage"]} == {16, 12, 8}


def test_the_command_line_writes_the_evidence_file(tmp_path):
    import json

    (tmp_path / "unit_pilot_panel.json").write_text(json.dumps(_panel_file()))
    target = tmp_path / "out.json"
    # sizes are fixed by the command line, so use a registry that can fill them
    table = {
        f"h{i:02d}": _row(f"h{i:02d}", ("C1", "C2a", "C5")[i % 3], f"c{i}", f"f{i}", f"d{i}")
        for i in range(60)
    }
    plans = {str(n): {"pilot": [f"h{i:02d}" for i in range(n)]} for n in (16, 24, 32)}
    (tmp_path / "unit_pilot_panel.json").write_text(json.dumps({"table": table, "plans": plans}))
    assert ppd.main(["--evidence", str(tmp_path), "--output", str(target)]) == 0
    assert set(json.loads(target.read_text())["panels"]) == {"16", "24", "32"}


def test_historical_overlap_separates_labelled_rows_from_carrier_only_rows():
    table = {"uci:1": _row("uci:1", "C1", "uci", "f", "d"), "g": _row("g", "C1", "z", "f", "d")}
    rows = [
        {"uci_id": 1, "roles": ["carrier", "labelled"]},
        {"uci_id": 2, "roles": ["carrier", "labelled"]},
        {"uci_id": 3, "roles": ["carrier"]},
    ]
    assert ppd.historical_overlap(table, rows) == {"labelled": ["uci:1"], "carrier": []}
    table["uci:3"] = _row("uci:3", "C1", "uci", "f", "d")
    assert ppd.historical_overlap(table, rows)["carrier"] == ["uci:3"]


def test_the_exposure_scenario_marks_groups_without_touching_the_input():
    table = _table()
    marked = ppd.with_exposure(table, ["g00"])
    assert marked["g00"]["exposed"] is True and table["g00"]["exposed"] is False
    assert "g00" not in ppd.balanced_panel(marked, 6, seed=1)["groups"]


def test_the_evidence_reports_the_historical_overlap_with_the_current_panels():
    rows = [{"uci_id": 1, "roles": ["carrier", "labelled"]}]
    panel_file = _panel_file()
    panel_file["table"]["uci:1"] = _row("uci:1", "C1", "uci", "f", "d")
    panel_file["plans"]["4"]["pilot"].append("uci:1")
    out = ppd.build(panel_file, 5, sizes=(4,), pool_rows=rows)
    exposure = out["historical_exposure"]
    assert exposure["labelled_pool_groups"] == ["uci:1"]
    assert exposure["in_current_panels"] == {"4": ["uci:1"]}
    assert exposure["scenario_labelled_groups_also_exposed"]["4"]["clusters"] == 4


def _fixture():
    table = {
        "a1": _row("a1", "C1", "uci", "s1", "d1"),
        "a2": _row("a2", "C1", "uci", "s1", "d2"),
        "a3": _row("a3", "C1", "uci", "s2", "d3"),
        "a4": _row("a4", "C1", "zen", "s3", "d4"),
        "b1": _row("b1", "C2a", "uci", "s4", "d5"),
        "b2": _row("b2", "C2a", "zen", "s4", "d5"),
        "b3": _row("b3", "C2a", "noaa", "s5", "d6", floor=False),
        "c1": _row("c1", "C5", "uci", "s6", "d7"),
        "c2": _row("c2", "C5", "zen", "s6", "d8"),
        "x1": _row("x1", "C5", "zen", "s7", "d9", exposed=True),
        "l1": _row("l1", "C5", "zen", "s8", "d10", floor=None),
        "l2": _row("l1", "C1", "zen", "s8", "d10"),
    }
    return table


def test_the_cluster_table_is_exact_for_a_linked_unknown_floor_cluster():
    clusters = ppd.cluster_table(_fixture())
    assert clusters["l1"] == {
        "categories": ["C1", "C5"],
        "curators": ["zen"],
        "domains": ["d10"],
        "exposed": False,
        "floor": None,
        "groups": ["l1", "l2"],
        "schema_families": ["s8"],
    }
    assert clusters["b3"]["floor"] is False
    assert clusters["x1"]["exposed"] is True and clusters["a1"]["exposed"] is False
    assert clusters["a1"]["schema_families"] == ["s1"] and clusters["a1"]["domains"] == ["d1"]


def test_eligibility_defaults_to_the_floor_and_never_admits_exposed_or_unknown_clusters():
    clusters = ppd.cluster_table(_fixture())
    assert ppd.eligible_clusters(clusters) == {"a1", "a2", "a3", "a4", "b1", "b2", "c1", "c2"}
    assert ppd.eligible_clusters(clusters, require_floor=False) == {
        "a1",
        "a2",
        "a3",
        "a4",
        "b1",
        "b2",
        "b3",
        "c1",
        "c2",
        "l1",
    }


@pytest.mark.parametrize(
    ("size", "quotas", "clusters"),
    [
        (3, {"C1": 1, "C2a": 1, "C5": 1}, ["a3", "b1", "c2"]),
        (4, {"C1": 2, "C2a": 1, "C5": 1}, ["a3", "a4", "b1", "c2"]),
        (6, {"C1": 2, "C2a": 2, "C5": 2}, ["a3", "a4", "b1", "b2", "c1", "c2"]),
    ],
)
def test_the_balanced_panel_is_exact_and_spreads_curators_and_families(size, quotas, clusters):
    panel = ppd.balanced_panel(_fixture(), size, 3)
    assert panel == {
        "seed": 3,
        "size": size,
        "require_floor": True,
        "quotas": quotas,
        "clusters": clusters,
        "groups": clusters,
    }


def test_the_technical_panel_takes_below_floor_clusters_with_all_their_groups():
    panel = ppd.balanced_panel(_fixture(), 2, 3, require_floor=False)
    assert panel["clusters"] == ["b3", "l1"] and panel["groups"] == ["b3", "l1", "l2"]
    assert panel["quotas"] == {"C1": 1, "C2a": 1}
    assert panel["require_floor"] is False


def test_the_profile_is_exact():
    table = _fixture()
    panel = ppd.balanced_panel(table, 4, 3)
    assert ppd.panel_profile(table, panel["groups"]) == {
        "category_clusters": {"C1": 2, "C2a": 1, "C5": 1},
        "clusters": 4,
        "curators": 2,
        "domains": 4,
        "exposed": 0,
        "floor_met": 4,
        "holdout_clusters": 6,
        "holdout_floor_met": 4,
        "holdout_floor_met_by_category": {"C1": 2, "C2a": 1, "C5": 1},
        "max_per_curator": 2,
        "max_per_schema_family": 1,
        "schema_families": 4,
        "uci_clusters": 2,
    }


def test_the_default_curator_cap_is_a_quarter_of_the_panel_and_at_least_two():
    table = {f"u{i}": _row(f"u{i}", "C1", "uci", f"s{i}", f"d{i}") for i in range(6)}
    table |= {f"o{i}": _row(f"o{i}", "C1", f"cur{i}", "fS", "dS") for i in range(6)}
    count = lambda size, **kw: ppd.panel_profile(  # noqa: E731
        table, ppd.balanced_panel(table, size, 1, **kw)["groups"]
    )["uci_clusters"]
    assert count(8) == 2  # ceil(8 x 0.25) = 2
    assert count(8, curator_share=0.5) == 4
    assert count(12, curator_share=0.5) == 6
    assert count(3) == 2  # never below two


def test_a_scarce_category_is_filled_first_and_quotas_follow_the_capacity():
    table = {f"u{i}": _row(f"u{i}", "C1", f"c{i}", f"s{i}", f"d{i}") for i in range(5)}
    table["r1"] = _row("r1", "C6", "c9", "s9", "d9")
    panel = ppd.balanced_panel(table, 4, 2)
    assert panel["quotas"] == {"C1": 2, "C6": 1} or panel["quotas"] == {"C1": 3, "C6": 1}
    assert panel["quotas"]["C6"] == 1 and "r1" in panel["clusters"]
    assert sum(panel["quotas"].values()) == 4


def test_the_summary_and_the_evidence_keys_are_exact():
    assert ppd._summary([1, 5, 3]) == {"min": 1, "median": 3.0, "max": 5}
    out = ppd.build(_panel_file(), 5, sizes=(4,))
    assert set(out) == {"note", "seed", "coverage", "panels", "technical_validation_panel"}
    assert out["seed"] == 5 and out["note"].startswith("design-only")
    assert set(out["panels"]["4"]) == {
        "current",
        "balanced",
        "seed_stability",
        "pilot_upper_ratio_95",
        "required_sources",
    }
    assert out["technical_validation_panel"]["purpose"].startswith("protocol plumbing")
    first = out["panels"]["4"]["required_sources"][0]
    assert first == {
        "sigma_hat": 0.07,
        "ratio": 1.4,
        "comparisons": 1,
        "design_effect": 1.0,
        "sources": ppd.required_sources(0.07, 1.4, 1, 1.0),
        "fits_holdout_floor_met": ppd.required_sources(0.07, 1.4, 1, 1.0)
        <= out["panels"]["4"]["balanced"]["holdout_floor_met"],
    }
    assert out["panels"]["4"]["required_sources"][-1]["fits_holdout_floor_met"] is False
    assert out["coverage"][0] == {
        "effective_n": 16,
        "ratio": 1.4,
        "one_sided": 0.9369,
        "two_sided_level": 0.8739,
    }


def _registry(tmp_path):
    import json

    table = {
        f"h{i:02d}": _row(f"h{i:02d}", ("C1", "C2a", "C5")[i % 3], f"c{i % 9}", f"f{i}", f"d{i}")
        for i in range(60)
    }
    table["uci:7"] = _row("uci:7", "C1", "uci", "fu", "du")
    table["h60"] = _row("h60", "C1", "z", "fz", "dz", floor=False)
    plans = {str(n): {"pilot": [f"h{i:02d}" for i in range(n)]} for n in (16, 24, 32)}
    evidence = tmp_path / "v2"
    evidence.mkdir()
    (evidence / "unit_pilot_panel.json").write_text(json.dumps({"table": table, "plans": plans}))
    (tmp_path / "dataset_registry").mkdir()
    pool = {"rows": [{"uci_id": 7, "roles": ["carrier", "labelled"]}]}
    (tmp_path / "dataset_registry/uci_pool.json").write_text(json.dumps(pool))
    return evidence, table, plans


def test_the_command_line_text_is_the_sorted_indented_build_with_the_pool_overlap(tmp_path, capsys):
    import json

    evidence, table, plans = _registry(tmp_path)
    expected = (
        json.dumps(
            ppd.build(
                {"table": table, "plans": plans},
                20261121,
                pool_rows=[{"uci_id": 7, "roles": ["carrier", "labelled"]}],
            ),
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )
    assert ppd.main(["--evidence", str(evidence)]) == 0
    assert capsys.readouterr().out == expected
    target = tmp_path / "o.json"
    assert ppd.main(["--evidence", str(evidence), "--seed", "5", "--output", str(target)]) == 0
    other = json.loads(target.read_text())
    assert other["seed"] == 5 and other["historical_exposure"]["labelled_pool_groups"] == ["uci:7"]
    assert target.read_text().startswith('{\n "coverage"')


def test_without_the_pool_file_the_evidence_has_no_exposure_section(tmp_path, capsys):
    import json

    evidence, _, _ = _registry(tmp_path)
    (tmp_path / "dataset_registry/uci_pool.json").unlink()
    assert ppd.main(["--evidence", str(evidence)]) == 0
    assert "historical_exposure" not in json.loads(capsys.readouterr().out)


def test_the_evidence_uses_the_given_seed_everywhere_and_the_floor_boundary_is_inclusive():
    out = ppd.build(_panel_file(), 5, sizes=(4,))
    table = _panel_file()["table"]
    assert (
        out["panels"]["4"]["balanced"]["cluster_ids"] == ppd.balanced_panel(table, 4, 5)["clusters"]
    )
    assert out["panels"]["4"]["balanced"]["clusters"] == 4
    assert out["technical_validation_panel"]["clusters"] == ["g99"]
    assert ppd.balanced_panel(table, 1, 5, require_floor=False)["seed"] == 5
    assert out["technical_validation_panel"]["quotas"] == {"C1": 1}
    capacity = out["panels"]["4"]["balanced"]["holdout_floor_met"]
    exact = [r for r in out["panels"]["4"]["required_sources"] if r["sources"] == capacity]
    assert all(r["fits_holdout_floor_met"] for r in exact)


def test_the_exposure_section_lists_carrier_only_groups_and_the_strict_panels():
    rows = [{"uci_id": 1, "roles": ["carrier", "labelled"]}, {"uci_id": 3, "roles": ["carrier"]}]
    panel_file = _panel_file()
    panel_file["table"]["uci:1"] = _row("uci:1", "C1", "uci", "f", "d")
    panel_file["table"]["uci:3"] = _row("uci:3", "C1", "uci", "f", "d")
    exposure = ppd.build(panel_file, 5, sizes=(4,), pool_rows=rows)["historical_exposure"]
    assert exposure["carrier_only_groups"] == ["uci:3"]
    strict = ppd.with_exposure(panel_file["table"], ["uci:1"])
    assert exposure["scenario_labelled_groups_also_exposed"]["4"] == ppd.panel_profile(
        strict, ppd.balanced_panel(strict, 4, 5)["groups"]
    )


def test_the_profile_counts_exposed_clusters_and_uci_clusters_exactly():
    table = {
        "e": _row("e", "C1", "uci", "f", "d", exposed=True),
        "p": _row("p", "C1", "uci", "f2", "d2"),
        "q": _row("q", "C1", "z", "f3", "d3"),
    }
    profile = ppd.panel_profile(table, ["e", "p", "q"])
    assert profile["exposed"] == 1 and profile["uci_clusters"] == 2
    assert ppd.panel_profile(table, ["q"])["uci_clusters"] == 0
