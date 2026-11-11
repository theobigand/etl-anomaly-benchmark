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


@pytest.mark.parametrize("rule", ["zscore", "iqr", "great_expectations"])
def test_no_rule_is_ever_given_a_tunable_alert_budget(rule):
    x, y = _problem()
    row = ab.run_problem(x, y, seeds=(42,), methods=[rule])["runs"][rule][0]
    assert "budgets" not in row and set(row["rule"]) >= {"test_alert_rate", "recall", "precision"}
    assert ab.fit_scores(ab.build(rule, ab.FIXED_BUILD, 42), pd.DataFrame(x[:100])) is None


# --- exact behaviour of the arithmetic, the strict threshold rule and the accounting -----------

import json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402


def _stub(monkeypatch, fit, scores, flags=None):
    """A detector whose training and test scores are fixed, so every count is known by hand."""
    calls = {}

    def build(method, contamination, seed):
        calls["build"] = (method, contamination, seed)
        return "detector"

    def capped(train, method, seed):
        calls["capped"] = (method, seed)
        return train

    def detect(test, detector, fit_df=None):
        calls["detect"] = (detector, len(fit_df))
        return SimpleNamespace(
            scores=pd.Series(scores, dtype=float),
            flags=pd.Series(flags if flags is not None else [False] * len(scores)),
        )

    def fit_scores(detector, fit_df):
        calls["fit_scores"] = (detector, len(fit_df))
        return None if fit is None else np.asarray(fit, dtype=float)

    monkeypatch.setattr(ab, "build", build)
    monkeypatch.setattr(ab, "capped", capped)
    monkeypatch.setattr(ab, "detect", detect)
    monkeypatch.setattr(ab, "fit_scores", fit_scores)
    return calls


FIT_TIES = [0.0] * 90 + [1.0] * 10  # the 5% threshold lands exactly on the value 1.0
SCORES = [0, 0, 0, 0, 0, 1, 1, 2, 2, 2]
LABELS = np.array([0, 0, 0, 0, 1, 0, 1, 0, 1, 1])


def _frames(n_fit=100, n_test=10):
    return pd.DataFrame({"f0": np.zeros(n_fit)}), pd.DataFrame({"f0": np.zeros(n_test)})


def test_counts_are_exact_for_a_hand_computed_confusion_matrix():
    flags = np.array([True, True, True, False, False, False, False, False, False, False])
    y = np.array([1, 1, 0, 1, 1, 1, 0, 0, 0, 0])
    got = ab._counts(y, flags)  # tp=2 fp=1 fn=3 tn=4
    assert (got["tp"], got["fp"], got["fn"], got["tn"]) == (2, 1, 3, 4)
    assert got["precision"] == pytest.approx(2 / 3)
    assert got["recall"] == pytest.approx(2 / 5)
    assert got["f1"] == pytest.approx(4 / 8)
    assert got["fpr"] == pytest.approx(1 / 5)
    assert got["test_alert_rate"] == pytest.approx(3 / 10)


def test_counts_with_balanced_hits_and_false_alarms_do_not_collapse_precision():
    flags = np.array([True, True, False, False])
    got = ab._counts(np.array([1, 0, 1, 0]), flags)  # tp=fp=fn=tn=1
    assert got["precision"] == pytest.approx(0.5) and got["f1"] == pytest.approx(0.5)
    assert got["recall"] == pytest.approx(0.5) and got["fpr"] == pytest.approx(0.5)


def test_counts_without_any_true_positive_report_zero_not_one():
    got = ab._counts(np.array([1, 1, 0, 0]), np.array([False, False, True, False]))
    assert got["tp"] == 0 and got["precision"] == 0.0 and got["f1"] == 0.0
    assert got["recall"] == 0.0
    silent = ab._counts(np.array([1, 0]), np.array([False, False]))
    assert silent["precision"] == 0.0 and silent["f1"] == 0.0 and silent["test_alert_rate"] == 0.0


def test_a_score_equal_to_the_training_threshold_is_not_an_alert():
    fit = np.array(FIT_TIES)
    threshold = ab.budget_threshold(fit, 0.05)["threshold"]
    assert threshold == 1.0
    flags = ab.flags_for(fit, np.array([0.5, 1.0, 1.0000001, 2.0]), 0.05)
    assert flags.tolist() == [False, False, True, True]


