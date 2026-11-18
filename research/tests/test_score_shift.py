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


# --- exact arithmetic, accounting and boundaries ------------------------------------------------

import copy  # noqa: E402
import json  # noqa: E402

import pandas as pd  # noqa: E402
from scipy.stats import ks_2samp  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402


def test_the_scale_of_a_shift_is_the_training_spread_and_one_when_that_spread_is_zero():
    flat = np.full(50, 3.0)
    _, moved = ss.transform("location", 2.0, flat, np.array([1.0, 2.0]), 1)
    assert moved.tolist() == [3.0, 4.0]  # sigma falls back to exactly 1.0
    spread = np.array([0.0, 2.0])  # std 1.0
    _, widened = ss.transform("location", -1.0, spread * 3, np.array([0.0]), 1)
    assert widened.tolist() == [-3.0]  # std 3.0


def test_noise_is_the_documented_seeded_draw_scaled_by_parameter_and_spread():
    assert ss.NOISE_SEED == 7
    fit, scores = np.array([0.0, 4.0, 8.0]), np.array([1.0, 2.0, 3.0, 4.0])
    sigma = float(np.std(fit))
    expected = scores + 0.5 * sigma * np.random.default_rng([7, 9]).standard_normal(4)
    _, got = ss.transform("noise", 0.5, fit, scores, 9)
    assert np.array_equal(got, expected)


def test_the_monotone_scenario_transforms_calibration_and_evaluation_scores_alike():
    fit, scores = np.array([0.0, 1.0, 5.0]), np.array([2.0, -3.0])
    new_fit, new_scores = ss.transform("monotone_both", 0.0, fit, scores, 1)
    assert np.array_equal(new_fit, np.arcsinh(fit)) and np.array_equal(
        new_scores, np.arcsinh(scores)
    )
    with pytest.raises(ValueError, match="^unknown score scenario: sideways$"):
        ss.transform("sideways", 1.0, fit, scores, 1)


def test_a_score_equal_to_the_threshold_is_no_alert_and_a_silent_window_has_zero_precision():
    fit = np.array([0.0] * 90 + [1.0] * 10)  # the 5% threshold is exactly 1.0
    y = np.array([0, 1, 0, 1])
    got = ss.outcome(fit, np.array([0.0, 1.0, 1.0, 1.0]), y, 0.05)
    assert got["flagged"] == 0 and got["precision"] == 0.0 and got["recall"] == 0.0
    assert got["alert_rate"] == 0.0 and got["alert_over_budget"] == 0.0
    scores = np.array([0.5, 2.0, 1.0, 3.0])
    got = ss.outcome(fit, scores, y, 0.05)
    assert got["flagged"] == 2 and got["precision"] == 1.0 and got["recall"] == 1.0
    assert got["alert_rate"] == 0.5 and got["alert_over_budget"] == pytest.approx(10.0)
    assert got["ks_fit_vs_eval"] == pytest.approx(float(ks_2samp(fit, scores).statistic))


def _detector_stub(monkeypatch):
    calls = {}

    class Detector:
        def fit(self, rows):
            calls["fit"] = len(rows)

        def score(self, frame):
            return frame["f0"].to_numpy()

    def build(method, contamination, seed):
        calls["build"] = (method, contamination, seed)
        return Detector()

    def capped(train, method, seed):
        calls["capped"] = (method, seed)
        return train

    def fit_scores(detector, rows):
        calls["fit_scores"] = len(rows)
        return np.arange(100.0)

    monkeypatch.setattr(ss, "build", build)
    monkeypatch.setattr(ss, "capped", capped)
    monkeypatch.setattr(ss, "fit_scores", fit_scores)
    return calls


def test_run_method_scores_every_scenario_from_the_fixed_detector(monkeypatch):
    calls = _detector_stub(monkeypatch)
    train = pd.DataFrame({"f0": np.zeros(100)})
    test = pd.DataFrame({"f0": np.arange(10.0) * 12})
    y = np.array([0, 0, 0, 0, 0, 0, 0, 1, 1, 1])
    row = ss.run_method("hbos", train, test, y, 5)
    assert calls == {"build": ("hbos", ss.FIXED_BUILD, 5), "capped": ("hbos", 5),
                     "fit": 100, "fit_scores": 100}  # fmt: skip
    assert row["seed"] == 5
    assert list(row["scenarios"]) == [f"{k}:{p:g}" for k, p in ss.SCENARIOS]
    fit, scores = np.arange(100.0), np.arange(10.0) * 12
    base = row["scenarios"]["baseline:0"]
    assert base["roc_auc"] == pytest.approx(roc_auc_score(y, scores))
    assert base["ap"] == pytest.approx(average_precision_score(y, scores))
    assert base["0.05"] == ss.outcome(fit, scores, y, 0.05)
    assert set(base) == {"roc_auc", "ap", *map(str, ss.BUDGETS)}
    moved = row["scenarios"]["feature_shift:0.5"]  # one feature unit moves the score by 0.5 here
    assert moved["0.05"] == ss.outcome(fit, scores + 0.5, y, 0.05)
    location = row["scenarios"]["location:-1"]
    assert location["0.02"] == ss.outcome(fit, scores - float(np.std(fit)), y, 0.02)


