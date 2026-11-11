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


# --- messages, boundaries, the exact reweighting and what reaches the source-clustered bootstrap --

import json  # noqa: E402


def test_the_refusals_state_what_was_wrong_in_full():
    with pytest.raises(ValueError, match=r"^prevalence must be in \(0, 1\)$"):
        ps.shifted(_cell(), 1.0)
    with pytest.raises(ValueError, match="^a cell needs held-out positives and negatives$"):
        ps.shifted(_cell(tp=0, fn=0), 0.1)


def test_a_single_held_out_positive_or_negative_is_enough_to_read_the_rates():
    one_positive = ps.shifted(_cell(tp=1, fn=0, fp=2, tn=7), 0.5)
    assert one_positive["recall"] == 1.0 and one_positive["fpr"] == pytest.approx(2 / 9)
    one_negative = ps.shifted(_cell(tp=3, fn=1, fp=0, tn=1), 0.5)
    assert one_negative["fpr"] == 0.0 and one_negative["recall"] == pytest.approx(0.75)


def test_f1_is_the_harmonic_mean_even_when_precision_and_recall_are_small_or_unequal():
    got = ps.shifted(_cell(tp=1, fn=9, fp=1, tn=89), 0.1)  # tpr 0.1, fpr 1/90
    alert = 0.1 * 0.1 + 0.9 * (1 / 90)
    precision = 0.1 * 0.1 / alert
    assert got["precision"] == pytest.approx(precision)
    assert got["f1"] == pytest.approx(2 * precision * 0.1 / (precision + 0.1))
    low = ps.shifted(_cell(tp=1, fn=99, fp=0, tn=100), 0.1)  # precision 1, tpr 0.01
    assert low["precision"] == 1.0 and low["f1"] == pytest.approx(2 * 0.01 / 1.01)
    assert low["alert_over_budget"] == pytest.approx(low["alert_rate"] / 0.05)


class _Spy:
    """Stands in for the bootstrap and keeps what it was given."""

    def __init__(self):
        self.calls = []

    def __call__(self, values, clusters, *, by_cluster, draws):
        self.calls.append((values.tolist(), clusters.tolist(), by_cluster, draws))
        return {"units": len(set(clusters.tolist())), "p_two_sided": 0.5, "mean": 0.0}