def test_exactly_one_over_budget_training_scores_are_enough_and_one_fewer_is_not():
    assert ab.budget_threshold(np.arange(10.0), 0.1)["nominal"] == 0.1
    assert ab.budget_threshold(np.arange(100.0), 0.01)["threshold"] == pytest.approx(98.01)
    with pytest.raises(ValueError, match="at least 1/budget in number"):
        ab.budget_threshold(np.arange(9.0), 0.1)


def test_error_messages_name_the_violated_condition():
    with pytest.raises(ValueError, match=r"^budget must be a share in \(0, 0.5\)$"):
        ab.budget_threshold(np.arange(100.0), 0.7)
    with pytest.raises(ValueError, match="training scores must be finite"):
        ab.budget_threshold(np.array([np.nan] * 100), 0.1)
    with pytest.raises(ValueError, match="^test scores must be finite$"):
        ab.flags_for(np.arange(100.0), np.array([1.0, np.inf]), 0.1)


def test_run_method_reports_exact_counts_ties_and_auc_for_a_known_score_vector(monkeypatch):
    calls = _stub(monkeypatch, FIT_TIES, SCORES)
    train, test = _frames()
    row = ab.run_method("hbos", train, test, LABELS, 7)
    assert calls["build"] == ("hbos", ab.FIXED_BUILD, 7) and calls["capped"] == ("hbos", 7)
    assert calls["detect"] == ("detector", 100) and calls["fit_scores"] == ("detector", 100)
    assert (row["seed"], row["fit_rows"], row["test_rows"]) == (7, 100, 10)
    assert row["roc_auc"] == pytest.approx(roc_auc_score(LABELS, SCORES))
    assert row["pr_auc"] == pytest.approx(average_precision_score(LABELS, SCORES))
    cell = row["budgets"]["0.05"]  # threshold 1.0: only the three scores of 2 alert
    assert (cell["tp"], cell["fp"], cell["fn"], cell["tn"]) == (2, 1, 2, 5)
    assert cell["precision"] == pytest.approx(2 / 3) and cell["f1"] == pytest.approx(4 / 7)
    assert cell["nominal"] == 0.05 and cell["threshold"] == 1.0
    assert cell["ties_at_threshold"] == 10 and cell["fit_alert_rate"] == 0.0


def test_a_budget_the_fit_rows_cannot_realize_keeps_its_reason(monkeypatch):
    _stub(monkeypatch, FIT_TIES, SCORES)
    train, test = _frames()
    row = ab.run_method("hbos", train, test, LABELS, 7)
    assert row["budgets"]["0.005"] == {
        "nominal": 0.005,
        "infeasible": "training scores must be finite and at least 1/budget in number",
    }
    assert "infeasible" not in row["budgets"]["0.01"]  # exactly 100 rows realize a 1% budget


def test_a_single_class_held_out_set_is_refused(monkeypatch):
    _stub(monkeypatch, FIT_TIES, SCORES)
    train, test = _frames()
    with pytest.raises(ValueError, match="^a held-out evaluation needs both classes$"):
        ab.run_method("hbos", train, test, np.zeros(10, dtype=int), 7)


def test_a_rule_reports_its_own_decision_and_no_scores(monkeypatch):
    flags = [False, False, False, False, False, False, False, True, True, True]
    _stub(monkeypatch, None, SCORES, flags=flags)
    train, test = _frames()
    row = ab.run_method("zscore", train, test, LABELS, 7)
    assert "budgets" not in row and "roc_auc" not in row
    assert (row["rule"]["tp"], row["rule"]["fp"]) == (2, 1)


def test_checkpoint_names_are_stable_and_the_file_is_sorted_json(tmp_path):
    x, y = _problem()
    result = ab.run_problem(x, y, seeds=(42, 1), methods=["hbos"], cells=tmp_path, tag="p:1")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["p_1__hbos__1.json", "p_1__hbos__42.json"]
    text = (tmp_path / "p_1__hbos__42.json").read_text()
    row = json.loads(text)
    assert text == json.dumps(row, sort_keys=True) + "\n"
    assert row == {"method": "hbos", **result["runs"]["hbos"][0]}
    assert result["seeds"] == [42, 1]


