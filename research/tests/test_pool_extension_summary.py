"""Hypotheses P1 to P6 of the pool extension, on small hand-made run files."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_extension_summary as ps  # noqa: E402


def _metrics(f1, flagged=5.0, pr=0.5):
    return {"precision": f1, "recall": f1, "f1": f1, "flagged_pct": flagged, "pr_auc": pr}


def _row(seed, prevalence_f1, fixed_f1, pr=0.5, curve=None, sweep=None):
    row = {
        "seed": seed,
        "metrics": _metrics(prevalence_f1, pr=pr),
        "fixed": _metrics(fixed_f1, pr=pr),
        "fit_s": 1.0,
        "predict_s": 0.5,
        "score_s": 0.5,
    }
    if curve is not None:
        row["curve"] = {"average_precision": curve}
    if sweep is not None:
        row["sweep"] = {c: _metrics(f1) for c, f1 in sweep.items()}
    return row


def _run(problem, methods):
    return {"problem": problem, "runs": methods, "errors": {}, "skipped": []}


def test_the_classical_and_the_neural_files_of_a_problem_are_merged(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "p.json").write_text(json.dumps(_run("p", {"zscore": [_row(1, 0.2, 0.1)]})))
    run = _run("p", {"vae": [_row(1, 0.3, 0.2)]}) | {"skipped": ["lof"]}
    (b / "p.json").write_text(json.dumps(run))
    (b / "q.json").write_text(json.dumps({"problem": "q", "failed": "boom"}))
    merged = ps.load_runs(a, b)
    assert len(merged) == 1 and set(merged[0]["runs"]) == {"zscore", "vae"}
    assert merged[0]["skipped"] == ["lof"]


def test_p1_counts_the_detectors_whose_median_f1_is_lower_at_the_fixed_threshold():
    names = [f"m{i}" for i in range(17)]
    runs = [
        _run("p1", {m: [_row(1, 0.4, 0.1 if i < 12 else 0.5)] for i, m in enumerate(names)}),
        _run("p2", {m: [_row(1, 0.4, 0.1 if i < 12 else 0.5)] for i, m in enumerate(names)}),
    ]
    out = ps.fixed_threshold(runs)
    assert out["supported"] and out["lower_at_fixed"] == 12 and out["detectors"] == 17
    runs[0]["runs"]["m11"][0]["fixed"]["f1"] = 0.9
    runs[1]["runs"]["m11"][0]["fixed"]["f1"] = 0.9
    assert not ps.fixed_threshold(runs)["supported"]


def test_p2_compares_the_curve_ranking_with_the_published_one():
    runs = [
        _run(
            "p",
            {
                "a": [_row(42, 0.1, 0.1, pr=0.9, curve=0.9)],
                "b": [_row(42, 0.1, 0.1, pr=0.2, curve=0.2)],
            },
        ),
        _run(
            "q",
            {
                "a": [_row(42, 0.1, 0.1, pr=0.8, curve=0.8)],
                "b": [_row(42, 0.1, 0.1, pr=0.3, curve=0.3)],
            },
        ),
    ]
    out = ps.curve_ranking(runs)
    assert out["supported"] and out["spearman"] == pytest.approx(1.0)
    assert out["median_ap"]["a"] == pytest.approx(0.85)


def test_the_contamination_sweep_takes_the_median_over_problems():
    sweep = {c: 0.1 * (i + 1) for i, c in enumerate(ps.GRID)}
    runs = [
        _run("p", {"isolation_forest": [_row(42, 0.1, 0.1, sweep=sweep)]}),
        _run("q", {"isolation_forest": [_row(42, 0.1, 0.1, sweep={c: 0.5 for c in ps.GRID})]}),
    ]
    out = ps.contamination_sweep(runs)
    assert set(out) == set(ps.GRID) and out["0.001"]["f1"] == pytest.approx(0.3)
    assert out["0.2"]["f1"] == pytest.approx(0.5)


def test_the_timing_is_the_median_of_fit_predict_and_score():
    runs = [_run("p", {"zscore": [_row(1, 0, 0)]}), _run("q", {"zscore": [_row(1, 0, 0)]})]
    assert ps.timings(runs)["zscore"] == {"median_s": 2.0, "max_s": 2.0}


def _severity_file(folder, name, low, high, methods=("isolation_forest", "drift")):
    def frame(value):
        return {
            "index": list(methods),
            "columns": ["univariate_outlier", "multivariate_outlier", "temporal_drift"],
            "data": [[0.1, value, 0.1] for _ in methods],
        }

    payload = {"recall_by_severity": {"0.5": frame(low), "4.0": frame(high)}}
    (folder / f"{name}.json").write_text(json.dumps(payload))


def test_p3_needs_every_learned_detector_to_gain_recall_with_severity(tmp_path):
    _severity_file(tmp_path, "t1", 0.1, 0.8)
    _severity_file(tmp_path, "t2", 0.2, 0.9)
    assert ps.severity(tmp_path)["supported"]
    _severity_file(tmp_path, "t3", 0.9, 0.1)
    _severity_file(tmp_path, "t4", 0.9, 0.1)
    out = ps.severity(tmp_path)
    assert not out["supported"] and out["higher_at_4"] == 0


def test_p4_compares_the_detection_share_of_two_detectors_on_large_datasets():
    def record(method, share, rows=60_000, status="OK"):
        return {
            "id": "d",
            "method": method,
            "status": status,
            "rows_after_transform": rows,
            "detect_stage_share": share,
        }

    good = [record("isolation_forest", 0.5), record("zscore", 0.02), record("zscore", 0.9, rows=10)]
    out = ps.pipeline(good)
    assert out["supported"] and out["datasets_above"] == 1
    bad = [
        record("isolation_forest", 0.1),
        record("zscore", 0.02),
        record("zscore", 0, status="FAIL"),
    ]
    out = ps.pipeline(bad)
    assert not out["supported"] and out["failed"] == ["d"]
    assert not ps.pipeline([record("zscore", 0.01)])["supported"]


def test_p5_needs_two_thirds_of_the_pairs_lower_and_lists_the_excluded_datasets():
    def result(chrono, strat):
        return {
            "chronological": {f"m{i}": {"pr_auc": c} for i, c in enumerate(chrono)},
            "stratified": {f"m{i}": {"pr_auc": s} for i, s in enumerate(strat)},
        }

    data = {"a": result([0.1, 0.1, 0.9], [0.5, 0.5, 0.5]), "b": {"excluded": "too few"}}
    out = ps.chronology(data)
    assert out["supported"] and out["lower"] == 2 and out["pairs"] == 3
    assert out["by_dataset"]["b"] == {"excluded": "too few"}
    assert not ps.chronology({"a": result([0.9, 0.9, 0.1], [0.5, 0.5, 0.5])})["supported"]
    assert not ps.chronology({"b": {"excluded": "x"}})["supported"]


def test_p6_is_the_status_of_the_file_check():
    report = {"summary": {"datasets": 2, "counts": {"ok": 2}, "all_ok": True}}
    assert ps.contract(report)["supported"]
    report["summary"]["all_ok"] = False
    assert not ps.contract(report)["supported"]


def test_the_latex_rows_of_the_pool_tables_carry_the_computed_numbers():
    table = {
        "by_detector": {
            "zscore": {
                "f1": {"prevalence": 0.164, "fixed": 0.164},
                "flagged_pct": {"prevalence": 11.4, "fixed": 11.4},
            },
            "pca": {
                "f1": {"prevalence": 0.169, "fixed": 0.068},
                "flagged_pct": {"prevalence": 11.4, "fixed": 2.4},
            },
        }
    }
    rows = ps.fixed_rows(table, {"zscore": "Z-score", "pca": "PCA"})
    assert "Z-score" in rows and "0.164 & 0.164 & 11.4 & 11.4" in rows
    assert "0.169 & 0.068 & 11.4 & 2.4" in rows and rows.count("midrule") == 1
    grid = {"0.01": {"precision": 0.125, "recall": 0.018, "f1": 0.032, "flagged_pct": 1.089}}
    assert ps.sweep_rows(grid) == "0.010 & 0.125 & 0.018 & 0.032 & 1.1 \\\\"
    results = {
        "a": {
            "partitions": {
                "test": {"positives": 52, "prevalence": 0.0012},
                "train": {"prevalence": 0.0018},
            },
            "chronological": {"m": {"pr_auc": 0.1}},
            "stratified": {"m": {"pr_auc": 0.3}},
        },
        "b": {"excluded": "0 anomalies"},
    }
    out = ps.chrono_rows(results, {"a": "Alpha", "b": "Beta"})
    assert "Alpha & 52 & 0.2 & 0.1 & 1 of 1" in out and "excluded: 0 anomalies" in out