def test_the_summary_resamples_whole_sources_and_reports_its_parameters(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(ps, "bootstrap", spy)
    runs = [_run("uci:42", _cell()), _run("adbench:glass", _cell()), _run("uci:7", _cell())]
    out = ps.summarize(runs, budgets=(0.05,), prevalences=(0.1,), draws=33)
    assert out["prevalences"] == [0.1] and out["budgets"] == [0.05]
    assert len(spy.calls) == len(ps.METRICS)
    assert all(
        c[1] == ["uci:42", "uci:42", "uci:7"] and c[2] is True and c[3] == 33 for c in spy.calls
    )
    assert out["table"]["hbos"]["0.05"]["by_prevalence"]["0.1"]["recall"]["units"] == 2


def test_problems_that_did_not_evaluate_a_detector_are_skipped_without_losing_later_ones():
    infeasible = _run("uci:1", _cell(), infeasible=True)
    rule_only = {"problem": "uci:2", "runs": {"zscore": [{"seed": 0, "rule": {"tp": 1}}]}}
    other_method = {
        "problem": "uci:3",
        "runs": {"ecod": [{"seed": 0, "budgets": {"0.05": _cell()}}]},
    }
    good = _run("uci:4", _cell())
    out = ps.summarize([infeasible, rule_only, other_method, good], budgets=(0.05,),
                       prevalences=(0.1,), draws=20)  # fmt: skip
    assert set(out["table"]) == {"ecod", "hbos"}  # a rule has no budget cell and no row
    assert out["table"]["hbos"]["0.05"]["problems"] == 1
    assert out["table"]["ecod"]["0.05"]["problems"] == 1


def _many(n, extra=()):
    return [_cells_run(f"uci:{i}", 4 + i, 6, 3, 87 - i) for i in range(n)] + list(extra)


def test_exactly_the_minimum_number_of_sources_gives_intervals_and_the_message_is_exact():
    got = ps.contrasts(_many(ps.MIN_SOURCES), prevalences=(0.1,), draws=30)
    assert "insufficient" not in got and len(got["contrasts"]) == len(ps.CONTRAST_METRICS)
    assert got["budget"] == 0.02 and got["draws"] == 30
    few = ps.contrasts(_many(ps.MIN_SOURCES - 1), draws=30)
    assert few["insufficient"] == "fewer than 10 independent sources"
    assert few["budget"] == 0.02 and few["draws"] == 30 and few["sources"] == 9


def test_two_problems_of_one_source_are_one_unit_and_singletons_are_counted():
    runs = _many(9, [_cells_run("uci:42", 5, 5, 2, 88), _cells_run("adbench:glass", 5, 5, 2, 88)])
    got = ps.contrasts(runs, prevalences=(0.1,), draws=30)
    assert got["problems"] == 11 and got["sources"] == 10 and got["singleton_sources"] == 9


def test_the_contrast_bootstrap_resamples_sources_with_the_requested_draws(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(ps, "bootstrap", spy)
    runs = _many(11)
    runs[1] = _cells_run("adbench:glass", 5, 5, 2, 88)
    runs[2] = _cells_run("uci:42", 5, 5, 2, 88)
    got = ps.contrasts(runs, prevalences=(0.1, 0.3), draws=44)
    assert len(spy.calls) == 4 and all(c[2] is True and c[3] == 44 for c in spy.calls)
    assert all(c[1].count("uci:42") == 2 for c in spy.calls)
    assert [c["holm_p"] for c in got["contrasts"]] == [1.0] * 4  # four p = 0.5, Holm-adjusted
    assert [(c["prevalence"], c["metric"]) for c in got["contrasts"]] == [
        (0.1, "alert_over_budget"), (0.1, "precision"), (0.3, "alert_over_budget"), (0.3, "precision"),
    ]  # fmt: skip


def test_contrasts_use_only_feasible_budget_cells_and_never_stop_at_an_empty_problem():
    empty = {"problem": "uci:90", "runs": {"zscore": [{"seed": 0, "rule": {"tp": 1}}]}}
    infeasible = {"problem": "uci:91", "runs": {"hbos": [{"seed": 0, "budgets": {
        "0.02": {"nominal": 0.02, "infeasible": "few rows"}}}]}}  # fmt: skip
    other_budget = {"problem": "uci:92", "runs": {"hbos": [{"seed": 0, "budgets": {
        "0.05": {"tp": 1, "fn": 1, "fp": 1, "tn": 1, "nominal": 0.05}}}]}}  # fmt: skip
    got = ps.contrasts([empty, infeasible, other_budget, *_many(10)], prevalences=(0.1,), draws=20)
    assert got["problems"] == 10 and got["sources"] == 10


def test_main_writes_the_summary_and_a_contrast_block_for_each_budget(tmp_path):
    folder = tmp_path / "runs"
    folder.mkdir()
    for i in range(ps.MIN_SOURCES):
        run = {"problem": f"uci:{i}", "runs": {"hbos": [{"seed": 0, "budgets": {
            k: {"tp": 4 + i, "fn": 6, "fp": 3, "tn": 87, "nominal": float(k)}
            for k in ("0.01", "0.02", "0.05")}}]}}  # fmt: skip
        (folder / f"uci_{i}.json").write_text(json.dumps(run))
    out = tmp_path / "shift.json"
    assert ps.main([str(folder), "--output", str(out), "--draws", "25"]) == 0
    text = out.read_text()
    data = json.loads(text)
    assert text == json.dumps(data, indent=1, sort_keys=True) + "\n"
    assert set(data["contrasts"]) == {"0.01", "0.02", "0.05"}
    assert all(block["draws"] == 25 for block in data["contrasts"].values())
    assert data["contrasts"]["0.05"]["budget"] == 0.05
    assert data["table"]["hbos"]["0.01"]["problems"] == ps.MIN_SOURCES
    with pytest.raises(SystemExit) as stop:
        ps.main([str(folder)])
    assert stop.value.code == 2


def test_f1_stays_the_harmonic_mean_when_precision_is_below_recall():
    got = ps.shifted(_cell(), 0.01)  # tpr 0.4, fpr 1/45: precision is far below recall
    assert got["precision"] < got["recall"]
    assert got["f1"] == pytest.approx(2 * got["precision"] * 0.4 / (got["precision"] + 0.4))
    assert got["f1"] > 0


def test_a_seed_without_budget_cells_does_not_hide_the_seeds_that_have_them():
    run = {
        "problem": "uci:1",
        "runs": {
            "hbos": [{"seed": 0, "rule": {"tp": 1}}, {"seed": 1, "budgets": {"0.05": _cell()}}]
        },
    }
    out = ps.summarize([run], budgets=(0.05,), prevalences=(0.1,), draws=20)
    assert out["table"]["hbos"]["0.05"]["seed_runs"] == 1


def test_a_budget_nobody_realized_does_not_stop_the_budgets_after_it():
    out = ps.summarize([_run("uci:1", _cell())], budgets=(0.01, 0.05), prevalences=(0.1,), draws=20)
    assert list(out["table"]["hbos"]) == ["0.05"]


def test_the_command_line_forwards_its_draws_to_both_analyses_and_documents_itself(
    tmp_path, monkeypatch, capsys
):
    folder = tmp_path / "runs"
    folder.mkdir()
    (folder / "uci_1.json").write_text(json.dumps(_run("uci:1", _cell())))
    spy = _Spy()
    monkeypatch.setattr(ps, "bootstrap", spy)
    assert ps.main([str(folder), "--output", str(tmp_path / "o.json"), "--draws", "25"]) == 0
    assert spy.calls and {c[3] for c in spy.calls} == {25}
    monkeypatch.setattr(ps, "DRAWS", 17)
    spy.calls.clear()
    assert ps.main([str(folder), "--output", str(tmp_path / "o.json")]) == 0
    assert {c[3] for c in spy.calls} == {17}
    with pytest.raises(SystemExit):
        ps.main(["--help"])
    assert "Fixed deployment thresholds under a change of anomaly prevalence" in " ".join(
        capsys.readouterr().out.split()
    )