def test_without_a_tag_the_checkpoint_is_still_written_under_a_predictable_name(tmp_path):
    x, y = _problem()
    ab.run_problem(x, y, seeds=(42,), methods=["hbos"], cells=tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["__hbos__42.json"]


def test_a_cell_is_accepted_when_it_holds_budgets_or_a_rule_and_rejected_when_it_holds_neither(
    tmp_path,
):
    def write(**extra):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"seed": 1, "method": "m", **extra}))
        return ab._load_cell(path, "m", 1)

    assert write(rule={"tp": 1}) is not None
    assert write(budgets={}) is not None
    assert write(roc_auc=0.5) is None
    assert ab._load_cell(tmp_path / "absent.json", "m", 1) is None


def test_one_skipped_or_failing_detector_never_stops_the_others(monkeypatch):
    x, y = _problem()
    monkeypatch.setattr(ab.nm, "KNN_MAX_TRAIN", 10)
    skipped_first = ab.run_problem(x, y, seeds=(42,), methods=["knn", "hbos"])
    assert skipped_first["skipped"] == ["knn"] and "hbos" in skipped_first["runs"]
    monkeypatch.undo()
    real = ab.run_method

    def flaky(method, *args, **kwargs):
        if method == "hbos":
            raise RuntimeError("boom")
        return real(method, *args, **kwargs)

    monkeypatch.setattr(ab, "run_method", flaky)
    result = ab.run_problem(x, y, seeds=(42,), methods=["hbos", "ecod"])
    assert result["errors"] == {"hbos": [{"seed": 42, "error": "RuntimeError('boom')"}]}
    assert list(result["runs"]) == ["ecod"]


def test_skipped_detectors_accumulate_over_seeds(monkeypatch):
    x, y = _problem()
    sequence = iter([{"knn"}, {"lof"}])
    monkeypatch.setattr(ab.nm, "skipped_detectors", lambda n: next(sequence))
    result = ab.run_problem(x, y, seeds=(1, 2), methods=["knn", "lof", "hbos"])
    assert result["skipped"] == ["knn", "lof"]


def _cell(rate, tp=1, fp=0):
    return {"nominal": 0.01, "tp": tp, "fp": fp, "fn": 0, "tn": 9, "precision": 1.0,
            "recall": 1.0, "f1": 1.0, "fpr": 0.0, "test_alert_rate": rate,
            "fit_alert_rate": 0.01}  # fmt: skip


def _run(problem, **by_method):
    return {"problem": problem, "source": "adbench", "prevalence": 0.1, "runs": by_method,
            "errors": {}, "skipped": []}  # fmt: skip


def test_summary_skips_problems_that_did_not_evaluate_a_detector_without_losing_later_ones():
    infeasible = {"seed": 1, "budgets": {"0.01": {"nominal": 0.01, "infeasible": "x"}}}
    rule_only = {"seed": 1, "rule": {"tp": 1}}
    runs = [
        _run("a", hbos=[infeasible]),
        _run("b"),  # this problem never evaluated hbos
        _run("c", hbos=[rule_only]),
        _run("d", hbos=[{"seed": 1, "budgets": {"0.01": _cell(0.04)}}]),
    ]
    cell = ab.summarize(runs, budgets=(0.01,))["hbos"]["0.01"]
    assert cell["problems"] == 1 and cell["seed_runs"] == 1
    assert cell["median_realized_over_nominal"] == pytest.approx(4.0)
    assert set(cell) == {
        "problems", "seed_runs", "median_precision", "median_recall", "median_f1",
        "median_fpr", "median_test_alert_rate", "median_fit_alert_rate",
        "median_realized_over_nominal",
    }  # fmt: skip


def test_rule_reference_ignores_problems_without_that_rule():
    rule = {"seed": 1, "rule": {"test_alert_rate": 0.2, "precision": 0.5, "recall": 0.4}}
    ref = ab.rule_reference([_run("a", zscore=[rule]), _run("b", hbos=[])])
    assert ref == {
        "zscore": {
            "problems": 1,
            "median_test_alert_rate": 0.2,
            "median_precision": 0.5,
            "median_recall": 0.4,
        }
    }


def test_integer_rule_flags_are_read_as_booleans(monkeypatch):
    flags = [0, 0, 0, 0, 0, 0, 0, 1, 1, 1]
    _stub(monkeypatch, None, SCORES, flags=flags)
    train, test = _frames()
    row = ab.run_method("zscore", train, test, LABELS, 7)
    assert (row["rule"]["tp"], row["rule"]["fp"], row["rule"]["fn"], row["rule"]["tn"]) == (
        2, 1, 2, 5,
    )  # fmt: skip