def _problem_xy(n=700, anomalies=70):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    x[:anomalies] += 4
    return x, y


def test_failures_are_recorded_per_method_and_never_stop_the_other_detectors(monkeypatch):
    x, y = _problem_xy()
    real = ss.run_method

    def flaky(method, *args):
        if method == "hbos":
            raise RuntimeError("boom")
        return real(method, *args)

    monkeypatch.setattr(ss, "run_method", flaky)
    result = ss.run_problem(x, y, seeds=(42, 1), methods=("hbos", "ecod"))
    assert result["seeds"] == [42, 1]
    assert result["errors"] == {"hbos": [{"seed": 42, "error": "RuntimeError('boom')"},
                                         {"seed": 1, "error": "RuntimeError('boom')"}]}  # fmt: skip
    assert [r["seed"] for r in result["runs"]["ecod"]] == [42, 1] and result["skipped"] == []


def test_skipped_detectors_never_stop_the_rest_and_accumulate_over_seeds(monkeypatch):
    x, y = _problem_xy()
    sequence = iter([{"knn"}, {"lof"}])
    monkeypatch.setattr(ss.nm, "skipped_detectors", lambda n: next(sequence))
    result = ss.run_problem(x, y, seeds=(1, 2), methods=("knn", "lof", "hbos"))
    assert result["skipped"] == ["knn", "lof"]  # skipped on one seed each, both remembered
    assert [len(result["runs"][m]) for m in ("hbos", "knn", "lof")] == [2, 1, 1]


def test_each_seed_uses_its_own_split_and_the_documented_default_detectors(monkeypatch):
    x, y = _problem_xy(n=300, anomalies=30)
    seen = []
    real_split = ss.nm.split

    def split(xx, yy, seed):
        seen.append(seed)
        return real_split(xx, yy, seed)

    monkeypatch.setattr(ss.nm, "split", split)
    monkeypatch.setattr(ss, "run_method", lambda method, train, test, yt, seed: {"seed": seed})
    result = ss.run_problem(x, y, seeds=(3, 4))
    assert seen == [3, 4] and sorted(result["runs"]) == sorted(ss.METHODS)


def test_a_job_reads_its_source_and_a_failure_is_returned_not_dropped(monkeypatch):
    x, y = _problem_xy(n=40, anomalies=10)
    seen = {}

    def adbench(name, path):
        seen["adbench"] = (name, path)
        return x, y, {"name": name}

    def uci(meta, path):
        seen["uci"] = (meta, path)
        return x, y, {"name": "toy"}

    monkeypatch.setattr(ss.lb, "load_adbench", adbench)
    monkeypatch.setattr(ss.lb, "load_uci", uci)
    monkeypatch.setattr(ss, "run_problem", lambda xx, yy: {"seeds": [1], "runs": {}})
    out = ss.run_job({"problem": "adbench:t", "source": "adbench", "name": "t", "path": "/d/t"})
    assert seen["adbench"] == ("t", Path("/d/t")) and "uci" not in seen
    assert out == {"problem": "adbench:t", "rows": 40, "prevalence": 0.25, "seeds": [1], "runs": {}}
    ss.run_job({"problem": "uci:7", "source": "uci", "meta": {"id": 7}, "path": "/d/7"})
    assert seen["uci"] == ({"id": 7}, Path("/d/7"))

    def broken(*args):
        raise OSError("disk")

    monkeypatch.setattr(ss.lb, "load_uci", broken)
    failed = ss.run_job({"problem": "uci:7", "source": "uci", "meta": {}, "path": "p"})
    assert failed == {"problem": "uci:7", "failed": "OSError('disk')"}


