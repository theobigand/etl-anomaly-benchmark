"""Rules against learned detectors at comparable alert volume (T167)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matched_alert as ma  # noqa: E402


def _cell(rate, precision=0.5, recall=0.4):
    return {"test_alert_rate": rate, "precision": precision, "recall": recall}


BUDGETS = {"0.01": _cell(0.012), "0.02": _cell(0.021), "0.05": _cell(0.06), "0.1": _cell(0.13)}


def test_the_closest_cell_in_ratio_is_chosen_and_its_ratio_reported():
    key, ratio = ma.match_cell(BUDGETS, 0.05)
    assert key == "0.05" and ratio == pytest.approx(1.2)
    key, ratio = ma.match_cell(BUDGETS, 0.016)  # ratios 0.75 and 1.3125: the second is closer
    assert key == "0.02" and ratio == pytest.approx(0.021 / 0.016)


def test_a_rule_beyond_the_tolerance_or_without_alerts_has_no_match():
    assert ma.match_cell(BUDGETS, 0.0) is None
    assert ma.match_cell(BUDGETS, 0.5) is None  # 0.13 / 0.5 is far below 1 / 1.5
    single = {"0.1": _cell(0.13)}
    assert ma.match_cell(single, 0.13 / ma.TOLERANCE * 0.999) is None
    assert ma.match_cell(single, 0.13 / ma.TOLERANCE * 1.001) is not None
    assert ma.match_cell(single, 0.13 * ma.TOLERANCE * 1.001) is None
    assert ma.match_cell(single, 0.13 * ma.TOLERANCE * 0.999) is not None


def test_infeasible_and_silent_cells_are_never_matched():
    cells = {"0.005": {"nominal": 0.005, "infeasible": "few rows"}, "0.01": _cell(0.0)}
    assert ma.match_cell(cells, 0.01) is None


def _run(problem, rule_rates, ml_rates, rule="zscore", method="ecod", precision=0.5):
    seeds = [42, 1, 2, 3, 4]
    return {
        "problem": problem,
        "runs": {
            rule: [
                {"seed": s, "rule": {"test_alert_rate": r, "precision": 0.2, "recall": 0.3}}
                for s, r in zip(seeds, rule_rates, strict=False)
            ],
            method: [
                {"seed": s, "budgets": {"0.05": _cell(r, precision=precision, recall=0.4)}}
                for s, r in zip(seeds, ml_rates, strict=False)
            ],
        },
    }


def test_pairs_are_by_seed_and_every_exclusion_is_counted():
    run = _run("uci:1", [0.05, 0.0, 0.05, 0.9, 0.05], [0.05, 0.05, 0.05, 0.05])
    paired = ma.pair_problem(run, "zscore", "ecod")
    assert len(paired["rows"]) == 2  # seeds 42 and 2
    assert (paired["no_alerts"], paired["no_match"], paired["unpaired"]) == (1, 1, 1)
    row = paired["rows"][0]
    assert row["precision"] == pytest.approx(0.3) and row["recall"] == pytest.approx(0.1)


def test_a_problem_needs_enough_matched_seeds_and_the_difference_is_learned_minus_rule():
    runs = [_run(f"uci:{i}", [0.05] * 5, [0.05] * 5, precision=0.2 + 0.1 * i) for i in range(4)]
    runs.append(_run("uci:9", [0.05, 0.05, 0.9, 0.9, 0.9], [0.05] * 5))  # only 2 seeds match
    entry = ma.compare(runs, "zscore", "ecod", draws=200)
    assert entry["problems"] == 4 and entry["seed_runs"] == 20
    assert entry["excluded_seed_runs"]["few_seeds"] == 2
    assert entry["excluded_seed_runs"]["no_match"] == 3
    assert entry["recall"]["mean"] == pytest.approx(0.1)  # 0.4 - 0.3
    assert entry["precision"]["mean"] == pytest.approx(0.15)  # learned .2 .3 .4 .5 minus rule .2
    assert entry["median_alert_ratio"] == pytest.approx(1.0)
    assert entry["alert_ratio_quartiles"] == [pytest.approx(1.0), pytest.approx(1.0)]


def test_sources_are_resampled_not_problems():
    runs = [_run("adbench:glass", [0.05] * 5, [0.05] * 5), _run("uci:42", [0.05] * 5, [0.05] * 5)]
    entry = ma.compare(runs, "zscore", "ecod", draws=100)
    assert entry["problems"] == 2 and entry["recall"]["units"] == 1  # glass derives from UCI 42


def test_analyse_adjusts_each_metric_over_the_whole_family_and_ignores_rules_as_learners():
    runs = [_run(f"uci:{i}", [0.05] * 5, [0.05] * 5, precision=0.2 + 0.05 * i) for i in range(6)]
    result = ma.analyse(runs, draws=100)
    assert {e["rule"] for e in result["comparisons"]} == set(ma.RULES)
    assert {e["method"] for e in result["comparisons"]} == {"ecod"}
    zscore = next(e for e in result["comparisons"] if e["rule"] == "zscore")
    assert zscore["recall"]["holm_p"] >= zscore["recall"]["p_two_sided"]
    iqr = next(e for e in result["comparisons"] if e["rule"] == "iqr")
    assert iqr["problems"] == 0 and "recall" not in iqr  # a rule that did not run is not invented


def test_load_merges_classical_and_neural_files_by_problem(tmp_path):
    for folder, method in (("a", "ecod"), ("b", "vae")):
        (tmp_path / folder).mkdir()
        run = {"problem": "uci:1", "runs": {method: []}}
        (tmp_path / folder / "uci_1.json").write_text(json.dumps(run))
    (tmp_path / "b" / "uci_2.json").write_text(json.dumps({"problem": "uci:2", "failed": "x"}))
    merged = ma.load(tmp_path / "a", tmp_path / "b")
    assert len(merged) == 1 and set(merged[0]["runs"]) == {"ecod", "vae"}
