"""Fixed thresholds under prior (prevalence) shift (T169)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prevalence_shift as ps  # noqa: E402


def _cell(tp=40, fn=60, fp=20, tn=880, nominal=0.05):
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "nominal": nominal}


def test_the_formulas_for_alert_rate_precision_recall_and_fpr():
    got = ps.shifted(_cell(), 0.10)
    tpr, fpr = 0.4, 20 / 900
    alert = 0.1 * tpr + 0.9 * fpr
    assert got["alert_rate"] == pytest.approx(alert)
    assert got["recall"] == pytest.approx(tpr) and got["fpr"] == pytest.approx(fpr)
    assert got["precision"] == pytest.approx(0.1 * tpr / alert)
    assert got["f1"] == pytest.approx(2 * got["precision"] * tpr / (got["precision"] + tpr))
    assert got["alert_over_budget"] == pytest.approx(alert / 0.05)


def test_the_observed_prevalence_reproduces_the_observed_cell():
    cell = _cell()
    n = cell["tp"] + cell["fn"] + cell["fp"] + cell["tn"]
    got = ps.shifted(cell, (cell["tp"] + cell["fn"]) / n)
    assert got["alert_rate"] == pytest.approx((cell["tp"] + cell["fp"]) / n)
    assert got["precision"] == pytest.approx(cell["tp"] / (cell["tp"] + cell["fp"]))


def test_recall_and_fpr_do_not_move_with_prevalence_but_alert_volume_and_precision_do():
    low, high = ps.shifted(_cell(), 0.01), ps.shifted(_cell(), 0.20)
    assert low["recall"] == high["recall"] and low["fpr"] == high["fpr"]
    assert high["alert_rate"] > low["alert_rate"] and high["precision"] > low["precision"]


def test_the_expectation_matches_a_resampled_population():
    rng = np.random.default_rng(0)
    anomalies, normals = rng.normal(2.0, 1.0, 50_000), rng.normal(0.0, 1.0, 50_000)
    threshold = 1.5
    cell = {
        "tp": int((anomalies > threshold).sum()), "fn": int((anomalies <= threshold).sum()),
        "fp": int((normals > threshold).sum()), "tn": int((normals <= threshold).sum()),
        "nominal": 0.05,
    }  # fmt: skip
    for pi in (0.01, 0.05, 0.2):
        size = 400_000
        k = rng.binomial(size, pi)
        sample = np.r_[rng.choice(anomalies, k), rng.choice(normals, size - k)]
        labels = np.r_[np.ones(k), np.zeros(size - k)]
        flags = sample > threshold
        expected = ps.shifted(cell, pi)
        assert flags.mean() == pytest.approx(expected["alert_rate"], abs=2e-3)
        assert (flags & (labels == 1)).sum() / max(flags.sum(), 1) == pytest.approx(
            expected["precision"], abs=0.02
        )


@pytest.mark.parametrize("pi", [0.0, 1.0, -0.1, 1.5])
def test_an_invalid_prevalence_is_refused(pi):
    with pytest.raises(ValueError, match="prevalence"):
        ps.shifted(_cell(), pi)


def test_a_cell_without_positives_or_negatives_is_refused_and_silence_gives_zero_precision():
    with pytest.raises(ValueError, match="positives and negatives"):
        ps.shifted(_cell(tp=0, fn=0), 0.1)
    with pytest.raises(ValueError, match="positives and negatives"):
        ps.shifted(_cell(fp=0, tn=0), 0.1)
    silent = ps.shifted(_cell(tp=0, fn=10, fp=0, tn=90), 0.1)
    assert silent["alert_rate"] == 0.0 and silent["precision"] == 0.0 and silent["f1"] == 0.0


def _run(problem, cell, infeasible=False):
    budgets = {"0.05": {"nominal": 0.05, "infeasible": "few rows"} if infeasible else cell}
    return {
        "problem": problem,
        "runs": {"hbos": [{"seed": s, "budgets": budgets} for s in range(3)]},
    }


def test_the_summary_counts_problems_seed_runs_and_the_smallest_class_and_skips_infeasible():
    runs = [
        _run("uci:1", _cell()),
        _run("uci:2", _cell(tp=10, fn=10, fp=5, tn=75)),
        _run("uci:3", _cell(), True),
    ]
    out = ps.summarize(runs, budgets=(0.05,), prevalences=(0.02, 0.2), draws=200)
    entry = out["table"]["hbos"]["0.05"]
    assert (entry["problems"], entry["seed_runs"]) == (2, 6)
    assert (entry["min_positives"], entry["min_negatives"]) == (20, 80)
    assert set(entry["by_prevalence"]) == {"0.02", "0.2"}
    median = entry["by_prevalence"]["0.2"]["recall"]["median"]
    assert median == pytest.approx(np.median([0.4, 0.5]))


def _cells_run(problem, tp, fn, fp, tn):
    cell = {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "nominal": 0.02}
    runs = {"hbos": [{"seed": s, "budgets": {"0.02": cell}} for s in range(2)]}
    return {"problem": problem, "runs": runs}


def test_contrasts_compare_each_prevalence_with_the_problems_own_observed_one():
    runs = [_cells_run(f"uci:{i}", 4 + i, 6, 3, 87 - i) for i in range(12)]
    got = ps.contrasts(runs, prevalences=(0.1, 0.5), draws=200)
    assert (got["problems"], got["sources"], got["singleton_sources"]) == (12, 12, 12)
    entry = next(
        c for c in got["contrasts"] if c["prevalence"] == 0.5 and c["metric"] == "precision"
    )
    expected = []
    for i in range(12):  # independent calculation of the same difference
        tp, fn, fp, tn = 4 + i, 6, 3, 87 - i
        tpr, fpr = tp / (tp + fn), fp / (fp + tn)
        observed = tp / (tp + fp)
        moved = 0.5 * tpr / (0.5 * tpr + 0.5 * fpr)
        expected.append(moved - observed)
    assert entry["mean"] == pytest.approx(np.mean(expected))
    assert all(c["holm_p"] >= c["p_two_sided"] for c in got["contrasts"])
    assert len(got["contrasts"]) == 2 * len(ps.CONTRAST_METRICS)


def test_the_observed_prevalence_is_a_zero_contrast_and_few_sources_give_no_interval():
    runs = [_cells_run(f"uci:{i}", 5, 5, 2, 88) for i in range(ps.MIN_SOURCES)]
    observed = 10 / 100
    got = ps.contrasts(runs, prevalences=(observed,), draws=100)
    assert all(c["mean"] == pytest.approx(0.0) for c in got["contrasts"])
    few = ps.contrasts(runs[: ps.MIN_SOURCES - 1], draws=50)
    assert "insufficient" in few and few["contrasts"] == []
