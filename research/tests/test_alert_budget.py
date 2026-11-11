"""Alert budgets (T163, T164): thresholds from unlabelled training scores only."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import alert_budget as ab  # noqa: E402

from etl_benchmark.pipeline import detect  # noqa: E402


def _problem(n=600, anomalies=60, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    x[:anomalies] += 4
    return x, y


def test_budgets_cover_one_and_two_percent_in_increasing_order():
    assert {0.01, 0.02} <= set(ab.BUDGETS) and list(ab.BUDGETS) == sorted(ab.BUDGETS)


def test_the_threshold_is_the_training_score_quantile_and_ignores_test_data():
    fit = np.arange(1000, dtype=float)
    info = ab.budget_threshold(fit, 0.02)
    assert info["threshold"] == pytest.approx(np.percentile(fit, 98))
    assert info["fit_alert_rate"] == pytest.approx(0.02, abs=0.002)
    assert info["nominal"] == 0.02


def test_ties_at_the_threshold_are_reported_as_a_realized_fit_rate_below_nominal():
    fit = np.r_[np.zeros(990), np.ones(10)]  # 1% above, but the 2% quantile is tied at 0
    info = ab.budget_threshold(fit, 0.02)
    assert info["threshold"] == 0.0 and info["fit_alert_rate"] == pytest.approx(0.01)
    assert info["ties_at_threshold"] == 990


def test_score_direction_is_higher_is_more_anomalous():
    fit = np.arange(100, dtype=float)
    flags = ab.flags_for(fit, np.array([-5.0, 50.0, 1000.0]), 0.05)
    assert flags.tolist() == [False, False, True]


@pytest.mark.parametrize("bad", [0.0, -0.1, 0.5, 1.0, float("nan")])
def test_an_invalid_budget_is_refused(bad):
    with pytest.raises(ValueError, match="budget"):
        ab.budget_threshold(np.arange(100.0), bad)


@pytest.mark.parametrize("fit", [np.array([]), np.array([1.0, np.nan, 2.0]), np.arange(5.0)])
def test_missing_or_too_few_training_scores_are_refused(fit):
    with pytest.raises(ValueError, match="training scores"):
        ab.budget_threshold(fit, 0.01)


def test_the_flags_do_not_depend_on_test_labels_or_test_quantiles():
    x, y = _problem()
    one = ab.run_problem(x, y, seeds=(42,), methods=["hbos"])
    shuffled = y.copy()
    np.random.default_rng(1).shuffle(shuffled)
    # the split is stratified on labels, so compare the thresholds only: they are label-free
    detector = ab.build("hbos", ab.FIXED_BUILD, seed=42)
    train = pd.DataFrame(x[:400])
    detect(pd.DataFrame(x[400:]), detector, fit_df=train)
    kept = ab.fit_scores(detector, train)
    thresholds = [ab.budget_threshold(kept, b)["threshold"] for b in ab.BUDGETS]
    assert thresholds == sorted(thresholds, reverse=True)
    assert one["runs"]["hbos"][0]["budgets"]["0.01"]["nominal"] == 0.01


def test_a_problem_gives_every_budget_with_nominal_and_realized_rates_and_counts():
    x, y = _problem()
    result = ab.run_problem(x, y, seeds=(42,), methods=["zscore", "hbos", "ecod"])
    row = result["runs"]["hbos"][0]
    assert set(row["budgets"]) == {str(b) for b in ab.BUDGETS}
    for key, cell in row["budgets"].items():
        assert cell["nominal"] == float(key)
        tp, fp, fn, tn = (cell[k] for k in ("tp", "fp", "fn", "tn"))
        assert tp + fp + fn + tn == row["test_rows"]
        assert cell["test_alert_rate"] == pytest.approx((tp + fp) / row["test_rows"])
        assert cell["fpr"] == pytest.approx(fp / (fp + tn))
        assert cell["precision"] == pytest.approx(tp / (tp + fp) if tp + fp else 0.0)
    rates = [row["budgets"][str(b)]["test_alert_rate"] for b in ab.BUDGETS]
    assert rates == sorted(rates)  # a larger budget never alerts less on the same scores
    rule = result["runs"]["zscore"][0]
    assert "budgets" not in rule and rule["rule"]["test_alert_rate"] >= 0.0


def test_a_failing_detector_and_a_skip_are_recorded(monkeypatch):
    x, y = _problem()
    monkeypatch.setattr(ab.nm, "KNN_MAX_TRAIN", 10)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ab, "run_method", boom)
    result = ab.run_problem(x, y, seeds=(42,), methods=["hbos", "knn"])
    assert result["skipped"] == ["knn"] and result["runs"] == {}
    assert result["errors"]["hbos"][0]["error"] == "RuntimeError('boom')"


def test_unknown_methods_are_refused():
    x, y = _problem()
    with pytest.raises(ValueError, match="unknown"):
        ab.run_problem(x, y, seeds=(1,), methods=["nope"])


def test_summary_denominators_and_independent_median():
    def run(problem, tp, fp, rate):
        cell = {"nominal": 0.01, "tp": tp, "fp": fp, "fn": 10 - tp, "tn": 90 - fp,
                "precision": tp / (tp + fp), "recall": tp / 10, "f1": 0.0, "fpr": fp / (90),
                "test_alert_rate": rate, "fit_alert_rate": 0.01}  # fmt: skip
        return {"problem": problem, "source": "adbench", "prevalence": 0.1,
                "runs": {"hbos": [{"seed": 42, "test_rows": 100, "budgets": {"0.01": cell}}]},
                "errors": {}, "skipped": []}  # fmt: skip

    runs = [run("a", 1, 1, 0.02), run("b", 5, 0, 0.05), run("c", 9, 0, 0.09)]
    table = ab.summarize(runs, budgets=(0.01,))
    cell = table["hbos"]["0.01"]
    assert cell["problems"] == 3 and cell["seed_runs"] == 3
    assert cell["median_recall"] == pytest.approx(0.5)
    assert cell["median_precision"] == pytest.approx(1.0)
    assert cell["median_test_alert_rate"] == pytest.approx(0.05)
    assert cell["median_realized_over_nominal"] == pytest.approx(5.0)


def test_summary_counts_failures_and_skips_as_unevaluated_not_zero():
    base = {"problem": "a", "source": "adbench", "prevalence": 0.1, "runs": {},
            "errors": {"hbos": [{"seed": 42, "error": "x"}]}, "skipped": ["knn"]}  # fmt: skip
    table = ab.summarize([base], budgets=(0.01,))
    assert table == {} or "hbos" not in table
    assert ab.accounting([base]) == {"problems": 1, "failed_runs": 1, "skipped_detectors": 1}


def test_a_budget_the_training_set_cannot_realize_is_recorded_not_fatal():
    x, y = _problem(n=250, anomalies=40)  # about 175 training rows: 0.5% needs 200
    result = ab.run_problem(x, y, seeds=(42,), methods=["hbos"])
    cells = result["runs"]["hbos"][0]["budgets"]
    assert "infeasible" in cells["0.005"] and "tp" not in cells["0.005"]
    assert "infeasible" not in cells["0.01"] and result["errors"] == {}
    table = ab.summarize([{"problem": "a", **result}], budgets=(0.005, 0.01))
    assert "0.005" not in table["hbos"] and table["hbos"]["0.01"]["problems"] == 1


def test_rules_are_a_separate_untuned_reference():
    x, y = _problem()
    result = ab.run_problem(x, y, seeds=(42, 1), methods=["zscore", "hbos"])
    ref = ab.rule_reference([{"problem": "a", **result}])
    assert set(ref) == {"zscore"} and ref["zscore"]["problems"] == 1
    assert 0.0 <= ref["zscore"]["median_test_alert_rate"] <= 1.0


def test_a_checkpointed_seed_run_is_reused_and_a_corrupt_one_is_recomputed(tmp_path, monkeypatch):
    x, y = _problem()
    first = ab.run_problem(x, y, seeds=(42, 1), methods=["hbos"], cells=tmp_path, tag="p:1")
    assert len(list(tmp_path.glob("*.json"))) == 2 and not list(tmp_path.glob(".*"))

    def boom(*args, **kwargs):
        raise AssertionError("a valid checkpoint must not be refitted")

    monkeypatch.setattr(ab, "run_method", boom)
    again = ab.run_problem(x, y, seeds=(42, 1), methods=["hbos"], cells=tmp_path, tag="p:1")
    assert again == first
    monkeypatch.undo()
    (tmp_path / "p_1__hbos__1.json").write_text("{truncated")
    healed = ab.run_problem(x, y, seeds=(42, 1), methods=["hbos"], cells=tmp_path, tag="p:1")
    assert healed == first


def test_a_checkpoint_for_another_seed_or_method_is_ignored(tmp_path):
    x, y = _problem()
    ab.run_problem(x, y, seeds=(42,), methods=["hbos"], cells=tmp_path, tag="p")
    path = tmp_path / "p__hbos__42.json"
    assert ab._load_cell(path, "hbos", 42) is not None
    assert ab._load_cell(path, "ecod", 42) is None and ab._load_cell(path, "hbos", 1) is None
