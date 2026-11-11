"""Fixed thresholds under score-distribution shift (T170)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import score_shift as ss  # noqa: E402

RNG = np.random.default_rng(0)
FIT = RNG.normal(size=5000)
SCORES = RNG.normal(size=2000)


def test_a_baseline_changes_nothing_and_an_unknown_scenario_is_refused():
    fit, scores = ss.transform("baseline", 0.0, FIT, SCORES, 1)
    assert np.array_equal(fit, FIT) and np.array_equal(scores, SCORES)
    with pytest.raises(ValueError, match="unknown"):
        ss.transform("sideways", 1.0, FIT, SCORES, 1)


def test_location_and_scale_change_only_the_evaluated_scores_and_keep_their_ranking():
    sigma = FIT.std()
    fit, loc = ss.transform("location", 0.5, FIT, SCORES, 1)
    assert np.array_equal(fit, FIT) and np.allclose(loc, SCORES + 0.5 * sigma)
    fit, scaled = ss.transform("scale", 2.0, FIT, SCORES, 1)
    assert np.array_equal(fit, FIT) and np.array_equal(np.argsort(scaled), np.argsort(SCORES))
    centre = np.median(FIT)
    assert np.allclose(scaled, centre + 2.0 * (SCORES - centre))


def test_noise_is_reproducible_depends_on_the_seed_and_degrades_the_ranking():
    _, a = ss.transform("noise", 1.0, FIT, SCORES, 1)
    _, b = ss.transform("noise", 1.0, FIT, SCORES, 1)
    _, c = ss.transform("noise", 1.0, FIT, SCORES, 2)
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    assert not np.array_equal(np.argsort(a), np.argsort(SCORES))


def test_a_monotone_change_of_calibration_and_evaluation_together_keeps_the_alerts():
    y = (SCORES > 1.5).astype(int)
    base = ss.outcome(FIT, SCORES, y, 0.02)
    fit, scores = ss.transform("monotone_both", 0.0, FIT, SCORES, 1)
    changed = ss.outcome(fit, scores, y, 0.02)
    assert abs(changed["flagged"] - base["flagged"]) <= 1  # quantile interpolation only
    assert changed["recall"] == pytest.approx(base["recall"], abs=0.02)


def test_a_location_shift_of_the_evaluated_scores_alone_moves_the_alert_volume_not_the_ranking():
    y = np.r_[np.ones(100), np.zeros(1900)].astype(int)
    scores = np.r_[RNG.normal(3, 1, 100), RNG.normal(0, 1, 1900)]
    base = ss.outcome(FIT, scores, y, 0.05)
    _, up = ss.transform("location", 1.0, FIT, scores, 1)
    shifted = ss.outcome(FIT, up, y, 0.05)
    assert shifted["alert_over_budget"] > base["alert_over_budget"]
    assert ss.quality(y, up)["roc_auc"] == pytest.approx(ss.quality(y, scores)["roc_auc"])


def test_outcome_counts_alerts_precision_and_recall_exactly():
    fit = np.arange(100, dtype=float)
    scores = np.array([10.0, 99.5, 98.5, 97.0, 120.0])
    y = np.array([0, 1, 0, 1, 1])
    got = ss.outcome(fit, scores, y, 0.05)  # threshold: 95th percentile = 94.05
    assert got["flagged"] == 4 and got["alert_rate"] == pytest.approx(0.8)
    assert got["precision"] == pytest.approx(3 / 4) and got["recall"] == pytest.approx(1.0)
    assert got["alert_over_budget"] == pytest.approx(0.8 / 0.05)


def _problem(n=700, anomalies=70, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    x[:anomalies] += 4
    return x, y


def test_a_problem_records_every_scenario_and_budget_and_a_feature_shift_raises_the_alerts():
    x, y = _problem()
    result = ss.run_problem(x, y, seeds=(42,), methods=["isolation_forest"])
    record = result["runs"]["isolation_forest"][0]["scenarios"]
    assert set(record) == {f"{k}:{p:g}" for k, p in ss.SCENARIOS}
    for scenario in record.values():
        assert {"roc_auc", "ap"} <= set(scenario) and set(map(str, ss.BUDGETS)) <= set(scenario)
    assert (
        record["feature_shift:1"]["0.02"]["alert_over_budget"]
        > record["baseline:0"]["0.02"]["alert_over_budget"]
    )
    assert record["location:0.5"]["roc_auc"] == pytest.approx(record["baseline:0"]["roc_auc"])
    assert result["errors"] == {} and result["skipped"] == []


def _cell(ratio, ks, precision=0.5, recall=0.4, auc=0.9):
    cell = {
        "alert_over_budget": ratio,
        "ks_fit_vs_eval": ks,
        "precision": precision,
        "recall": recall,
    }
    return {"roc_auc": auc, "ap": 0.3, **{str(b): dict(cell) for b in ss.BUDGETS}}


def _runs(shifted_ratio, shifted_ks, shifted_auc=0.9, shifted_precision=0.5):
    base = {"baseline:0": _cell(1.0, 0.05)}
    moved = {"location:1": _cell(shifted_ratio, shifted_ks, shifted_precision, auc=shifted_auc)}
    fill = {f"{k}:{p:g}": _cell(1.0, 0.05) for k, p in ss.SCENARIOS} | base | moved
    return [
        {"problem": f"p{i}", "runs": {"ecod": [{"seed": 1, "scenarios": fill}]}} for i in range(3)
    ]


def test_monitors_fire_on_a_volume_breach_and_stay_quiet_without_a_shift():
    quiet = ss.monitor_table(_runs(1.0, 0.05))["location:1"]
    assert (
        quiet["volume_trigger"] == 0
        and quiet["ks_trigger"] == 0
        and quiet["deteriorated_fits"] == 0
    )
    breach = ss.monitor_table(_runs(3.0, 0.4, shifted_auc=0.8, shifted_precision=0.1))["location:1"]
    assert breach["volume_trigger"] == 1 and breach["ks_trigger"] == 1
    assert breach["ranking_deterioration"] == 1 and breach["precision_collapse"] == 1
    assert breach["deteriorated_fits"] == 3 and breach["volume_trigger_given_deteriorated"] == 1.0


def test_the_volume_band_and_the_ks_limit_are_closed_intervals():
    inside = ss.monitor_table(_runs(ss.VOLUME_BAND[1], ss.KS_LIMIT))["location:1"]
    assert inside["volume_trigger"] == 0 and inside["ks_trigger"] == 0
    outside = ss.monitor_table(_runs(ss.VOLUME_BAND[0] - 0.01, ss.KS_LIMIT + 0.01))["location:1"]
    assert outside["volume_trigger"] == 1 and outside["ks_trigger"] == 1


def test_the_summary_gives_medians_over_problems_per_method_and_pooled():
    table = ss.summarize(_runs(2.0, 0.3))
    cell = table["ecod"]["location:1"]["0.02"]
    assert cell["problems"] == 3 and cell["median_alert_over_budget"] == pytest.approx(2.0)
    assert table["all"]["baseline:0"]["0.01"]["median_roc_auc"] == pytest.approx(0.9)


def test_volume_false_alarms_are_stratified_by_the_expected_number_of_alerts():
    def run(rows, ratio):
        sc = {"baseline:0": {"0.02": {"alert_over_budget": ratio}}}
        return {"problem": "p", "rows": rows, "runs": {"ecod": [{"seed": 1, "scenarios": sc}]}}

    # expected alerts = rows * 0.15 * 0.02: 100 rows -> 0.3, 1,500 -> 4.5, 3,000 -> 9, 20,000 -> 60
    runs = [run(100, 3.0), run(1_500, 1.0), run(3_000, 0.4), run(20_000, 1.0), run(20_000, 1.1)]
    got = ss.volume_false_alarms(runs)
    assert got["fewer"] == {"fits": 2, "false_alarm": 0.5}
    assert got["between"] == {"fits": 1, "false_alarm": 1.0}
    assert got["enough"] == {"fits": 2, "false_alarm": 0.0}
    assert ss.volume_false_alarms([])["enough"] == {"fits": 0, "false_alarm": None}


def _scenario_run(problem, base_ratio, moved_ratio, base_auc=0.7, moved_auc=0.6):
    def sc(ratio, auc):
        cell = {"alert_over_budget": ratio, "precision": 0.5, "recall": 0.4, "ks_fit_vs_eval": 0.1}
        return {"roc_auc": auc, "ap": 0.3, **{str(b): dict(cell) for b in ss.BUDGETS}}

    full = {f"{k}:{p:g}": sc(base_ratio, base_auc) for k, p in ss.SCENARIOS}
    full["location:1"] = sc(moved_ratio, moved_auc)
    return {
        "problem": problem,
        "runs": {
            "ecod": [{"seed": 1, "scenarios": full}, {"seed": 2, "scenarios": full}],
            "hbos": [{"seed": 1, "scenarios": full}],
        },
    }


def test_contrasts_are_paired_per_problem_and_resample_whole_sources():
    # 12 sources of one problem each; the shifted alert ratio is baseline + 2 + (i % 3)
    runs = [_scenario_run(f"uci:{i}", 1.0 + i / 10, 3.0 + i / 10 + i % 3) for i in range(12)]
    got = ss.contrasts(runs, draws=300)
    assert (got["problems"], got["sources"], got["singleton_sources"]) == (12, 12, 12)
    entry = next(
        c
        for c in got["contrasts"]
        if c["scenario"] == "location:1" and c["metric"] == "alert_over_budget"
    )
    expected = np.mean([2.0 + i % 3 for i in range(12)])  # independent of the bootstrap
    assert entry["mean"] == pytest.approx(expected) and entry["units"] == 12
    assert entry["mean_ci"][0] <= expected <= entry["mean_ci"][1]
    auc = next(
        c for c in got["contrasts"] if c["scenario"] == "location:1" and c["metric"] == "roc_auc"
    )
    assert auc["mean"] == pytest.approx(-0.1)
    assert all(c["holm_p"] >= c["p_two_sided"] for c in got["contrasts"])
    assert len(got["contrasts"]) == (len(ss.SCENARIOS) - 1) * len(ss.CONTRAST_METRICS)


def test_problems_from_one_source_are_a_single_resampling_unit():
    # glass derives from UCI source 42, as does uci:42: three problems, two clusters
    runs = [_scenario_run(p, 1.0, 2.0) for p in ("adbench:glass", "uci:42", "uci:1")]
    runs += [_scenario_run(f"uci:{100 + i}", 1.0, 2.0) for i in range(9)]
    got = ss.contrasts(runs, draws=50)
    assert got["problems"] == 12 and got["sources"] == 11 and got["singleton_sources"] == 10


def test_too_few_independent_sources_give_no_interval():
    runs = [_scenario_run(f"uci:{i}", 1.0, 2.0) for i in range(ss.MIN_SOURCES - 1)]
    got = ss.contrasts(runs, draws=50)
    assert "insufficient" in got and got["contrasts"] == [] and got["sources"] == ss.MIN_SOURCES - 1
