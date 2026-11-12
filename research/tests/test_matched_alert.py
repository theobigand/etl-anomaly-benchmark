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


# --- boundaries, tie-breaks and the exact accounting of what was left out ----------------------


def test_a_ratio_exactly_at_the_tolerance_is_still_matched():
    assert ma.TOLERANCE == 1.5
    assert ma.match_cell({"0.1": _cell(0.75)}, 0.5) == ("0.1", 1.5)


def test_an_infeasible_cell_does_not_hide_the_feasible_cells_after_it():
    cells = {"0.005": {"nominal": 0.005, "infeasible": "few rows"}, "0.01": _cell(0.0),
             "0.02": _cell(0.021)}  # fmt: skip
    key, ratio = ma.match_cell(cells, 0.02)
    assert key == "0.02" and ratio == pytest.approx(1.05)


def test_equally_close_cells_are_resolved_by_the_smaller_nominal_budget_then_by_order():
    # same distance from the rule: the smaller nominal budget wins, whatever the iteration order
    both = {"0.9": _cell(0.75), "0.8": _cell(0.75)}
    assert ma.match_cell(both, 1.0)[0] == "0.8"
    # two spellings of the same budget: the first one listed is kept
    assert ma.match_cell({"0.1": _cell(0.12), "0.10": _cell(0.12)}, 0.12)[0] == "0.1"


def test_seeds_without_a_learned_run_are_each_counted_as_unpaired():
    run = _run("uci:1", [0.05, 0.05, 0.05], [0.05, 0.05, 0.05])
    del run["runs"]["ecod"]
    paired = ma.pair_problem(run, "zscore", "ecod")
    assert paired == {"rows": [], "unpaired": 3, "no_alerts": 0, "no_match": 0}


def test_an_unpaired_seed_does_not_stop_the_seeds_after_it():
    run = _run("uci:1", [0.05, 0.05, 0.05], [0.05, 0.05, 0.05])
    run["runs"]["ecod"] = run["runs"]["ecod"][1:]  # the first seed has no learned run
    paired = ma.pair_problem(run, "zscore", "ecod")
    assert paired["unpaired"] == 1 and len(paired["rows"]) == 2
    assert paired["rows"][0]["budget"] == 0.05
    assert paired["rows"][0]["ratio"] == pytest.approx(1.0)


def test_a_missing_rule_run_yields_no_pairs():
    run = {"problem": "uci:1", "runs": {"ecod": []}}
    assert ma.pair_problem(run, "zscore", "ecod") == {
        "rows": [], "unpaired": 0, "no_alerts": 0, "no_match": 0,
    }  # fmt: skip


def test_exclusions_accumulate_over_problems_and_a_short_problem_does_not_stop_the_rest():
    short_a = _run("uci:1", [0.05, 0.05, 0.9, 0.0, 0.05], [0.05, 0.05, 0.05, 0.05])
    short_b = _run("uci:2", [0.05, 0.05, 0.9, 0.0, 0.05], [0.05, 0.05, 0.05, 0.05])
    exactly_enough = _run("uci:3", [0.05] * 3, [0.05] * 3)
    entry = ma.compare([short_a, short_b, exactly_enough], "zscore", "ecod", draws=50)
    # per short problem: seeds 42, 1 match; seed 2 no_match; seed 3 no_alerts; seed 4 unpaired
    assert entry["excluded_seed_runs"] == {
        "unpaired": 2, "no_alerts": 2, "no_match": 2, "few_seeds": 4,
    }  # fmt: skip
    assert ma.MIN_SEEDS == 3
    assert entry["problems"] == 1 and entry["seed_runs"] == 3  # exactly MIN_SEEDS is enough


def test_alert_ratios_pool_every_eligible_seed_of_every_problem():
    a = _run("uci:1", [0.05] * 5, [0.05] * 5)
    b = _run("uci:2", [0.05] * 5, [0.06] * 5)  # ratio 1.2 on all its seeds
    entry = ma.compare([a, b], "zscore", "ecod", draws=50)
    assert entry["seed_runs"] == 10
    assert entry["median_alert_ratio"] == pytest.approx(1.1)
    low, high = entry["alert_ratio_quartiles"]
    assert low == pytest.approx(1.0) and high == pytest.approx(1.2)


