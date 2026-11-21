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
        "a": {"domain": "d1", "producer": "p1", "curator": "c1", "schema_family": "s1", "generating_system": "g1"},  # noqa: E501
        "b": {"domain": "d2", "producer": "p2", "curator": "c2", "schema_family": "s1", "generating_system": "g2"},  # noqa: E501
    }  # fmt: skip
    (tmp_path / "source_attributes.json").write_text(json.dumps(attributes))
    (tmp_path / "readiness.json").write_text(json.dumps({"ready_groups": {"C3": ["a", "b"]}}))
    assert tf.main(["--dir", str(tmp_path)]) == 0
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