def test_the_summary_keeps_each_detector_apart_from_the_pooled_row_and_skips_empty_cells():
    def run(problem, ecod_ratio, hbos_ratio):
        full = {f"{k}:{p:g}": _cell(1.0, 0.05) for k, p in ss.SCENARIOS}
        full["location:1"] = _cell(ecod_ratio, 0.05)
        other = dict(full) | {"location:1": _cell(hbos_ratio, 0.05)}
        runs = {"ecod": [{"seed": 1, "scenarios": full}], "hbos": [{"seed": 1, "scenarios": other}]}
        return {"problem": problem, "runs": runs}

    only_ecod = {"problem": "c", "runs": {"ecod": run("c", 6.0, 0)["runs"]["ecod"]}}
    table = ss.summarize(
        [run("a", 2.0, 4.0), run("b", 2.0, 4.0), only_ecod, {"problem": "d", "runs": {}}]
    )
    key = ("location:1", "0.02", "median_alert_over_budget")
    assert table["ecod"][key[0]][key[1]][key[2]] == pytest.approx(2.0)
    assert table["ecod"]["location:1"]["0.02"]["problems"] == 3
    assert table["hbos"]["location:1"]["0.02"]["problems"] == 2
    assert table["hbos"]["location:1"]["0.02"][key[2]] == pytest.approx(4.0)
    assert table["all"]["location:1"]["0.02"][key[2]] == pytest.approx(
        3.0
    )  # mean of 2 and 4, then 6


def test_the_ranking_and_precision_limits_are_inclusive_and_strict_as_documented(monkeypatch):
    monkeypatch.setattr(ss, "AUC_DROP", 0.25)
    monkeypatch.setattr(ss, "PRECISION_FLOOR", 0.5)
    runs = _runs(1.0, 0.05, shifted_auc=0.75, shifted_precision=0.25)  # base auc 0.9 -> drop 0.15
    quiet = ss.monitor_table(runs)["location:1"]
    assert quiet["ranking_deterioration"] == 0 and quiet["precision_collapse"] == 0
    for run in runs:
        run["runs"]["ecod"][0]["scenarios"]["baseline:0"]["roc_auc"] = 1.0
    boundary = ss.monitor_table(runs)["location:1"]  # drop exactly 0.25 counts
    assert boundary["ranking_deterioration"] == 1 and boundary["precision_collapse"] == 0


def test_a_deteriorated_fit_needs_only_one_of_ranking_or_precision_and_shares_are_exact():
    runs = _runs(3.0, 0.4, shifted_auc=0.9, shifted_precision=0.1)  # precision collapse only
    runs[0] = copy.deepcopy(runs[0])  # the three problems share their scenario cells
    runs[0]["runs"]["ecod"][0]["scenarios"]["location:1"]["0.02"]["ks_fit_vs_eval"] = 0.05
    got = ss.monitor_table(runs)["location:1"]
    assert got["fits"] == 3 and got["deteriorated_fits"] == 3
    assert got["ranking_deterioration"] == 0 and got["precision_collapse"] == 1
    assert got["ks_trigger"] == pytest.approx(2 / 3)
    assert got["ks_trigger_given_deteriorated"] == pytest.approx(2 / 3)
    assert got["volume_trigger_given_deteriorated"] == 1.0
    assert set(got) == {
        "fits",
        "volume_trigger",
        "ks_trigger",
        "ranking_deterioration",
        "precision_collapse",
        "deteriorated_fits",
        "volume_trigger_given_deteriorated",
        "ks_trigger_given_deteriorated",
    }
    quiet = ss.monitor_table(_runs(1.0, 0.05))["location:1"]
    assert quiet["volume_trigger_given_deteriorated"] is None
    assert quiet["ks_trigger_given_deteriorated"] is None


def test_a_scenario_nobody_ran_is_absent_and_the_next_one_is_still_reported():
    assert ss.monitor_table([]) == {}
    assert ss.monitor_table(_runs(1.0, 0.05)).keys() == {f"{k}:{p:g}" for k, p in ss.SCENARIOS}


def test_the_volume_band_edges_and_the_alert_bins_are_closed_on_the_documented_side(monkeypatch):
    monkeypatch.setattr(ss, "TEST_SHARE", 1.0)

    def run(rows, ratio):
        sc = {"baseline:0": {"0.01": {"alert_over_budget": ratio}}}
        return {"problem": "p", "rows": rows, "runs": {"ecod": [{"seed": 1, "scenarios": sc}]}}

    # expected alerts: 500 rows -> 5.0 (between), 3000 rows -> 30.0 (enough), 499 -> fewer
    runs = [run(499, ss.VOLUME_BAND[0]), run(500, ss.VOLUME_BAND[1]), run(3000, 1.0)]
    got = ss.volume_false_alarms(runs, budget=0.01)
    assert got["fewer"] == {"fits": 1, "false_alarm": 0.0}  # the band's lower edge is inside
    assert got["between"] == {"fits": 1, "false_alarm": 0.0}  # and so is its upper edge
    assert got["enough"] == {"fits": 1, "false_alarm": 0.0}
    outside = ss.volume_false_alarms([run(500, 0.49), run(500, 2.01)], budget=0.01)
    assert outside["between"] == {"fits": 2, "false_alarm": 1.0}


