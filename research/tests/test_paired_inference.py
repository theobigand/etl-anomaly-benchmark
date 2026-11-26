"""Holm correction, paired effects and rank statistics over independent units."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paired_inference as pi  # noqa: E402


def test_holm_matches_the_textbook_step_down_and_keeps_input_order():
    adjusted = pi.holm([0.04, 0.001, 0.03])
    # sorted 0.001, 0.03, 0.04 -> 3*0.001, 2*0.03, 1*0.04 -> monotone 0.003, 0.06, 0.06
    assert adjusted == pytest.approx([0.06, 0.003, 0.06])
    assert pi.holm([0.9, 0.8]) == pytest.approx([1.0, 1.0])


def test_group_means_average_twin_problems_and_ignore_missing_values():
    values = {"uci:1": 0.2, "adbench:a": 0.4, "uci:2": 0.5, "uci:3": np.nan}
    groups = {"uci:1": "s1", "adbench:a": "s1", "uci:2": "s2", "uci:3": "s3"}
    assert pi.group_means(values, groups) == pytest.approx({"s1": 0.3, "s2": 0.5})


def test_a_clear_paired_shift_is_detected_with_its_effect_size():
    rng = np.random.default_rng(0)
    b = rng.uniform(0.2, 0.6, 30)
    effect = pi.paired_effect(b + 0.1 + rng.normal(0, 0.01, 30), b, draws=500)
    assert effect["p"] < 1e-4 and effect["units"] == 30
    assert effect["ci_low"] > 0.05 and effect["probability_of_superiority"] == 1.0
    assert effect["rank_biserial"] == 1.0


def test_identical_scores_give_p_one_and_missing_units_are_not_used():
    a = np.array([0.1, 0.2, np.nan, 0.4])
    effect = pi.paired_effect(a, a.copy(), draws=100)
    assert effect["p"] == 1.0 and effect["units"] == 3 and effect["median_difference"] == 0.0
    assert pi.paired_effect(np.array([np.nan]), np.array([1.0]))["units"] == 0


def test_pairwise_adjusts_over_all_pairs():
    rng = np.random.default_rng(1)
    base = rng.uniform(0.2, 0.6, 25)
    table = {"x": base + 0.2, "y": base, "z": base + rng.normal(0, 0.05, 25)}
    rows = pi.pairwise(table, draws=200)
    assert len(rows) == 3
    for row in rows:
        assert row["p_holm"] >= row["p"]
    assert {(r["a"], r["b"]) for r in rows} == {("x", "y"), ("x", "z"), ("y", "z")}


def test_mean_ranks_use_one_for_the_best_and_average_ties():
    matrix = np.array([[0.9, 0.5, 0.5], [0.8, 0.6, 0.1]])
    assert pi.mean_ranks(matrix) == pytest.approx([1.0, 2.25, 2.75])


def test_complete_matrix_drops_rare_detectors_and_incomplete_units():
    table = {
        "a": np.array([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        "b": np.array([1.0, 2, 3, 4, 5, 6, 7, 8, 9, np.nan]),
        "c": np.array([np.nan] * 8 + [1.0, 2.0]),
    }
    names, matrix = pi.complete_matrix(table, coverage=0.9)
    assert names == ["a", "b"] and matrix.shape == (9, 2)


def test_rank_intervals_contain_the_mean_rank_and_friedman_sees_a_consistent_order():
    rng = np.random.default_rng(2)
    base = rng.uniform(0, 1, (20, 1))
    matrix = base + np.array([[0.0, 0.1, 0.2]])
    ranks = pi.mean_ranks(matrix)
    interval = pi.rank_intervals(matrix, draws=200)
    assert ((interval[:, 0] <= ranks) & (ranks <= interval[:, 1])).all()
    assert pi.friedman(matrix)["p"] < 1e-6
    assert pi.kendall(np.array([1, 2, 3, 4.0]), np.array([1, 3, 2, 4.0])) == pytest.approx(2 / 3)


def test_the_module_constants_are_the_documented_defaults():
    assert pi.DRAWS == 10_000 and pi.SEED == 2026 and pi.LEVEL == 0.95


def test_holm_accepts_integer_input_and_returns_floats():
    adjusted = pi.holm([1, 0])
    assert adjusted.dtype == float and adjusted.tolist() == [1.0, 0.0]
    assert pi.holm([]).tolist() == []


def test_a_comparison_without_common_units_has_only_units_median_and_p():
    out = pi.paired_effect(np.array([np.nan]), np.array([np.nan]))
    assert set(out) == {"units", "median_difference", "p"}
    assert out["units"] == 0 and np.isnan(out["median_difference"]) and out["p"] == 1.0


def test_zero_differences_are_left_out_of_the_test_but_counted_as_ties():
    from scipy.stats import wilcoxon

    b = np.zeros(8)
    a = np.array([0.0, 1.0, 2.0, 3.0, -1.0, 0.5, 0.0, 4.0])
    out = pi.paired_effect(a, b, draws=50)
    nonzero = a[a != 0]
    assert out["p"] == float(wilcoxon(nonzero).pvalue)
    assert out["units"] == 8 and out["median_difference"] == pytest.approx(0.75)
    # 5 wins, 1 loss, 2 ties
    assert out["probability_of_superiority"] == pytest.approx((5 + 0.5 * 2) / 8)
    assert out["rank_biserial"] == pytest.approx((5 - 1) / 8)


def test_the_effect_report_has_exactly_the_documented_fields():
    out = pi.paired_effect(np.array([0.3, 0.5, 0.2]), np.array([0.1, 0.5, 0.4]), draws=50)
    assert set(out) == {
        "units",
        "median_difference",
        "ci_low",
        "ci_high",
        "p",
        "probability_of_superiority",
        "rank_biserial",
    }
    assert out["probability_of_superiority"] == pytest.approx((1 + 0.5) / 3)
    assert out["rank_biserial"] == pytest.approx(0.0)


def test_the_interval_is_the_seeded_percentile_bootstrap_of_the_median_difference():
    rng = np.random.default_rng(5)
    a, b = rng.uniform(0, 1, 15), rng.uniform(0, 1, 15)
    d = a - b
    for seed in (2026, 7):
        draws = np.random.default_rng(seed).integers(0, 15, (300, 15))
        low, high = np.quantile(np.median(d[draws], axis=1), [0.025, 0.975])
        out = pi.paired_effect(a, b, draws=300, seed=seed)
        assert out["ci_low"] == low and out["ci_high"] == high
    default = np.random.default_rng(pi.SEED).integers(0, 15, (300, 15))
    low, high = np.quantile(np.median(d[default], axis=1), [0.025, 0.975])
    out = pi.paired_effect(a, b, draws=300)
    assert (out["ci_low"], out["ci_high"]) == (low, high)
    assert out["ci_low"] < out["ci_high"]
    assert pi.paired_effect(a, b, draws=300) == out


def test_the_default_number_of_draws_is_used_when_none_is_given():
    import inspect

    assert inspect.signature(pi.paired_effect).parameters["draws"].default == pi.DRAWS
    assert inspect.signature(pi.pairwise).parameters["draws"].default == pi.DRAWS
    assert inspect.signature(pi.rank_intervals).parameters["draws"].default == pi.DRAWS
    assert inspect.signature(pi.rank_intervals).parameters["seed"].default == pi.SEED
    assert inspect.signature(pi.complete_matrix).parameters["coverage"].default == 0.9


def test_pairwise_orders_the_pairs_by_name_and_adjusts_their_p_values_together():
    rng = np.random.default_rng(3)
    base = rng.uniform(0.2, 0.6, 12)
    table = {
        "c": base,
        "a": base + 0.2 + rng.normal(0, 0.01, 12),
        "b": base + rng.normal(0, 0.1, 12),
    }
    rows = pi.pairwise(table, draws=50)
    assert [(r["a"], r["b"]) for r in rows] == [("a", "b"), ("a", "c"), ("b", "c")]
    adjusted = pi.holm([r["p"] for r in rows])
    assert [r["p_holm"] for r in rows] == adjusted.tolist()
    for row in rows:
        expected = pi.paired_effect(table[row["a"]], table[row["b"]], 50)
        assert {k: row[k] for k in expected} == expected
    assert pi.pairwise({"only": base}) == []
    assert pi.pairwise({}) == []


def test_a_detector_is_kept_when_it_has_results_on_exactly_ninety_percent_of_units():
    table = {
        "full": np.arange(10.0),
        "nine": np.array([*np.arange(9.0), np.nan]),
        "eight": np.array([*np.arange(8.0), np.nan, np.nan]),
    }
    names, matrix = pi.complete_matrix(table)
    assert names == ["full", "nine"] and matrix.shape == (9, 2)
    names, matrix = pi.complete_matrix(table, coverage=0.8)
    assert names == ["eight", "full", "nine"] and matrix.shape == (8, 3)


def test_rank_intervals_are_the_seeded_percentiles_of_resampled_mean_ranks():
    from scipy.stats import rankdata

    rng = np.random.default_rng(9)
    matrix = rng.uniform(0, 1, (12, 3))
    ranks = np.array([rankdata(-row) for row in matrix])
    for seed in (2026, 3):
        picks = np.random.default_rng(seed).integers(0, 12, (200, 12))
        expected = np.quantile(ranks[picks].mean(axis=1), [0.025, 0.975], axis=0).T
        got = pi.rank_intervals(matrix, draws=200, seed=seed)
        assert got.shape == (3, 2) and np.allclose(got, expected, rtol=0, atol=1e-12)
    assert (pi.rank_intervals(matrix, draws=200) == pi.rank_intervals(matrix, draws=200)).all()


def test_rank_intervals_average_the_ranks_of_tied_detectors():
    matrix = np.array([[0.5, 0.5, 0.1]] * 10)
    got = pi.rank_intervals(matrix, draws=50)
    assert got.tolist() == [[1.5, 1.5], [1.5, 1.5], [3.0, 3.0]]


def test_friedman_reports_the_statistic_the_p_value_and_the_size_of_the_matrix():
    from scipy.stats import friedmanchisquare

    matrix = np.array([[0.9, 0.5, 0.1], [0.8, 0.6, 0.2], [0.7, 0.4, 0.3], [0.9, 0.2, 0.5]])
    out = pi.friedman(matrix)
    expected = friedmanchisquare(*matrix.T)
    assert out == {
        "statistic": float(expected.statistic),
        "p": float(expected.pvalue),
        "units": 4,
        "detectors": 3,
    }