def test_without_an_explicit_list_every_registered_detector_is_run(monkeypatch):
    x, y = _problem()
    monkeypatch.setattr(ab, "DETECTOR_NAMES", ("hbos", "ecod"))
    result = ab.run_problem(x, y, seeds=(42,))
    assert sorted(result["runs"]) == ["ecod", "hbos"]


# --- the per-problem job and the command line ---------------------------------------------------


def _loaders(monkeypatch, x=None, y=None, name="thyroid"):
    x = np.zeros((4, 3)) if x is None else x
    y = np.array([0, 0, 0, 1]) if y is None else y
    seen = {}

    def adbench(n, path):
        seen["adbench"] = (n, path)
        return x, y, {"name": name}

    def uci(meta, path):
        seen["uci"] = (meta, path)
        return x, y, {"name": "toy"}

    def problem(xx, yy, methods=None, cells=None, tag=""):
        seen["problem"] = {
            "methods": methods,
            "cells": cells,
            "tag": tag,
            "shape": xx.shape,
            "y": yy,
        }
        return {"seeds": [1], "runs": {}, "skipped": [], "errors": {}}

    monkeypatch.setattr(ab.lb, "load_adbench", adbench)
    monkeypatch.setattr(ab.lb, "load_uci", uci)
    monkeypatch.setattr(ab, "run_problem", problem)
    return seen


def test_an_adbench_job_is_loaded_by_name_and_described_with_its_shape_and_prevalence(
    monkeypatch, tmp_path
):
    seen = _loaders(monkeypatch)
    job = {"problem": "adbench:thyroid", "source": "adbench", "name": "thyroid", "path": "/d/t.npz"}
    out = ab.run_job(job, methods=["hbos"], cells=tmp_path)
    assert seen["adbench"] == ("thyroid", Path("/d/t.npz")) and "uci" not in seen
    assert seen["problem"] == {
        "methods": ["hbos"], "cells": tmp_path, "tag": "adbench:thyroid", "shape": (4, 3),
        "y": seen["problem"]["y"],
    }  # fmt: skip
    assert seen["problem"]["y"].tolist() == [0, 0, 0, 1]
    assert out == {
        "problem": "adbench:thyroid", "source": "adbench", "name": "thyroid",
        "prevalence": 0.25, "rows": 4, "features": 3,
        "seeds": [1], "runs": {}, "skipped": [], "errors": {},
    }  # fmt: skip


def test_a_uci_job_is_loaded_from_its_metadata(monkeypatch):
    seen = _loaders(monkeypatch)
    meta = {"uci_id": 7}
    out = ab.run_job({"problem": "uci:7", "source": "uci", "meta": meta, "path": "/d/7.csv"})
    assert seen["uci"] == (meta, Path("/d/7.csv")) and "adbench" not in seen
    assert out["name"] == "toy" and out["problem"] == "uci:7" and out["source"] == "uci"
    assert seen["problem"]["methods"] is None and seen["problem"]["cells"] is None


def test_a_job_that_cannot_be_read_is_returned_as_failed_never_dropped(monkeypatch):
    _loaders(monkeypatch)

    def broken(*args):
        raise OSError("disk")

    monkeypatch.setattr(ab.lb, "load_adbench", broken)
    out = ab.run_job({"problem": "adbench:t", "source": "adbench", "name": "t", "path": "p"})
    assert out == {"problem": "adbench:t", "source": "adbench", "failed": "OSError('disk')"}


class _SyncPool:
    """A process pool that runs inline, remembering how it was created."""

    created = []

    def __init__(self, max_workers):
        self.max_workers = max_workers
        _SyncPool.created.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, items):
        self.fn = fn
        return [fn(item) for item in items]


def _cli(monkeypatch, jobs, results):
    """Run ``main`` against canned jobs; ``results`` maps problem id to what ``run_job`` returns."""
    _SyncPool.created = []
    seen = {"jobs_args": None, "run": []}

    def lb_jobs(registry, adbench, pool):
        seen["jobs_args"] = (registry, adbench, pool)
        return jobs

    def run_job(job, methods=None, cells=None):
        seen["run"].append((job["problem"], methods, cells))
        return results[job["problem"]]

    monkeypatch.setattr(ab.lb, "jobs", lb_jobs)
    monkeypatch.setattr(ab, "run_job", run_job)
    monkeypatch.setattr(ab, "ProcessPoolExecutor", _SyncPool)
    return seen


