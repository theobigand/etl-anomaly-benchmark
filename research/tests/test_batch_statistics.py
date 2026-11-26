"""Batch-study statistics on synthetic data with known properties."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch_statistics as bs  # noqa: E402
import target_framework as tf  # noqa: E402


def test_linked_sets_share_one_cluster_and_overlapping_sets_merge():
    groups = ["a", "b", "c", "d", "e", "f"]
    assignment = bs.link_clusters(groups, [["c", "a"], ["b", "a"], ["e", "f"], ["zzz", "d"]])
    assert assignment == {"a": "a", "b": "a", "c": "a", "d": "d", "e": "e", "f": "e"}
    assert bs.clusters_of(assignment) == {"a": ["a", "b", "c"], "d": ["d"], "e": ["e", "f"]}


def test_a_chain_of_links_merges_into_the_smallest_group_name():
    groups = ["d", "c", "b", "a"]
    assert set(bs.link_clusters(groups, [["d", "c"], ["c", "b"], ["b", "a"]]).values()) == {"a"}


def _panel():
    members = {
        "C1": [f"c1_{i}" for i in range(8)],
        "C2": [f"c2_{i}" for i in range(6)] + ["c1_0"],
        "C3": [f"c3_{i}" for i in range(6)],
    }
    links = [["c1_1", "c3_1"], ["c1_2", "c2_2", "c3_2"]]
    return members, links


def test_a_clustered_pilot_never_splits_a_linked_set_and_keeps_exposed_clusters_out():
    members, links = _panel()
    out = bs.draw_clustered_pilot(members, links, ["c3_1"], 6, 1, seed=3)
    pilot, holdout, exposed = set(out["pilot"]), set(out["holdout"]), set(out["exposed"])
    assert exposed == {"c1_1", "c3_1"}  # the exposed group's linked partner is exposed too
    assert not exposed & (pilot | holdout)
    for linked in links:
        sides = [g in pilot for g in linked if g not in exposed]
        assert len(set(sides)) <= 1
    assert pilot | holdout | exposed == {g for gs in members.values() for g in gs}
    assert not pilot & holdout
    assert out["clusters"]["pilot"] >= 3  # at least the per-category minimum, counted in clusters


def test_the_clustered_draw_is_reproducible_and_seed_dependent():
    members, links = _panel()
    a = bs.draw_clustered_pilot(members, links, [], 6, 1, seed=1)
    b = bs.draw_clustered_pilot(members, links, [], 6, 1, seed=1)
    c = bs.draw_clustered_pilot(members, links, [], 6, 1, seed=2)
    assert a == b and a["pilot"] != c["pilot"]


def test_the_clustered_draw_can_balance_domains():
    members, links = _panel()
    domains = {g: ("x" if g.startswith("c1") else "y") for gs in members.values() for g in gs}
    out = bs.draw_clustered_pilot(members, links, [], 6, 1, seed=1, domains=domains)
    assert out["clusters"]["pilot"] == 6


def test_factor_structure_counts_levels_singletons_and_the_largest_level():
    attrs = {
        "a": {"domain": "x", "curator": "k"},
        "b": {"domain": "x", "curator": "l"},
        "c": {"domain": "y", "curator": "k"},
        "d": {},
    }
    out = bs.factor_structure(["a", "b", "c", "d"], attrs, ("domain", "curator"))
    assert out["domain"] == {"levels": 3, "singletons": 2, "largest": 2, "largest_level": "x"}
    assert out["curator"] == {"levels": 3, "singletons": 2, "largest": 2, "largest_level": "k"}
    assert bs.factor_structure([], attrs, ("domain",))["domain"] == {
        "levels": 0, "singletons": 0, "largest": 0, "largest_level": None,
    }  # fmt: skip


def test_effective_clusters_discount_by_the_intra_cluster_correlation():
    assert bs.effective_clusters([1, 1, 1], 0.5) == 3.0
    assert bs.effective_clusters([3], 0.5) == pytest.approx(1.5)
    assert bs.effective_clusters([3, 3], 0.0) == 6.0
    assert bs.effective_clusters([4], 0.2) == tf.effective_groups([4], 0.2)


def test_cluster_bootstrap_interval_contains_the_mean_and_is_reproducible():
    rng = np.random.default_rng(0)
    values = rng.normal(0.3, 1.0, 60)
    clusters = [f"c{i // 2}" for i in range(60)]
    a = bs.cluster_bootstrap(values, clusters, seed=5, resamples=500)
    b = bs.cluster_bootstrap(values, clusters, seed=5, resamples=500)
    assert a == b and a["clusters"] == 30
    assert a["mean"] == pytest.approx(values.mean())
    assert a["low"] < a["mean"] < a["high"]
    assert bs.cluster_bootstrap(values, clusters, 6, 500) != a


def test_a_linked_cluster_widens_the_interval_compared_with_independent_groups():
    rng = np.random.default_rng(1)
    shared = np.repeat(rng.normal(0, 1, 15), 4)  # four identical copies per cluster
    clustered = bs.cluster_bootstrap(shared, [f"c{i // 4}" for i in range(60)], 0, 800)
    naive = bs.cluster_bootstrap(shared, [f"g{i}" for i in range(60)], 0, 800)
    assert clustered["high"] - clustered["low"] > 1.5 * (naive["high"] - naive["low"])


def test_cluster_bootstrap_covers_the_truth_at_about_the_nominal_rate():
    rng = np.random.default_rng(2)
    hits = 0
    for trial in range(120):
        effect = rng.normal(0, 1, 40)  # one draw per cluster of two
        values = np.repeat(effect, 2) + rng.normal(0, 0.3, 80)
        ci = bs.cluster_bootstrap(values, [f"c{i // 2}" for i in range(80)], trial, 300)
        hits += ci["low"] <= 0.0 <= ci["high"]
    assert 0.88 <= hits / 120 <= 0.99


def test_cluster_bootstrap_validates_its_input():
    with pytest.raises(ValueError, match="one value and one cluster"):
        bs.cluster_bootstrap(np.ones(3), ["a", "b"], 0)
    with pytest.raises(ValueError, match="one value and one cluster"):
        bs.cluster_bootstrap(np.ones(0), [], 0)
    with pytest.raises(ValueError, match="level"):
        bs.cluster_bootstrap(np.ones(2), ["a", "b"], 0, level=1.0)


def test_icc_recovers_a_known_intraclass_correlation():
    rng = np.random.default_rng(3)
    n, k = 4000, 5
    y = rng.normal(0, 1.0, (n, 1)) + rng.normal(0, 1.0, (n, k))  # ICC = 0.5
    assert bs.icc_oneway(y) == pytest.approx(0.5, abs=0.03)
    assert bs.icc_oneway(rng.normal(size=(4000, 4))) < 0.03
    assert bs.icc_oneway(np.array([[1.0, 2.0], [2.0, 1.0], [1.5, 1.5]])) == 0.0  # truncated
    with pytest.raises(ValueError, match="at least two groups"):
        bs.icc_oneway(np.ones((1, 3)))
    with pytest.raises(ValueError, match="at least two groups"):
        bs.icc_oneway(np.ones((3, 1)))


def test_variance_components_recover_known_values():
    rng = np.random.default_rng(4)
    s, d, r = 400, 6, 4
    y = (
        rng.normal(0, 2.0, (s, 1, 1))  # source sd 2   -> variance 4
        + rng.normal(0, 1.0, (1, d, 1))  # detector sd 1 -> 1
        + rng.normal(0, 1.5, (s, d, 1))  # interaction sd 1.5 -> 2.25
        + rng.normal(0, 0.5, (s, d, r))  # residual sd 0.5 -> 0.25
    )
    out = bs.variance_components(y)
    assert out["source"] == pytest.approx(4.0, rel=0.15)
    assert out["source_by_detector"] == pytest.approx(2.25, rel=0.1)
    assert out["residual"] == pytest.approx(0.25, rel=0.05)
    assert out["detector"] == pytest.approx(1.0, abs=1.5)  # six detectors: poorly determined
    assert out["truncated"] == []


def test_a_negative_component_is_reported_as_zero_and_listed():
    y = np.random.default_rng(5).normal(0, 1, (30, 3, 3))
    out = bs.variance_components(y)
    assert min(out[k] for k in ("source", "detector", "source_by_detector", "residual")) >= 0
    assert out["truncated"]  # pure noise: some component estimates fall below zero
    assert all(out[k] == 0.0 for k in out["truncated"])
    assert out["truncated"] == sorted(out["truncated"])


def test_variance_components_need_a_crossed_design_with_replicates():
    for shape in ((1, 2, 2), (2, 1, 2), (2, 2, 1)):
        with pytest.raises(ValueError, match="at least two"):
            bs.variance_components(np.ones(shape))


def test_the_paired_difference_sd_is_the_sd_over_sources_of_the_replicate_mean_gap():
    y = np.zeros((4, 2, 3))
    y[:, 0, :] = np.array([[1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4]])
    assert bs.paired_difference_sd(y, 0, 1) == pytest.approx(np.std([1, 2, 3, 4], ddof=1))
    assert bs.paired_difference_sd(y, 1, 1) == 0.0
    with pytest.raises(ValueError, match="at least two sources"):
        bs.paired_difference_sd(y[:1], 0, 1)


def test_a_pilot_sd_feeds_the_registered_sample_size_table():
    sigma = 0.10
    assert tf.paired_sources(sigma, 0.05) == 34  # the table of the variance pilot design


def test_the_linked_set_file_names_registry_groups_and_the_five_exposed_ones():
    links = bs.load_links()
    facts = json.loads((bs.LINKS / "readiness_facts.json").read_text())["facts"]
    groups = {f["independent_group"] for f in facts.values()}
    for item in links["linked_sets"]:
        assert set(item["groups"]) <= groups and len(item["groups"]) >= 2
    assert len(links["exposed_groups"]) == 5 and set(links["exposed_groups"]) <= groups


def _evidence(tmp_path):
    ready = {"C1": ["a", "b", "x1"], "C3": ["c", "d", "e", "x2"]}
    (tmp_path / "readiness.json").write_text(json.dumps({"ready_groups": ready}))
    attrs = {g: {"domain": "d" + g, "curator": "k", "schema_family": "s"} for g in "abcde"}
    (tmp_path / "source_attributes.json").write_text(json.dumps(attrs))
    audit = {g: {"eligible": g in "abcde"} for g in ("a", "b", "c", "d", "e", "x1", "x2")}
    (tmp_path / "audit.json").write_text(json.dumps({"groups": audit}))
    links = {
        "linked_sets": [{"groups": ["a", "c"]}],
        "exposed_groups": {"b": "seen", "zz": "not eligible"},
    }
    (tmp_path / "links.json").write_text(json.dumps(links))
    return ["--evidence", str(tmp_path), "--audit", str(tmp_path / "audit.json"),
            "--links", str(tmp_path / "links.json")]  # fmt: skip


def test_structure_counts_eligible_groups_clusters_and_exposure(tmp_path, capsys):
    base = _evidence(tmp_path)
    assert bs.main(["structure", *base]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["eligible_groups"] == 5 and report["per_category"] == {"C1": 2, "C3": 3}
    assert report["clusters"] == 4  # a and c are linked
    assert report["exposed"] == ["b"] and report["available_after_exposure"] == 4
    assert report["factors"]["curator"] == {
        "levels": 1, "singletons": 0, "largest": 5, "largest_level": "k",
    }  # fmt: skip
    assert report["factors"]["domain"]["singletons"] == 5


def test_pilot_plan_needs_the_owner_decisions_and_writes_a_deterministic_file(tmp_path):
    base = _evidence(tmp_path)
    with pytest.raises(SystemExit, match="owner decisions"):
        bs.main(["pilot-plan", *base, "--total", "3"])
    out = tmp_path / "plan.json"
    argv = ["pilot-plan", *base, "--total", "3", "--seed", "9", "--output", str(out)]
    assert bs.main(argv) == 0
    plan = json.loads(out.read_text())
    assert plan["exposed"] == ["b"] and "b" not in plan["pilot"] + plan["holdout"]
    assert not {"a", "c"} & set(plan["pilot"]) or {"a", "c"} <= set(plan["pilot"])
    assert out.read_text() == json.dumps(plan, indent=1, sort_keys=True) + "\n"


def test_exposed_clusters_can_fill_the_pilot_without_spending_fresh_ones():
    members, links = _panel()
    out = bs.draw_clustered_pilot(members, links, ["c3_1"], 6, 1, seed=3, reuse_exposed=True)
    assert {"c1_1", "c3_1"} <= set(out["pilot"])  # the exposed cluster is in the pilot
    assert out["exposed"] == ["c1_1", "c3_1"]
    assert out["clusters"]["pilot"] == 6
    assert not set(out["pilot"]) & set(out["holdout"])
    fresh = bs.draw_clustered_pilot(members, links, ["c3_1"], 6, 1, seed=3)
    assert out["clusters"]["holdout"] == fresh["clusters"]["holdout"] + 1  # one fewer fresh draw
    with pytest.raises(ValueError, match="smaller than the exposed"):
        bs.draw_clustered_pilot(members, links, ["c3_1", "c1_5"], 1, 1, seed=3, reuse_exposed=True)


def test_the_parser_defaults_choices_and_description():
    parser = bs.build_parser()
    assert parser.description == bs.__doc__
    assert vars(parser.parse_args(["structure"])) == {
        "command": "structure",
        "evidence": bs.LINKS,
        "audit": bs.LINKS / "batch_eligibility.json",
        "links": bs.LINKS / "linked_sets.json",
        "total": None,
        "minimum": 1,
        "seed": None,
        "reuse_exposed": False,
        "output": None,
    }
    args = parser.parse_args(["pilot-plan", "--total", "4", "--seed", "2", "--reuse-exposed"])
    assert (args.total, args.seed, args.reuse_exposed, args.minimum) == (4, 2, True, 1)
    with pytest.raises(SystemExit):
        parser.parse_args(["bogus"])


def test_the_pilot_plan_passes_every_option_through_and_prints_without_an_output(tmp_path, capsys):
    base = _evidence(tmp_path)
    argv = ["pilot-plan", *base, "--total", "3", "--minimum", "1", "--seed", "9"]
    assert bs.main(argv) == 0
    printed = capsys.readouterr().out
    plan = json.loads(printed)
    assert printed == json.dumps(plan, indent=1, sort_keys=True) + "\n"
    assert plan["seed"] == 9 and plan["clusters"] == {"pilot": 3, "holdout": 0}
    assert "b" not in plan["pilot"]  # exposed, and not reused without the flag
    assert bs.main([*argv, "--reuse-exposed"]) == 0
    reused = json.loads(capsys.readouterr().out)
    assert "b" in reused["pilot"] and reused["clusters"] == {"pilot": 3, "holdout": 1}


def test_default_paths_point_at_the_committed_evidence():
    assert bs.LINKS.name == "dataset_registry_v2" and bs.LINKS.is_dir()
    assert (bs.LINKS / "linked_sets.json").is_file()
    assert bs.FACTORS == ("domain", "schema_family", "curator")


def test_a_domain_balanced_pilot_spreads_over_domains_for_every_seed():
    members = {"C1": ["a1", "a2", "a3", "b1", "b2"]}
    domains = {"a1": "X", "a2": "X", "a3": "X", "b1": "Y", "b2": "Y"}
    for seed in range(20):
        out = bs.draw_clustered_pilot(members, [], [], 2, 1, seed, domains=domains)
        assert {domains[g] for g in out["pilot"]} == {"X", "Y"}
    plain = [bs.draw_clustered_pilot(members, [], [], 2, 1, s)["pilot"] for s in range(20)]
    assert any(
        {domains[g] for g in p} == {"X"} for p in plain
    )  # without it the draw can be one-sided


def test_a_pilot_exactly_the_size_of_the_exposed_clusters_is_allowed():
    members, links = _panel()
    out = bs.draw_clustered_pilot(members, links, ["c3_1"], 1, 1, seed=3, reuse_exposed=True)
    assert {"c1_1", "c3_1"} <= set(out["pilot"])  # nothing left to draw but the category minima
    assert out["clusters"]["pilot"] >= 2 and not set(out["pilot"]) & set(out["holdout"])
    with pytest.raises(
        ValueError, match="^the pilot is smaller than the exposed clusters it must hold$"
    ):
        bs.draw_clustered_pilot(members, links, ["c3_1"], 0, 1, seed=3, reuse_exposed=True)


def test_a_group_or_factor_without_an_attribute_is_one_unknown_level():
    out = bs.factor_structure(["a", "b", "c"], {"a": {"domain": "x"}, "b": {}}, ("domain",))
    assert out["domain"] == {"levels": 2, "singletons": 1, "largest": 2, "largest_level": "unknown"}


def test_a_ready_group_missing_from_the_audit_is_not_eligible(tmp_path):
    (tmp_path / "readiness.json").write_text(json.dumps({"ready_groups": {"C1": ["a", "ghost"]}}))
    (tmp_path / "audit.json").write_text(json.dumps({"groups": {"a": {"eligible": True}}}))
    assert bs.eligible_members(tmp_path, tmp_path / "audit.json") == {"C1": ["a"]}


def _reference_bootstrap(values, clusters, seed, resamples, level):
    names = sorted(set(clusters))
    rows = [[i for i, c in enumerate(clusters) if c == n] for n in names]
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(resamples):
        pick = rng.integers(len(names), size=len(names))
        means.append(np.mean([values[i] for j in pick for i in rows[j]]))
    tail = (1 - level) / 2 * 100
    return np.percentile(means, [tail, 100 - tail])


def test_the_cluster_bootstrap_equals_an_independent_percentile_of_cluster_resamples():
    values = [1.0, 2.0, 4.0, 8.0, 3.0, 5.0, 9.0, 0.5]
    clusters = ["a", "a", "b", "c", "c", "d", "e", "e"]
    for level in (0.8, 0.95):
        out = bs.cluster_bootstrap(values, clusters, seed=4, resamples=50, level=level)
        low, high = _reference_bootstrap(values, clusters, 4, 50, level)
        assert (out["low"], out["high"]) == pytest.approx((low, high))
    assert out["mean"] == pytest.approx(np.mean(values)) and out["clusters"] == 5
    import inspect

    defaults = inspect.signature(bs.cluster_bootstrap).parameters
    assert (defaults["resamples"].default, defaults["level"].default) == (2000, 0.95)
    assert bs.cluster_bootstrap([1, 2, 3], ["a", "b", "c"], 0, 20)["mean"] == 2.0  # integers


def test_the_cluster_bootstrap_rejects_a_level_of_zero_and_states_its_errors_exactly():
    with pytest.raises(ValueError, match="^level must be between 0 and 1$"):
        bs.cluster_bootstrap(np.ones(2), ["a", "b"], 0, level=0.0)
    with pytest.raises(
        ValueError, match="^one value and one cluster per group, at least one group$"
    ):
        bs.cluster_bootstrap(np.ones(2), ["a"], 0)


def test_icc_has_the_closed_form_value_and_accepts_the_smallest_valid_table():
    y = np.array([[1.0, 3.0], [2.0, 2.0], [5.0, 7.0]])  # MSB 32/3, MSW 4/3
    assert bs.icc_oneway(y) == pytest.approx(7 / 9)
    assert bs.icc_oneway(np.array([[1, 2], [5, 6]])) == pytest.approx(
        31 / 33
    )  # n = k = 2: MSB 16, MSW 1/2
    with pytest.raises(
        ValueError, match="^need at least two groups and two observations per group$"
    ):
        bs.icc_oneway(np.ones((1, 2)))


def test_additive_effects_give_the_sample_variances_of_the_effects_and_no_other_component():
    source = np.array([0.0, 1.0, 5.0])
    detector = np.array([0.0, 2.0])
    y = (source[:, None] + detector[None, :])[:, :, None] * np.ones((1, 1, 2))
    out = bs.variance_components(y)
    assert out["source"] == pytest.approx(np.var(source, ddof=1))
    assert out["detector"] == pytest.approx(np.var(detector, ddof=1))
    assert out["source_by_detector"] == 0.0 and out["residual"] == 0.0
    assert out["truncated"] == []


def test_replicate_noise_alone_is_the_residual_and_a_pure_interaction_is_recovered():
    noise = np.array([1.0, 4.0])
    y = np.ones((3, 2, 1)) * noise  # identical in every cell, differing by replicate
    out = bs.variance_components(y)
    assert out["residual"] == pytest.approx(np.var(noise, ddof=1))
    assert out["source"] == 0.0 and out["source_by_detector"] == 0.0
    cell = np.array([[1.0, 0.0], [0.0, 1.0]])
    pure = bs.variance_components(np.repeat(cell[:, :, None], 2, axis=2))
    assert pure["source_by_detector"] == pytest.approx(1.0)  # residual is zero
    assert pure["truncated"] == ["detector", "source"]


def test_variance_components_accept_the_smallest_design_and_state_their_error():
    out = bs.variance_components(np.arange(8.0).reshape(2, 2, 2))
    assert set(out) == {"source", "detector", "source_by_detector", "residual", "truncated"}
    with pytest.raises(
        ValueError, match="^need at least two sources, two detectors and two replicates$"
    ):
        bs.variance_components(np.ones((1, 2, 2)))


def test_the_paired_difference_sd_uses_the_difference_of_the_replicate_means_per_source():
    y = np.array([[[1.0, 3.0], [0.0, 2.0]], [[4.0, 6.0], [0.0, 0.0]], [[2.0, 2.0], [1.0, 1.0]]])
    # replicate means: detector 0 -> 2, 5, 2; detector 1 -> 1, 0, 1; differences 1, 5, 1
    assert bs.paired_difference_sd(y, 0, 1) == pytest.approx(np.std([1, 5, 1], ddof=1))
    two = y[:2]
    assert bs.paired_difference_sd(two, 0, 1) == pytest.approx(
        np.std([1, 5], ddof=1)
    )  # two sources
    with pytest.raises(ValueError, match="^need at least two sources$"):
        bs.paired_difference_sd(y[:1], 0, 1)


def test_pilot_plan_states_that_its_size_and_seed_are_owner_decisions(tmp_path):
    base = _evidence(tmp_path)
    with pytest.raises(SystemExit) as caught:
        bs.main(["pilot-plan", *base])
    assert str(caught.value) == "pilot-plan needs --total and --seed (both are owner decisions)"