def test_contrasts_report_their_parameters_a_message_and_resample_sources_with_the_draws(
    monkeypatch,
):
    runs = [_scenario_run(f"uci:{i}", 1.0, 2.0) for i in range(ss.MIN_SOURCES)]
    seen = []

    def spy(diff, clusters, *, by_cluster, draws):
        seen.append((clusters.tolist(), by_cluster, draws))
        return {"units": 0, "p_two_sided": 0.5}

    monkeypatch.setattr(ss, "bootstrap", spy)
    got = ss.contrasts(runs, budget=0.05, draws=21)
    assert got["budget"] == 0.05 and got["draws"] == 21 and "insufficient" not in got
    assert seen and all(c[1] is True and c[2] == 21 and len(c[0]) == 10 for c in seen)
    few = ss.contrasts(runs[:-1], draws=21)
    assert few["insufficient"] == "fewer than 10 independent sources" and few["contrasts"] == []
    assert few["draws"] == 21 and few["budget"] == 0.02


def test_summarizing_a_folder_writes_every_analysis_and_skips_failed_problems(tmp_path):
    folder = tmp_path / "runs"
    folder.mkdir()
    for i in range(ss.MIN_SOURCES):
        run = _scenario_run(f"uci:{i}", 1.0, 2.0) | {"rows": 1000}
        (folder / f"uci_{i}.json").write_text(json.dumps(run))
    (folder / "uci_99.json").write_text(json.dumps({"problem": "uci:99", "failed": "x"}))
    assert [r["problem"] for r in ss.load(folder)] == [f"uci:{i}" for i in range(10)]
    out = tmp_path / "doc.json"
    assert ss.main(["--summarize", str(folder), "--output", str(out)]) == 0
    text = out.read_text()
    doc = json.loads(text)
    assert text == json.dumps(doc, indent=1, sort_keys=True) + "\n"
    assert set(doc) == {"problems", "summary", "monitors", "volume_false_alarms", "contrasts"}
    assert doc["problems"] == 10 and doc["contrasts"]["problems"] == 10
    assert doc["monitors"]["location:1"]["fits"] == 30


class _SyncPool:
    created = []

    def __init__(self, max_workers):
        self.max_workers = max_workers
        _SyncPool.created.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, items):
        return [fn(item) for item in items]


