"""Exact tests of the design-only sample-size and coverage calculations."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import target_framework as tf  # noqa: E402


def test_the_normal_approximation_reproduces_the_documented_factor_of_7_85():
    assert tf.normal_factor(0.05, 0.80) == pytest.approx(7.849, abs=0.001)
    assert tf.z_sources(0.10, 0.03) == pytest.approx(
        87.2, abs=0.1
    )  # recorded as 87 in the design decision
    assert tf.z_sources(0.15, 0.05) == pytest.approx(70.7, abs=0.1)  # recorded as 71
    assert tf.z_sources(0.10, 0.03, comparisons=3) > tf.z_sources(0.10, 0.03)


def test_paired_power_grows_with_sources_and_the_smallest_adequate_n_straddles_the_target():
    assert (
        tf.paired_power(10, 0.10, 0.03)
        < tf.paired_power(40, 0.10, 0.03)
        < tf.paired_power(120, 0.10, 0.03)
    )
    n = tf.paired_sources(0.10, 0.03)
    assert tf.paired_power(n, 0.10, 0.03) >= 0.80 > tf.paired_power(n - 1, 0.10, 0.03)
    assert n >= math.ceil(
        tf.z_sources(0.10, 0.03)
    )  # the t distribution needs a few more than the normal
    assert tf.paired_power(n, 0.10, 0.0) == pytest.approx(0.05, abs=1e-9)  # no effect: the level


def test_multiplicity_and_clustering_inflate_the_requirement_and_precision_scales_with_sigma():
    base = tf.paired_sources(0.10, 0.05)
    assert tf.paired_sources(0.10, 0.05, comparisons=6) > base  # Bonferroni level alpha / 6
    assert tf.paired_sources(0.10, 0.05, design_effect=1.5) == math.ceil(base * 1.5)
    assert tf.paired_sources(0.20, 0.05) > 3 * base  # about four times for twice the sigma
    assert tf.design_effect(4, 0.25) == 1.75 and tf.design_effect(1, 0.9) == 1.0
    with pytest.raises(ValueError, match="positive"):
        tf.paired_sources(0.0, 0.05)
    with pytest.raises(ValueError, match="positive"):
        tf.paired_sources(0.1, 0.0)


def test_confidence_interval_sources_meet_the_half_width_and_are_minimal():
    n = tf.ci_sources(0.10, 0.03)
    t = tf.t_quantile(0.975, n - 1)
    assert t * 0.10 / math.sqrt(n) <= 0.03 < tf.t_quantile(0.975, n - 2) * 0.10 / math.sqrt(n - 1)
    assert tf.ci_sources(0.10, 0.03, design_effect=2.0) == math.ceil(n * 2.0)
    assert tf.ci_sources(0.10, 0.03, level=0.99) > n


def test_the_sensitivity_grid_lists_every_combination_in_a_fixed_order_with_both_methods():
    grid = tf.sensitivity_grid(sigmas=[0.05, 0.10], deltas=[0.03, 0.05], comparisons=[1, 3])
    assert [(r["sigma"], r["delta"], r["comparisons"]) for r in grid[:3]] == [
        (0.05, 0.03, 1),
        (0.05, 0.03, 3),
        (0.05, 0.05, 1),
    ]
    assert len(grid) == 8
    row = grid[0]
    assert row["z_sources"] == pytest.approx(tf.z_sources(0.05, 0.03), abs=1e-9)
    assert row["t_sources"] == tf.paired_sources(0.05, 0.03) and row[
        "ci_sources_half_width_delta"
    ] == tf.ci_sources(0.05, 0.03)
    assert grid[-1]["t_sources"] == tf.paired_sources(0.10, 0.05, comparisons=3)


def test_effective_groups_discount_clustered_sources_by_the_assumed_icc():
    assert tf.effective_groups([1, 1, 1], 0.5) == 3.0  # singletons keep their weight
    assert tf.effective_groups([4], 0.5) == pytest.approx(4 / 2.5)  # one cluster of four, icc 0.5
    assert tf.effective_groups([4], 0.0) == 4.0 and tf.effective_groups([4], 1.0) == 1.0
    assert tf.effective_groups([12, 1, 1], 0.2) == pytest.approx(12 / (1 + 11 * 0.2) + 2)
    assert tf.effective_groups([], 0.5) == 0.0


def test_simulation_shows_that_ignoring_domain_clustering_inflates_false_positives():
    kwargs = dict(domains=6, per_domain=5, sigma_domain=0.08, sigma_source=0.05, reps=1500, seed=7)
    naive_null, cluster_null = tf.simulate_rejection(delta=0.0, **kwargs)
    assert naive_null > 0.10  # a source-level test on clustered data rejects far above 5 percent
    assert cluster_null < 0.09  # the domain-level analysis keeps the level near 5 percent
    again = tf.simulate_rejection(delta=0.0, **kwargs)
    assert again == (naive_null, cluster_null)  # seeded: identical
    naive_alt, cluster_alt = tf.simulate_rejection(delta=0.10, **kwargs)
    assert naive_alt > cluster_alt  # the cluster analysis pays for its validity with power


def test_the_coverage_summary_counts_distinct_levels_per_category_and_discounts_shared_schemas():
    attributes = {
        "a": {"domain": "transport", "producer": "p1", "curator": "c1", "schema_family": "gtfs", "generating_system": "s1"},  # noqa: E501
        "b": {"domain": "transport", "producer": "p2", "curator": "c1", "schema_family": "gtfs", "generating_system": "s2"},  # noqa: E501
        "c": {"domain": "health", "producer": "p3", "curator": "c2", "schema_family": "xes", "generating_system": "s3"},  # noqa: E501
        "d": {"domain": "health", "producer": "p4", "curator": "c2", "schema_family": "xes", "generating_system": "s4"},  # noqa: E501
    }  # fmt: skip
    ready = {"C5": ["a", "b", "c"], "C4": ["c", "d"]}
    out = tf.coverage_summary(attributes, ready, icc=0.5)
    assert out["C5"] == {"groups": 3, "domains": 2, "producers": 3, "curators": 2, "schema_families": 2,  # noqa: E501
                         "largest_schema_family_share": round(2 / 3, 4), "effective_groups": round(2 / 1.5 + 1, 4)}  # fmt: skip  # noqa: E501
    assert (
        out["C4"]["groups"] == 2
        and out["C4"]["schema_families"] == 1
        and out["C4"]["effective_groups"] == round(2 / 1.5, 4)
    )
    assert (
        out["ALL"]["groups"] == 4 and out["ALL"]["domains"] == 2
    )  # distinct groups over all categories
    with pytest.raises(KeyError):
        tf.coverage_summary(attributes, {"C3": ["zzz"]}, icc=0.5)


def test_the_report_has_the_documented_tables_and_main_writes_it_next_to_its_inputs(tmp_path):
    import json

    attributes = {
        "a": {"domain": "d1", "producer": "p1", "curator": "c1", "schema_family": "s1", "generating_system": "g1", "structure": {"C3": "f1"}},  # noqa: E501
        "b": {"domain": "d2", "producer": "p2", "curator": "c2", "schema_family": "s1", "generating_system": "g2", "structure": {"C3": "f2"}},  # noqa: E501
    }  # fmt: skip
    (tmp_path / "source_attributes.json").write_text(json.dumps(attributes))
    (tmp_path / "readiness.json").write_text(json.dumps({"ready_groups": {"C3": ["a", "b"]}}))
    assert tf.main(["--dir", str(tmp_path), "--reps", "40"]) == 0
    out = json.loads((tmp_path / "target_framework.json").read_text())
    assert len(out["sensitivity"]) == len(tf.SIGMAS) * len(tf.DELTAS) * len(tf.COMPARISONS) == 48
    assert out["coverage"]["0.5"]["C3"]["effective_groups"] == round(2 / 1.5, 4)
    assert out["coverage"]["0.2"]["ALL"]["groups"] == 2 and len(out["design_effect_sources"]) == 9
    assert out["note"].startswith("design-only")
    assert [r["domains"] for r in out["simulation"]] == [6, 10, 10]
    assert (
        out["simulation"][0]["null_rejection_source_level"]
        > out["simulation"][2]["null_rejection_source_level"]
    )
    row = next(
        r for r in out["design_effect_sources"] if r["cluster_size"] == 4 and r["icc"] == 0.5
    )
    assert row["design_effect"] == 2.5 and row["sources"] == tf.paired_sources(
        0.10, 0.05, design_effect=2.5
    )


def test_the_minimum_detectable_difference_inverts_the_power_calculation():
    delta = tf.minimum_detectable_delta(34, 0.10)
    assert tf.paired_power(34, 0.10, delta) >= 0.80
    assert tf.paired_power(34, 0.10, delta - 0.0005) < 0.80
    assert (
        0.045 < delta < 0.055
    )  # 34 sources detect about 0.05 at sigma 0.10 (see the sensitivity grid)
    assert tf.minimum_detectable_delta(34, 0.20) == pytest.approx(
        2 * delta, abs=0.002
    )  # scales with sigma
    assert tf.minimum_detectable_delta(10, 0.10) > tf.minimum_detectable_delta(34, 0.10)
    with pytest.raises(ValueError, match="at least 2"):
        tf.minimum_detectable_delta(1, 0.10)


def test_power_is_one_for_a_huge_standardised_effect_and_the_routines_never_return_nan():
    assert tf.paired_power(100, 0.01, 1.0) == 1.0
    assert 0.0 <= tf.paired_power(3, 1.0, 0.001) <= 1.0


def test_required_sources_match_the_recorded_values_for_several_parameter_sets():
    assert [tf.paired_sources(0.10, 0.05, comparisons=k) for k in (1, 3, 6)] == [34, 45, 52]
    assert tf.paired_sources(0.05, 0.03) == 24 and tf.paired_sources(0.10, 0.03) == 90
    assert (
        tf.paired_sources(0.05, 0.10) == 5
    )  # the exact t calculation does not go below the normal one by much
    assert tf.paired_sources(0.20, 0.03, alpha=0.01, power=0.9) == 665
    assert tf.ci_sources(0.10, 0.03) == 46 and tf.ci_sources(0.05, 0.03) == 14
    assert tf.ci_sources(0.10, 0.03, level=0.99) == 78 and tf.ci_sources(0.30, 0.20) == 12
    assert tf.z_sources(0.1, 0.03, alpha=0.01, power=0.9, comparisons=2) == pytest.approx(
        185.739, abs=0.001
    )
    assert tf.normal_factor(0.01, 0.9) == pytest.approx(14.879, abs=0.001)


def test_power_values_the_level_and_the_degenerate_sizes_are_exact():
    assert tf.paired_power(25, 0.1, 0.05) == pytest.approx(0.6697, abs=0.0001)
    assert tf.paired_power(25, 0.1, 0.05, alpha=0.01) == pytest.approx(0.4023, abs=0.0001)
    assert tf.paired_power(2, 0.1, 0.05) == pytest.approx(0.0619, abs=0.0001)
    assert tf.paired_power(1, 0.1, 0.05) == 0.0 and tf.paired_power(0, 0.1, 0.05) == 0.0


def test_minimum_detectable_delta_matches_recorded_values_and_accepts_fractional_sizes():
    assert tf.minimum_detectable_delta(34, 0.10) == 0.0496
    assert tf.minimum_detectable_delta(10, 0.05) == 0.0499
    assert tf.minimum_detectable_delta(34.9, 0.10) == 0.0496  # a fractional size is floored
    assert tf.minimum_detectable_delta(25, 0.10, alpha=0.01, power=0.9) == 0.083
    with pytest.raises(ValueError) as error:
        tf.minimum_detectable_delta(1.9, 0.1)
    assert str(error.value) == "at least 2 sources are needed"
    assert tf.minimum_detectable_delta(2, 0.1) > 0.5  # two sources detect only a huge difference
    with pytest.raises(ValueError) as error:
        tf.paired_sources(-1, 0.1)
    assert str(error.value) == "sigma and delta must be positive"


def test_the_seeded_simulation_returns_the_recorded_rates_for_a_null_and_an_effect():
    assert tf.simulate_rejection(5, 4, 0.05, 0.05, 0.0, 300, 3) == (0.2133, 0.0433)
    assert tf.simulate_rejection(5, 4, 0.05, 0.05, 0.08, 300, 3) == (0.9567, 0.63)
    assert tf.simulate_rejection(5, 4, 0.05, 0.05, 0.0, 300, 3, alpha=0.01)[0] < 0.2133


def test_the_report_lists_the_documented_design_effect_grid_and_simulation_settings(tmp_path):
    import json

    attributes = {
        "a": {
            "domain": "d",
            "producer": "p",
            "curator": "c",
            "schema_family": "s",
            "generating_system": "g",
            "structure": {"C3": "f"},
        }
    }
    out = tf.report(attributes, {"ready_groups": {"C3": ["a"]}}, reps=40)
    assert sorted(out) == [
        "coverage",
        "design_effect_sources",
        "diversity",
        "effect_requirements",
        "minimum_detectable_delta",
        "note",
        "pilot_sd_precision",
        "sensitivity",
        "simulation",
    ]
    assert [(r["cluster_size"], r["icc"]) for r in out["design_effect_sources"]] == [
        (m, i) for m in (2, 4, 8) for i in (0.0, 0.2, 0.5)
    ]
    assert all(r["sigma"] == 0.10 and r["delta"] == 0.05 for r in out["design_effect_sources"])
    assert (
        out["design_effect_sources"][0]["sources"] == 34
        and out["design_effect_sources"][-1]["sources"] == 153
    )
    assert [(r["domains"], r["per_domain"], r["sigma_domain"]) for r in out["simulation"]] == [
        (6, 5, 0.08),
        (10, 3, 0.08),
        (10, 3, 0.02),
    ]
    assert [(r["sources"], r["sigma"]) for r in out["minimum_detectable_delta"]][:4] == [
        (10, 0.05),
        (10, 0.1),
        (10, 0.15),
        (18, 0.05),
    ]
    assert out["minimum_detectable_delta"][4]["delta"] == 0.0701
    assert sorted(out["coverage"]) == ["0.2", "0.5"] and out["note"] == "design-only: every sigma, delta and icc below is hypothetical; no detector was run"  # fmt: skip  # noqa: E501
    (tmp_path / "source_attributes.json").write_text(json.dumps(attributes))
    (tmp_path / "readiness.json").write_text(json.dumps({"ready_groups": {"C3": ["a"]}}))
    assert tf.main(["--dir", str(tmp_path), "--reps", "40"]) == 0
    text = (tmp_path / "target_framework.json").read_text()
    assert (
        text.endswith("}\n")
        and text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    )


def test_main_prints_the_row_count_and_group_count(tmp_path, capsys):
    import json

    (tmp_path / "source_attributes.json").write_text(
        json.dumps(
            {
                "a": {
                    "domain": "d",
                    "producer": "p",
                    "curator": "c",
                    "schema_family": "s",
                    "generating_system": "g",
                    "structure": {"C3": "f"},
                }
            }
        )
    )
    (tmp_path / "readiness.json").write_text(json.dumps({"ready_groups": {"C3": ["a"]}}))
    tf.main(["--dir", str(tmp_path), "--reps", "40"])
    assert capsys.readouterr().out == "48 sensitivity rows, coverage of 1 groups\n"


def test_coverage_summary_handles_an_empty_category_and_uses_the_largest_family_share():
    attributes = {
        "a": {
            "domain": "d",
            "producer": "p",
            "curator": "c",
            "schema_family": "s",
            "generating_system": "g",
            "structure": {"C3": "f"},
        }
    }
    out = tf.coverage_summary(attributes, {"C1": [], "C3": ["a"]}, icc=0.3)
    assert out["C1"] == {"groups": 0, "domains": 0, "producers": 0, "curators": 0, "schema_families": 0,  # noqa: E501
                         "largest_schema_family_share": 0.0, "effective_groups": 0.0}  # fmt: skip
    assert out["C3"]["largest_schema_family_share"] == 1.0 and out["ALL"]["groups"] == 1


def test_ci_sources_start_from_two_and_step_by_one():
    assert tf.ci_sources(0.01, 1.0) == 2  # a tiny sigma needs only two sources
    assert (
        tf.ci_sources(0.10, 0.04) == 27 and tf.ci_sources(0.2, 0.07) == 34
    )  # odd and even results


def test_the_grid_applies_the_number_of_comparisons_to_the_normal_approximation_too():
    grid = tf.sensitivity_grid(sigmas=[0.10], deltas=[0.05], comparisons=[1, 3])
    assert grid[1]["z_sources"] == pytest.approx(tf.z_sources(0.10, 0.05, comparisons=3), abs=1e-9)
    assert grid[1]["z_sources"] > grid[0]["z_sources"]


def test_the_report_pins_its_simulation_and_minimum_detectable_grids():
    attributes = {
        "a": {
            "domain": "d",
            "producer": "p",
            "curator": "c",
            "schema_family": "s",
            "generating_system": "g",
            "structure": {"C3": "f"},
        }
    }
    out = tf.report(attributes, {"ready_groups": {"C3": ["a"]}})
    rows = [(r["domains"], r["per_domain"], r["sigma_domain"], r["null_rejection_source_level"], r["null_rejection_domain_level"]) for r in out["simulation"]]  # fmt: skip  # noqa: E501
    assert rows == [
        (6, 5, 0.08, 0.3595, 0.048),
        (10, 3, 0.08, 0.219, 0.0525),
        (10, 3, 0.02, 0.085, 0.0505),
    ]
    assert [r["sources"] for r in out["minimum_detectable_delta"]][::3] == [10, 18, 25, 34, 49, 73]
    by = {(r["sources"], r["sigma"]): r["delta"] for r in out["minimum_detectable_delta"]}
    assert (
        by[(25, 0.05)] == 0.0293
        and by[(25, 0.15)] == 0.0877
        and by[(49, 0.05)] == 0.0205
        and by[(49, 0.15)] == 0.0613
    )
    assert (
        len(out["minimum_detectable_delta"]) == 18
        and out["coverage"]["0.2"]["C3"]["effective_groups"] == 1.0
    )


def test_main_without_arguments_uses_the_evidence_folder_next_to_the_package_and_describes_itself(
    tmp_path, monkeypatch, capsys
):
    import json

    folder = tmp_path / "verification" / "evidence" / "dataset_registry_v2"
    folder.mkdir(parents=True)
    (folder / "source_attributes.json").write_text(
        json.dumps(
            {
                "a": {
                    "domain": "d",
                    "producer": "p",
                    "curator": "c",
                    "schema_family": "s",
                    "generating_system": "g",
                    "structure": {"C3": "f"},
                }
            }
        )
    )
    (folder / "readiness.json").write_text(json.dumps({"ready_groups": {"C3": ["a"]}}))
    (tmp_path / "research").mkdir()
    monkeypatch.setattr(tf, "__file__", str(tmp_path / "research" / "target_framework.py"))
    assert tf.main(["--reps", "40"]) == 0
    assert (folder / "target_framework.json").exists()
    with pytest.raises(SystemExit):
        tf.main(["--help"])
    help_text = capsys.readouterr().out
    assert "Design-only calculations" in help_text and "--dir DIR" in help_text


def test_holm_adjustment_is_step_down_monotone_and_capped_at_one():
    p = [0.01, 0.04, 0.03, 0.20]
    assert tf.holm_adjust(p) == [
        0.04,
        0.09,
        0.09,
        0.2,
    ]  # sorted 0.01*4, 0.03*3, 0.04*2 -> monotone, 0.20*1
    assert tf.holm_adjust([0.5, 0.6]) == [1.0, 1.0]
    assert tf.holm_adjust([0.2]) == [0.2] and tf.holm_adjust([]) == []
    assert tf.holm_adjust([0.30, 0.001]) == [0.3, 0.002]  # order of the input is kept
    with pytest.raises(ValueError, match="between 0 and 1"):
        tf.holm_adjust([1.5])
    with pytest.raises(ValueError, match="between 0 and 1"):
        tf.holm_adjust([-0.1])
    assert tf.holm_rejections([0.01, 0.04, 0.03, 0.20], alpha=0.05) == [True, False, False, False]
    assert tf.holm_rejections([0.001, 0.01], alpha=0.05) == [True, True]


def test_a_relative_reduction_is_planned_on_the_log_ratio_scale():
    assert tf.log_ratio_delta(0.2) == pytest.approx(0.22314, abs=1e-5)  # ln(1 / 0.8)
    assert tf.log_ratio_delta(0.5) == pytest.approx(0.69315, abs=1e-5)
    with pytest.raises(ValueError, match="between 0 and 1"):
        tf.log_ratio_delta(1.0)
    with pytest.raises(ValueError, match="between 0 and 1"):
        tf.log_ratio_delta(0.0)


def test_the_sd_confidence_ratio_shrinks_with_the_number_of_pilot_sources():
    low, high = tf.sd_ratio_interval(24)
    assert (round(low, 3), round(high, 3)) == (0.777, 1.403)
    assert tf.sd_ratio_interval(10) == (
        pytest.approx(0.688, abs=0.001),
        pytest.approx(1.826, abs=0.001),
    )
    assert tf.sd_ratio_interval(48)[1] < tf.sd_ratio_interval(24)[1] < tf.sd_ratio_interval(10)[1]
    n = tf.pilot_sources_for_sd(1.40)
    assert tf.sd_ratio_interval(n)[1] <= 1.40 < tf.sd_ratio_interval(n - 1)[1]
    assert tf.pilot_sources_for_sd(1.40, level=0.80) < n
    with pytest.raises(ValueError, match="above 1"):
        tf.pilot_sources_for_sd(1.0)


def test_the_effect_scenarios_cover_the_approved_smallest_effects():
    names = [s["metric"] for s in tf.EFFECT_SCENARIOS]
    assert names == [
        "recall at matched alert budget",
        "AUPRC",
        "AUROC",
        "false-positive burden",
        "cost",
    ]
    by = {s["metric"]: s for s in tf.EFFECT_SCENARIOS}
    assert (
        by["AUROC"]["delta"] == 0.02
        and by["AUPRC"]["delta"] == 0.05
        and by["recall at matched alert budget"]["delta"] == 0.05
    )
    assert (
        by["false-positive burden"]["relative_reduction"] == 0.20
        and by["cost"]["relative_reduction"] == 0.20
    )
    table = tf.effect_requirements(sigmas=[0.02, 0.05, 0.10])
    row = next(r for r in table if r["metric"] == "AUROC" and r["sigma"] == 0.02)
    assert row["delta"] == 0.02 and row["sources_k1"] == tf.paired_sources(0.02, 0.02)
    assert row["sources_holm_k6"] == tf.paired_sources(0.02, 0.02, comparisons=6)
    rel = next(r for r in table if r["metric"] == "cost" and r["sigma"] == 0.10)
    assert rel["delta"] == pytest.approx(0.22314, abs=1e-5) and rel["scale"] == "log ratio"
    assert len(table) == 5 * 3


def _attrs(groups):
    return {
        g: {"domain": d, "producer": g, "curator": "c", "schema_family": "s", "generating_system": g, "structure": {"C3": f}}  # noqa: E501
        for g, d, f in groups
    }  # fmt: skip


def test_the_diversity_report_counts_domains_and_families_and_applies_the_approved_guardrails():
    attributes = _attrs(
        [
            ("a", "d1", "f1"),
            ("b", "d2", "f1"),
            ("c", "d3", "f2"),
            ("e", "d4", "f2"),
            ("g", "d5", "f3"),
        ]
    )
    out = tf.diversity_report(attributes, {"C3": ["a", "b", "c"]})
    c3 = out["C3"]
    assert c3 == {
        "groups": 3, "target": 40, "gap": 37, "domains": 3, "families": 2,
        "largest_family": "f1", "largest_family_share": round(2 / 3, 4),
        "unclassified_groups": 0, "exploratory": True, "quota": False, "diversity": False,
        "missing": ["groups: 3 of 40", "domains: 3 of 5", "families: 2 of 3"],
    }  # fmt: skip
    full = tf.diversity_report(attributes, {"C3": ["a", "b", "c", "e", "g"]}, targets={"C3": 5})
    assert (
        full["C3"]["quota"] is True
        and full["C3"]["diversity"] is True
        and full["C3"]["missing"] == []
    )
    assert full["C3"]["gap"] == 0
    thin = tf.diversity_report(attributes, {"C3": ["a", "b"]})["C3"]
    assert thin["exploratory"] is False  # two domains and one family


def test_the_diversity_report_uses_the_per_category_family_minima_and_ignores_unlisted_categories():
    attributes = _attrs(
        [
            ("a", "d1", "f1"),
            ("b", "d2", "f2"),
            ("c", "d3", "f3"),
            ("e", "d4", "f4"),
            ("g", "d5", "f5"),
        ]
    )
    for g in attributes.values():
        g["structure"]["C5"] = g["structure"]["C3"]
    ready = {"C3": ["a", "b", "c", "e", "g"], "C5": ["a", "b", "c", "e", "g"]}
    out = tf.diversity_report(attributes, ready, targets={"C3": 5, "C5": 5})
    assert tf.MINIMA["C5"] == (5, 4) and tf.MINIMA["C3"] == (5, 3) and tf.MINIMA["C2b"] == (5, 4)
    assert (
        tf.MINIMA["C1"] == (5, 3)
        and tf.MINIMA["C2a"] == (5, 3)
        and tf.MINIMA["C4"] == (5, 3)
        and tf.MINIMA["C6"] == (5, 4)
    )
    assert out["C3"]["diversity"] is True and out["C5"]["diversity"] is True
    assert tf.TARGETS == {"C1": 36, "C2a": 30, "C2b": 30, "C3": 40, "C4": 28, "C5": 36, "C6": 30}
    assert sum(tf.TARGETS.values()) == 230
    assert tf.diversity_report(attributes, {}) == {}
    with pytest.raises(KeyError):
        tf.diversity_report(attributes, {"C4": ["a"]})  # the group has no C4 structure


def test_holm_and_effect_helpers_match_recorded_values():
    assert tf.holm_adjust([0.01, 0.02, 0.03]) == [0.03, 0.04, 0.04]
    assert tf.holm_adjust([0.5, 0.01, 0.2, 0.04]) == [0.5, 0.04, 0.4, 0.12]
    assert tf.holm_adjust([0.0, 1.0]) == [0.0, 1.0] and tf.holm_adjust([0.2, 0.2]) == [0.4, 0.4]
    assert tf.holm_rejections([0.012, 0.02, 0.5], alpha=0.05) == [True, True, False]
    assert tf.holm_rejections([0.0125, 0.0125], alpha=0.05) == [True, True]
    assert tf.holm_rejections([0.0125, 0.0125], alpha=0.02) == [False, False]
    assert tf.log_ratio_delta(0.1) == pytest.approx(0.105361, abs=1e-6) and tf.log_ratio_delta(
        0.9
    ) == pytest.approx(2.302585, abs=1e-6)


def test_pilot_precision_and_interval_values_are_recorded():
    assert [tf.pilot_sources_for_sd(r, lv) for r in (1.25, 1.40, 1.60) for lv in (0.80, 0.95)] == [
        24,
        49,
        13,
        25,
        8,
        15,
    ]
    low, high = tf.sd_ratio_interval(10, 0.90)
    assert (round(low, 4), round(high, 4)) == (0.7293, 1.6452)
    low, high = tf.sd_ratio_interval(3)
    assert (round(low, 4), round(high, 4)) == (0.5207, 6.2847)


def test_effect_requirements_rows_are_exact_and_ordered_by_scenario_then_sigma():
    rows = tf.effect_requirements([0.05])
    assert rows[0] == {"metric": "recall at matched alert budget", "scale": "absolute", "sigma": 0.05, "delta": 0.05,  # noqa: E501
                       "sources_k1": 10, "sources_holm_k3": 14, "sources_holm_k6": 16}  # fmt: skip
    assert rows[2]["metric"] == "AUROC" and rows[2]["delta"] == 0.02 and (rows[2]["sources_k1"], rows[2]["sources_holm_k3"], rows[2]["sources_holm_k6"]) == (52, 69, 80)  # fmt: skip  # noqa: E501
    assert [r["metric"] for r in rows] == [
        "recall at matched alert budget",
        "AUPRC",
        "AUROC",
        "false-positive burden",
        "cost",
    ]
    assert (
        rows[3]["scale"] == "log ratio" and rows[3]["sources_k1"] == 3 and rows[3]["sigma"] == 0.05
    )


def test_sample_size_options_alpha_power_comparisons_and_design_effect_each_change_the_result():
    assert tf.paired_sources(0.1, 0.1, alpha=0.1, power=0.9) == 11
    assert tf.paired_sources(0.3, 0.1, comparisons=2) == 89
    assert tf.paired_sources(0.1, 0.05, design_effect=2.0) == 68
    assert tf.paired_sources(0.1, 0.05, power=0.9) == 44
    assert tf.paired_sources(0.1, 0.05) == 34
    assert (
        tf.minimum_detectable_delta(5, 0.1) == 0.1682
        and tf.minimum_detectable_delta(100, 0.1) == 0.0283
    )
    assert (
        tf.minimum_detectable_delta(34, 0.1, alpha=0.1) == 0.0436
        and tf.minimum_detectable_delta(34, 0.1, power=0.9) == 0.0573
    )
    assert tf.paired_power(10, 0.1, 0.05, alpha=0.1) == pytest.approx(0.4282, abs=0.0001)
    assert (
        tf.paired_power(10, 0.1, -0.05) == tf.paired_power(10, 0.1, 0.05)
        or abs(tf.paired_power(10, 0.1, -0.05) - tf.paired_power(10, 0.1, 0.05)) < 1e-9
    )  # noqa: E501
    assert tf.paired_power(3, 0.5, 0.4) == pytest.approx(0.1349, abs=0.0001)


def test_diversity_report_covers_several_categories_in_sorted_order_with_exact_fields():
    attributes = {
        "a": {"domain": "d1", "structure": {"C3": "f1", "C4": "g1"}},
        "b": {"domain": "d2", "structure": {"C3": "f1", "C4": "g2"}},
        "c": {"domain": "d2", "structure": {"C3": "f2"}},
    }
    out = tf.diversity_report(
        attributes, {"C4": ["a", "b"], "C3": ["a", "b", "c"]}, targets={"C3": 3, "C4": 4}
    )
    assert list(out) == ["C3", "C4"]
    assert out["C3"] == {"groups": 3, "target": 3, "gap": 0, "domains": 2, "families": 2, "largest_family": "f1",  # noqa: E501
                         "largest_family_share": round(2 / 3, 4), "unclassified_groups": 0, "exploratory": False, "quota": True,  # noqa: E501
                         "diversity": False, "missing": ["domains: 2 of 5", "families: 2 of 3"]}  # fmt: skip  # noqa: E501
    assert (
        out["C4"]["gap"] == 2
        and out["C4"]["quota"] is False
        and out["C4"]["largest_family_share"] == 0.5
    )
    exact = tf.diversity_report(
        {f"g{i}": {"domain": f"d{i}", "structure": {"C3": f"f{i % 3}"}} for i in range(5)},
        {"C3": [f"g{i}" for i in range(5)]}, targets={"C3": 5},
    )["C3"]  # fmt: skip
    assert exact["exploratory"] is True and exact["diversity"] is True and exact["missing"] == []
    three = tf.diversity_report({f"g{i}": {"domain": f"d{i % 3}", "structure": {"C3": f"f{i % 2}"}} for i in range(4)},  # noqa: E501
                                {"C3": [f"g{i}" for i in range(4)]})["C3"]  # fmt: skip
    assert (
        three["exploratory"] is True
    )  # exactly 3 domains and 2 families is enough for the exploratory tier


def test_the_report_has_every_documented_section_with_exact_row_counts():
    attributes = {"a": {"domain": "d", "producer": "p", "curator": "c", "schema_family": "s", "generating_system": "g", "structure": {"C3": "f"}}}  # fmt: skip  # noqa: E501
    out = tf.report(attributes, {"ready_groups": {"C3": ["a"]}}, reps=30)
    assert len(out["effect_requirements"]) == 15 and len(out["pilot_sd_precision"]) == 6
    assert out["pilot_sd_precision"][0] == {
        "max_upper_ratio": 1.25,
        "level": 0.80,
        "pilot_sources": 24,
    }
    assert out["pilot_sd_precision"][-1] == {
        "max_upper_ratio": 1.60,
        "level": 0.95,
        "pilot_sources": 15,
    }
    assert out["diversity"]["C3"]["groups"] == 1 and out["sensitivity"][0]["sigma"] == 0.05
    assert tf.SIGMAS == [0.05, 0.10, 0.15, 0.20] and tf.DELTAS == [0.02, 0.03, 0.05, 0.10] and tf.COMPARISONS == [1, 3, 6] and tf.ICCS == [0.0, 0.2, 0.5]  # fmt: skip  # noqa: E501
    assert [r["domains"] for r in out["simulation"]] == [6, 10, 10] and out["simulation"][0][
        "per_domain"
    ] == 5


def test_holm_edge_cases_error_text_cap_and_inclusive_alpha():
    with pytest.raises(ValueError) as error:
        tf.holm_adjust([2.0])
    assert str(error.value) == "p-values must be between 0 and 1"
    assert tf.holm_adjust([0.8, 0.9]) == [1.0, 1.0] and tf.holm_adjust([0.9, 0.8]) == [1.0, 1.0]
    assert tf.holm_adjust([0.7, 0.9, 0.95]) == [1.0, 1.0, 1.0]
    assert tf.holm_rejections([0.05], alpha=0.05) == [True] and tf.holm_rejections(
        [0.0501], alpha=0.05
    ) == [False]
    assert tf.holm_rejections([]) == []
    assert tf.holm_adjust([0.0, 0.0]) == [0.0, 0.0]
    with pytest.raises(ValueError) as error:
        tf.log_ratio_delta(-0.2)
    assert str(error.value) == "a relative reduction must be between 0 and 1"


def test_the_ci_level_default_is_ninety_five_percent_and_the_search_starts_at_two_sources():
    assert tf.ci_sources(0.10, 0.03) == tf.ci_sources(0.10, 0.03, level=0.95)
    assert tf.ci_sources(0.10, 0.03, level=0.90) < tf.ci_sources(0.10, 0.03)
    assert tf.paired_sources(0.1, 100.0) == 2  # a huge effect needs only the minimum of two sources
    assert (
        tf.paired_sources(0.1, 0.5) >= 3
    )  # three sources are needed for the usual level at this effect
    assert tf.ci_sources(0.1, 100.0) == 2


def test_unclassified_domains_and_families_are_not_counted_but_the_groups_are_reported():
    attributes = {
        "a": {"domain": "Other", "structure": {"C1": "other"}},
        "b": {"domain": "d1", "structure": {"C1": "f1"}},
        "c": {"domain": "d1", "structure": {"C1": "other"}},
        "e": {"domain": "unknown", "structure": {"C1": "f2"}},
    }
    out = tf.diversity_report(attributes, {"C1": ["a", "b", "c", "e"]}, targets={"C1": 4})["C1"]
    assert out["domains"] == 1 and out["families"] == 2 and out["groups"] == 4
    assert (
        out["unclassified_groups"] == 3
        and out["largest_family"] == "f1"
        and out["largest_family_share"] == 0.25
    )
    assert {"Other", "unknown", "other"} == tf.UNCLASSIFIED


def test_the_sd_interval_widens_when_clustering_reduces_the_effective_number_of_sources():
    plain = tf.sd_ratio_interval(24)
    same = tf.effective_sd_interval(24, design_effect=1.0)
    assert same == plain
    clustered = tf.effective_sd_interval(24, design_effect=1.6)  # 15 effective sources
    assert clustered == tf.sd_ratio_interval(15) and clustered[1] > plain[1]
    assert tf.effective_sd_interval(24, design_effect=100.0) == tf.sd_ratio_interval(
        2
    )  # never fewer than two
    with pytest.raises(ValueError, match="at least 1"):
        tf.effective_sd_interval(24, design_effect=0.5)


def test_pilot_allocation_caps_each_category_at_a_share_of_its_ready_groups_and_a_minimum():
    ready = {"A": 20, "B": 10, "C": 6}
    out = tf.pilot_allocation(ready, minimum=2, max_share=0.25, total_cap=10)
    assert out == {
        "A": 5,
        "B": 2,
        "C": 2,
    }  # 25 percent of 20 is 5; 2.5 and 1.5 round down to the minimum of 2
    assert tf.pilot_allocation(ready, minimum=3, max_share=0.25, total_cap=10) == {
        "A": 4,
        "B": 3,
        "C": 3,
    }
    assert tf.pilot_allocation(ready, minimum=3, max_share=0.25, total_cap=11) == {
        "A": 5,
        "B": 3,
        "C": 3,
    }
    capped = tf.pilot_allocation(ready, minimum=2, max_share=0.5, total_cap=9)
    assert (
        sum(capped.values()) == 9 and capped["A"] >= 2 and capped["C"] >= 2
    )  # the largest quota is trimmed first
    assert tf.pilot_allocation({"A": 2}, minimum=3, max_share=0.5, total_cap=5) == {
        "A": 2
    }  # never more than ready
    assert tf.pilot_allocation({}, minimum=2, max_share=0.5, total_cap=5) == {}


def test_the_pilot_draw_is_seeded_covers_each_category_once_per_group_and_leaves_a_disjoint_holdout():  # noqa: E501
    members = {
        "A": ["a1", "a2", "a3", "a4", "a5", "x"],
        "B": ["b1", "b2", "b3", "x"],  # x belongs to two categories and counts once
        "C": ["c1", "c2", "c3"],
    }
    quota = {"A": 2, "B": 2, "C": 2}
    first = tf.draw_pilot(members, quota, seed=5)
    again = tf.draw_pilot(members, quota, seed=5)
    assert first == again
    pilot = set(first["pilot"])
    assert len(first["pilot"]) == len(pilot)  # a group is drawn once
    for category, groups in members.items():
        assert len(pilot & set(groups)) >= quota[category]
    assert pilot.isdisjoint(first["holdout"]) and pilot | set(first["holdout"]) == {
        g for v in members.values() for g in v
    }
    assert first["holdout"] == sorted(first["holdout"]) and first["pilot"] == sorted(first["pilot"])
    assert first["seed"] == 5
    assert tf.draw_pilot({"A": ["a1"]}, {"A": 3}, seed=1)["pilot"] == [
        "a1"
    ]  # cannot exceed what exists


def test_pilot_size_search_starts_at_three_sources_and_uses_an_inclusive_bound():
    assert (
        tf.pilot_sources_for_sd(100.0) == 3
    )  # the first size already satisfies a very loose bound
    n = tf.pilot_sources_for_sd(1.403)
    assert tf.sd_ratio_interval(n)[1] <= 1.403 and tf.sd_ratio_interval(n - 1)[1] > 1.403
    with pytest.raises(ValueError) as error:
        tf.pilot_sources_for_sd(1.0)
    assert str(error.value) == "the upper ratio must be above 1"
    with pytest.raises(ValueError):
        tf.pilot_sources_for_sd(0.9)


def test_effective_sd_interval_defaults_to_no_clustering_and_passes_the_level_through():
    assert tf.effective_sd_interval(24) == tf.sd_ratio_interval(24)
    assert tf.effective_sd_interval(24, level=0.80) == tf.sd_ratio_interval(24, 0.80)
    assert tf.effective_sd_interval(24, 1.0, 0.90) == tf.sd_ratio_interval(24, 0.90)
    with pytest.raises(ValueError) as error:
        tf.effective_sd_interval(24, design_effect=0.9)
    assert str(error.value) == "the design effect must be at least 1"
    assert tf.effective_sd_interval(24, design_effect=1.0) == tf.sd_ratio_interval(24)


def test_pilot_allocation_never_trims_below_the_minimum_and_returns_the_untrimmed_quota():
    ready = {"A": 5, "B": 5}
    assert tf.pilot_allocation(ready, minimum=3, max_share=0.5, total_cap=4) == {"A": 3, "B": 3}
    assert tf.pilot_allocation(ready, minimum=2, max_share=1.0, total_cap=6) == {
        "A": 3,
        "B": 3,
    }  # 5 + 5 trimmed to 3 + 3
    assert tf.pilot_allocation({"A": 4}, minimum=2, max_share=0.5, total_cap=1) == {"A": 2}


def test_the_pilot_draw_ignores_unknown_categories_and_does_not_redraw_what_other_categories_covered():  # noqa: E501
    members = {"A": ["a1", "x"], "B": ["b1", "x"]}
    out = tf.draw_pilot(members, {"A": 2, "B": 1, "Z": 3}, seed=0)  # Z has no groups
    assert out["pilot"] == ["a1", "x"] and out["holdout"] == [
        "b1"
    ]  # B is covered by x; Z has no groups
    shared = tf.draw_pilot({"A": ["x"], "B": ["x", "b1"]}, {"A": 1, "B": 1}, seed=3)
    assert shared["pilot"] == ["x"] and shared["holdout"] == [
        "b1"
    ]  # x covers both quotas, b1 is not drawn
    again = tf.draw_pilot({"A": ["x", "a1"], "B": ["x"]}, {"A": 1, "B": 1}, seed=3)
    assert len(again["pilot"]) == 1  # one group serves both categories
    assert tf.draw_pilot({}, {"A": 2}, seed=1) == {"seed": 1, "pilot": [], "holdout": []}


def test_the_diversity_report_requires_both_domains_and_families_and_handles_empty_categories():
    attrs = {f"g{i}": {"domain": f"d{i}", "structure": {"C3": "f1"}} for i in range(6)}
    out = tf.diversity_report(attrs, {"C3": [f"g{i}" for i in range(6)]}, targets={"C3": 6})["C3"]
    assert (
        out["domains"] == 6 and out["families"] == 1 and out["diversity"] is False
    )  # enough domains, one family
    assert out["missing"] == ["families: 1 of 3"]
    few = tf.diversity_report({f"g{i}": {"domain": "d", "structure": {"C3": f"f{i}"}} for i in range(6)},  # noqa: E501
                              {"C3": [f"g{i}" for i in range(6)]}, targets={"C3": 6})["C3"]  # fmt: skip  # noqa: E501
    assert few["diversity"] is False and few["domains"] == 1 and few["families"] == 6
    empty = tf.diversity_report(attrs, {"C3": []})["C3"]
    assert empty["largest_family"] == "" and empty["largest_family_share"] == 0.0
    assert (
        empty["groups"] == 0
        and empty["gap"] == 40
        and empty["exploratory"] is False
        and empty["quota"] is False
    )
    top = tf.diversity_report({"a": {"domain": "d1", "structure": {"C3": "x"}}, "b": {"domain": "d2", "structure": {"C3": "y"}},  # noqa: E501
                               "c": {"domain": "d3", "structure": {"C3": "y"}}}, {"C3": ["a", "b", "c"]})["C3"]  # fmt: skip  # noqa: E501
    assert top["largest_family"] == "y" and top["largest_family_share"] == round(2 / 3, 4)


def test_main_without_a_reps_option_runs_the_documented_two_thousand_repetitions(tmp_path, capsys):
    import json

    attrs = {"a": {"domain": "d", "producer": "p", "curator": "c", "schema_family": "s", "generating_system": "g", "structure": {"C3": "f"}}}  # fmt: skip  # noqa: E501
    (tmp_path / "source_attributes.json").write_text(json.dumps(attrs))
    (tmp_path / "readiness.json").write_text(json.dumps({"ready_groups": {"C3": ["a"]}}))
    assert tf.main(["--dir", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "target_framework.json").read_text())
    assert (
        out["simulation"][0]["null_rejection_source_level"] == 0.3595
    )  # the golden rate of 2000 repetitions
    with pytest.raises(SystemExit):
        tf.main(["--help"])
    assert "simulation repetitions" in capsys.readouterr().out.replace("\n", " ")


def test_the_report_fixes_the_effect_and_pilot_grids():
    attrs = {"a": {"domain": "d", "producer": "p", "curator": "c", "schema_family": "s", "generating_system": "g", "structure": {"C3": "f"}}}  # fmt: skip  # noqa: E501
    out = tf.report(attrs, {"ready_groups": {"C3": ["a"]}}, reps=20)
    assert sorted({r["sigma"] for r in out["effect_requirements"]}) == [0.02, 0.05, 0.10]
    assert [(r["max_upper_ratio"], r["level"]) for r in out["pilot_sd_precision"]] == [
        (1.25, 0.8), (1.25, 0.95), (1.4, 0.8), (1.4, 0.95), (1.6, 0.8), (1.6, 0.95)]  # fmt: skip


def test_plan_pilot_reaches_exactly_the_requested_number_of_distinct_groups_and_reports_holdouts():
    members = {
        "A": [f"a{i}" for i in range(8)] + ["x"],
        "B": [f"b{i}" for i in range(6)] + ["x"],  # x serves both categories
        "C": [f"c{i}" for i in range(4)],
    }
    plan = tf.plan_pilot(members, total=6, minimum=2, seed=1)
    assert len(plan["pilot"]) == 6 and len(set(plan["pilot"])) == 6
    for groups in members.values():
        assert len(set(plan["pilot"]) & set(groups)) >= 2
    assert set(plan["pilot"]).isdisjoint(plan["holdout"])
    assert plan["per_category"]["A"] == {"ready": 9, "pilot": len(set(plan["pilot"]) & set(members["A"])),  # noqa: E501
                                         "holdout": 9 - len(set(plan["pilot"]) & set(members["A"]))}  # fmt: skip  # noqa: E501
    assert (
        plan == tf.plan_pilot(members, total=6, minimum=2, seed=1)
        and plan["seed"] == 1
        and plan["total"] == 6
    )
    assert plan["quotas"]["A"] >= 2 and sum(plan["quotas"].values()) >= 6
    bigger = tf.plan_pilot(members, total=9, minimum=2, seed=1)
    assert len(bigger["pilot"]) == 9 and len(bigger["holdout"]) == 19 - 9  # 19 distinct groups
    assert tf.plan_pilot({"A": ["a1", "a2"]}, total=5, minimum=1, seed=0)["pilot"] == [
        "a1",
        "a2",
    ]  # cannot exceed


def test_a_domain_map_makes_the_draw_prefer_domains_not_yet_in_the_pilot():
    members = {"A": ["a1", "a2", "a3", "a4", "a5", "a6"]}
    domains = {"a1": "x", "a2": "x", "a3": "x", "a4": "y", "a5": "y", "a6": "z"}
    for seed in range(8):
        pilot = tf.draw_pilot(members, {"A": 3}, seed=seed, domains=domains)["pilot"]
        assert {domains[g] for g in pilot} == {
            "x",
            "y",
            "z",
        }  # one group of each domain whatever the seed
    plain = {tf.draw_pilot(members, {"A": 3}, seed=s)["pilot"].__repr__() for s in range(8)}
    assert len(plain) > 1  # without a domain map the draw only follows the seed
    plan = tf.plan_pilot(members, total=4, minimum=1, seed=2, domains=domains)
    assert len(plan["pilot"]) == 4 and {domains[g] for g in plan["pilot"]} == {"x", "y", "z"}
