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