def test_the_command_line_writes_one_file_per_problem_and_can_resume(tmp_path, monkeypatch, capsys):
    jobs = [{"problem": "adbench:a"}, {"problem": "uci:7"}]
    ran = []

    def run_job(job):
        ran.append(job["problem"])
        return {"problem": job["problem"], "rows": 1} if job["problem"] == "adbench:a" else {
            "problem": job["problem"], "failed": "boom"}  # fmt: skip

    seen = {}
    monkeypatch.setattr(ss.lb, "jobs", lambda r, a, p: seen.setdefault("args", (r, a, p)) and jobs)
    monkeypatch.setattr(ss, "run_job", run_job)
    monkeypatch.setattr(ss, "ProcessPoolExecutor", _SyncPool)
    out = tmp_path / "deep" / "out"
    assert ss.main(["--output", str(out), "--workers", "3"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["adbench_a.json", "uci_7.json"]
    assert (out / "uci_7.json").read_text() == json.dumps(
        {"problem": "uci:7", "failed": "boom"}, sort_keys=True
    ) + "\n"
    assert capsys.readouterr().out.splitlines() == ["adbench:a ok", "uci:7 boom"]
    assert _SyncPool.created[0].max_workers == 3
    root = Path(ss.__file__).resolve().parent.parent
    assert seen["args"] == (root / "verification/evidence/dataset_registry",
                            root / "data" / "adbench", root / "data" / "pool")  # fmt: skip
    ran.clear()
    assert ss.main(["--output", str(out), "--resume", "--only", "uci:7", "adbench:a"]) == 0
    assert ran == []  # both results exist
    (out / "uci_7.json").unlink()
    assert ss.main(["--output", str(out), "--resume"]) == 0 and ran == ["uci:7"]
    ran.clear()
    assert ss.main(["--output", str(out), "--only", "uci:7"]) == 0 and ran == ["uci:7"]
    with pytest.raises(SystemExit) as stop:
        ss.main([])
    assert stop.value.code == 2


def test_the_monitor_band_is_closed_at_both_edges():
    for ratio in ss.VOLUME_BAND:
        assert ss.monitor_table(_runs(ratio, 0.05))["location:1"]["volume_trigger"] == 0


def test_a_baseline_precision_of_zero_cannot_collapse():
    runs = _runs(1.0, 0.05, shifted_precision=0.0)
    for run in runs:
        cells = run["runs"]["ecod"][0]["scenarios"]
        cells["baseline:0"] = copy.deepcopy(cells["baseline:0"])
        for budget in map(str, ss.BUDGETS):
            cells["baseline:0"][budget]["precision"] = 0.0
    assert ss.monitor_table(runs)["location:1"]["precision_collapse"] == 0


def test_a_job_hands_the_loaded_table_and_labels_to_the_run(monkeypatch):
    x, y = _problem_xy(n=40, anomalies=10)
    seen = {}
    monkeypatch.setattr(ss.lb, "load_adbench", lambda n, p: (x, y, {"name": n}))
    monkeypatch.setattr(ss, "run_problem", lambda xx, yy: seen.update(x=xx, y=yy) or {})
    ss.run_job({"problem": "adbench:t", "source": "adbench", "name": "t", "path": "p"})
    assert seen["x"] is x and seen["y"] is y


def test_each_problem_run_gives_the_detector_named_feature_columns(monkeypatch):
    x, y = _problem_xy(n=300, anomalies=30)
    frames = []
    monkeypatch.setattr(
        ss, "run_method", lambda m, train, test, yt, seed: frames.append((train, test)) or {}
    )
    ss.run_problem(x, y, seeds=(1,), methods=("hbos",))
    train, test = frames[0]
    assert list(train.columns) == ["f0", "f1", "f2", "f3"] == list(test.columns)


def test_the_command_line_defaults_to_four_workers_and_documents_its_options(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(ss.lb, "jobs", lambda r, a, p: [])
    monkeypatch.setattr(ss, "ProcessPoolExecutor", _SyncPool)
    _SyncPool.created.clear()
    assert (
        ss.main(["--output", str(tmp_path), "--registry", "r", "--adbench", "a", "--pool", "p"])
        == 0
    )
    assert _SyncPool.created[0].max_workers == 4
    seen = []
    monkeypatch.setattr(ss.lb, "jobs", lambda r, a, p: seen.append((r, a, p)) or [])
    ss.main(["--output", str(tmp_path), "--registry", "r", "--adbench", "a", "--pool", "p"])
    assert seen == [(Path("r"), Path("a"), Path("p"))]
    with pytest.raises(SystemExit):
        ss.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "summarize this run folder instead of running" in text
    assert "--summarize SUMMARIZE summarize this run folder instead of running" in text
    assert "Fixed deployment thresholds under score-distribution shift" in text


def test_a_holm_adjustment_of_the_wrong_length_is_refused(monkeypatch):
    runs = [_scenario_run(f"uci:{i}", 1.0 + i / 10, 3.0 + i / 10 + i % 3) for i in range(12)]
    monkeypatch.setattr(ss, "holm", lambda p: list(p)[:-1])
    with pytest.raises(ValueError, match="zip"):
        ss.contrasts(runs, draws=20)


def test_a_problem_without_fits_does_not_hide_the_problems_after_it():
    runs = [{"problem": "uci:empty", "runs": {}}] + [
        _scenario_run(f"uci:{i}", 1.0 + i / 10, 3.0 + i / 10 + i % 3) for i in range(12)
    ]
    got = ss.contrasts(runs, draws=30)
    assert got["problems"] == 12 and got["contrasts"]


def test_the_scenarios_come_from_every_problem_even_when_it_has_a_single_fit():
    def single(i):
        run = _scenario_run(f"uci:{i}", 1.0 + i / 10, 3.0 + i / 10 + i % 3)
        run["runs"] = {"ecod": run["runs"]["ecod"][:1]}
        return run

    got = ss.contrasts([single(i) for i in range(12)], draws=30)
    assert got["problems"] == 12 and got["contrasts"]


def test_progress_lines_are_flushed_as_they_arrive(tmp_path, monkeypatch):
    monkeypatch.setattr(ss.lb, "jobs", lambda r, a, p: [{"problem": "adbench:a"}])
    monkeypatch.setattr(ss, "run_job", lambda job: {"problem": job["problem"]})
    monkeypatch.setattr(ss, "ProcessPoolExecutor", _SyncPool)
    calls = []
    monkeypatch.setattr(ss, "print", lambda *a, **k: calls.append((a, k)), raising=False)
    ss.main(["--output", str(tmp_path / "o")])
    assert calls == [(("adbench:a", "ok"), {"flush": True})]
