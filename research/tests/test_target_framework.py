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
        "exploratory": True, "quota": False, "diversity": False,
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