def test_a_comparison_with_no_eligible_problem_has_no_ratio_and_no_interval():
    run = _run("uci:1", [0.9] * 5, [0.05] * 5)
    entry = ma.compare([run], "zscore", "ecod", draws=50)
    assert entry["problems"] == 0 and entry["seed_runs"] == 0
    assert entry["median_alert_ratio"] is None and entry["alert_ratio_quartiles"] is None
    assert "recall" not in entry and "precision" not in entry
    assert entry["excluded_seed_runs"]["no_match"] == 5


def test_the_bootstrap_receives_one_cluster_per_original_source_and_the_requested_draws(
    monkeypatch,
):
    seen = []

    def spy(differences, clusters, *, by_cluster, draws):
        seen.append((differences.tolist(), clusters.tolist(), by_cluster, draws))
        return {"units": 0, "p_two_sided": 1.0}

    monkeypatch.setattr(ma, "bootstrap", spy)
    runs = [_run("adbench:glass", [0.05] * 5, [0.05] * 5), _run("uci:7", [0.05] * 5, [0.05] * 5)]
    ma.compare(runs, "zscore", "ecod", draws=321)
    assert [call[1] for call in seen] == [["uci:42", "uci:7"]] * 2
    assert all(call[2] is True and call[3] == 321 for call in seen)
    assert seen[0][0] == pytest.approx([0.3, 0.3])  # precision: learned 0.5 minus rule 0.2
    assert seen[1][0] == pytest.approx([0.1, 0.1])  # recall: learned 0.4 minus rule 0.3


def test_two_distinct_sources_make_two_units():
    runs = [_run("uci:1", [0.05] * 5, [0.05] * 5), _run("uci:2", [0.05] * 5, [0.05] * 5)]
    assert ma.compare(runs, "zscore", "ecod", draws=50)["recall"]["units"] == 2


def test_analyse_records_its_parameters_and_forwards_the_draws(monkeypatch):
    seen = []
    real = ma.bootstrap

    def spy(*args, draws, **kwargs):
        seen.append(draws)
        return real(*args, draws=draws, **kwargs)

    monkeypatch.setattr(ma, "bootstrap", spy)
    runs = [_run(f"uci:{i}", [0.05] * 5, [0.05] * 5) for i in range(3)]
    result = ma.analyse(runs, draws=77)
    assert set(seen) == {77}
    assert result["tolerance"] == 1.5 and result["min_seeds"] == 3 and result["draws"] == 77
    assert result["problems_read"] == 3 and len(result["comparisons"]) == 3


def test_a_failed_problem_file_does_not_stop_the_files_after_it(tmp_path):
    (tmp_path / "a_bad.json").write_text(json.dumps({"problem": "uci:1", "failed": "x"}))
    for name, problem in (("b.json", "uci:2"), ("c.json", "uci:3")):
        (tmp_path / name).write_text(json.dumps({"problem": problem, "runs": {"ecod": []}}))
    merged = ma.load(tmp_path)
    assert [m["problem"] for m in merged] == ["uci:2", "uci:3"]
    assert all(set(m) == {"problem", "runs"} for m in merged)


def test_main_writes_a_sorted_indented_analysis_and_returns_zero(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "a"
    folder.mkdir()
    (folder / "uci_1.json").write_text(json.dumps(_run("uci:1", [0.05] * 5, [0.05] * 5)))
    out = tmp_path / "result.json"
    monkeypatch.setattr(ma, "DRAWS", 40)
    real = ma.analyse
    monkeypatch.setattr(ma, "analyse", lambda runs, draws=40: real(runs, draws))
    assert ma.main([str(folder), "--output", str(out)]) == 0
    text = out.read_text()
    result = json.loads(text)
    assert text == json.dumps(result, indent=1, sort_keys=True) + "\n"
    assert result["problems_read"] == 1
    with pytest.raises(SystemExit) as stop:
        ma.main([str(folder)])
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        ma.main(["--help"])
    assert "Rules against learned detectors at comparable alert volume" in " ".join(
        capsys.readouterr().out.split()
    )


def test_a_holm_adjustment_of_the_wrong_length_is_refused(monkeypatch):
    runs = [_run(f"uci:{i}", [0.05] * 5, [0.05] * 5, precision=0.2 + 0.05 * i) for i in range(6)]
    monkeypatch.setattr(ma, "holm", lambda p: list(p)[:-1])
    with pytest.raises(ValueError, match="zip"):
        ma.analyse(runs, draws=20)