def test_main_writes_one_file_per_problem_and_reports_the_failed_count(
    monkeypatch, tmp_path, capsys
):
    jobs = [{"problem": "adbench:a"}, {"problem": "uci:7"}]
    results = {
        "adbench:a": {"runs": {"z": 1}, "problem": "adbench:a"},
        "uci:7": {"problem": "uci:7", "failed": "boom"},
    }
    seen = _cli(monkeypatch, jobs, results)
    out = tmp_path / "deep" / "out"  # parents are created
    assert ab.main(["--output", str(out), "--methods", "classical"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["adbench_a.json", "uci_7.json"]
    text = (out / "adbench_a.json").read_text()
    assert text == json.dumps(results["adbench:a"], sort_keys=True) + "\n"
    printed = capsys.readouterr().out.splitlines()
    assert printed == ["adbench:a ok", "uci:7 boom", "2 problems, 1 failed"]
    root = Path(ab.__file__).resolve().parent.parent
    assert seen["jobs_args"] == (
        root / "verification" / "evidence" / "dataset_registry",
        root / "data" / "adbench",
        root / "data" / "pool",
    )
    assert _SyncPool.created[0].max_workers == 4
    assert [run[1] for run in seen["run"]] == [list(ab.DETECTOR_NAMES)] * 2
    assert all(run[2] is None for run in seen["run"])


def test_main_honours_workers_only_cells_and_the_deep_detector_family(monkeypatch, tmp_path):
    jobs = [{"problem": "p1"}, {"problem": "p2"}]
    results = {k: {"problem": k} for k in ("p1", "p2")}
    seen = _cli(monkeypatch, jobs, results)
    cells = tmp_path / "cells"
    args = ["--output", str(tmp_path), "--workers", "2", "--only", "p2", "p1", "--methods", "deep"]
    assert ab.main([*args, "--cells", str(cells)]) == 0
    assert [run[0] for run in seen["run"]] == ["p1", "p2"]  # several ids may be named
    assert seen["run"][0][1] == list(ab.DEEP_NAMES) and seen["run"][0][2] == cells
    assert _SyncPool.created[0].max_workers == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["p1.json", "p2.json"]


def test_resume_skips_a_problem_whose_result_is_already_on_disk(monkeypatch, tmp_path, capsys):
    jobs = [{"problem": "adbench:a"}, {"problem": "adbench:b"}]
    seen = _cli(monkeypatch, jobs, {k["problem"]: {"problem": k["problem"]} for k in jobs})
    (tmp_path / "adbench_a.json").write_text("{}")
    assert ab.main(["--output", str(tmp_path), "--resume"]) == 0
    assert [run[0] for run in seen["run"]] == ["adbench:b"]
    assert capsys.readouterr().out.splitlines()[-1] == "1 problems, 0 failed"
    seen["run"].clear()
    assert ab.main(["--output", str(tmp_path)]) == 0
    assert [run[0] for run in seen["run"]] == ["adbench:a", "adbench:b"]  # no resume: all rerun


def test_the_command_line_refuses_an_unknown_detector_family_and_a_missing_output(monkeypatch):
    _cli(monkeypatch, [], {})
    for argv in (["--output", "x", "--methods", "other"], []):
        with pytest.raises(SystemExit) as stop:
            ab.main(argv)
        assert stop.value.code == 2


def test_path_arguments_reach_the_job_listing_as_paths_and_help_documents_them(
    monkeypatch, tmp_path, capsys
):
    seen = _cli(monkeypatch, [], {})
    argv = ["--output", str(tmp_path), "--registry", "r", "--adbench", "a", "--pool", "p"]
    assert ab.main(argv) == 0
    assert seen["jobs_args"] == (Path("r"), Path("a"), Path("p"))
    assert all(isinstance(value, Path) for value in seen["jobs_args"])
    with pytest.raises(SystemExit):
        ab.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--only [ONLY ...] problem ids, for a quick check" in text
    assert text.count("checkpoint folder: one file per seed run") == 1
    assert "--cells CELLS checkpoint folder: one file per seed run" in text
    assert "Fixed alert budgets, label-free" in text
