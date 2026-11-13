"""Strict comparisons, exact outputs and LaTeX rows of the pool extension hypotheses."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from test_pool_extension_summary import _row, _run

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_extension_summary as ps  # noqa: E402


def _result(chrono, strat):
    return {
        "chronological": {f"m{i}": {"pr_auc": c} for i, c in enumerate(chrono)},
        "stratified": {f"m{i}": {"pr_auc": s} for i, s in enumerate(strat)},
    }


def test_p5_counts_only_strictly_lower_pairs_adds_them_across_datasets_and_reports_each():
    tie = _result([0.5, 0.5], [0.5, 0.5])
    assert ps.chronology({"t": tie})["lower"] == 0
    data = {"a": _result([0.1, 0.1, 0.9], [0.5] * 3), "b": _result([0.1, 0.9, 0.9], [0.5] * 3)}
    out = ps.chronology(data)
    assert out == {
        "supported": False,
        "lower": 3,
        "pairs": 6,
        "by_dataset": {"a": {"lower": 2, "detectors": 3}, "b": {"lower": 1, "detectors": 3}},
    }
    two_thirds = ps.chronology({"a": _result([0.1, 0.1, 0.9], [0.5] * 3)})
    assert two_thirds["supported"] is True
    four = ps.chronology({"a": _result([0.1, 0.1, 0.9, 0.9], [0.5] * 4)})
    assert four["supported"] is False and four["pairs"] == 4


def _record(method, share, rows=60_000, status="OK", ident="d"):
    return {
        "id": ident, "method": method, "status": status,
        "rows_after_transform": rows, "detect_stage_share": share,
    }  # fmt: skip


def test_p4_boundaries_are_strict_and_a_missing_group_is_not_a_number():
    at_limit = [_record("isolation_forest", 0.5, rows=50_000), _record("zscore", 0.02, rows=50_000)]
    out = ps.pipeline(at_limit)
    assert out["supported"] is False and out["datasets_above"] == 0
    assert ps.pipeline(at_limit, large=49_999)["datasets_above"] == 1
    assert ps.pipeline(at_limit, large=49_999)["supported"] is True
    flat = [_record("isolation_forest", 0.30), _record("zscore", 0.02)]
    assert ps.pipeline(flat)["supported"] is False
    tied = [_record("isolation_forest", 0.5), _record("zscore", 0.10)]
    assert ps.pipeline(tied)["supported"] is False
    only_zscore = ps.pipeline([_record("zscore", 0.02)])
    assert (
        only_zscore["median_detect_share"]["isolation_forest"]
        != only_zscore["median_detect_share"]["isolation_forest"]
    )
    assert only_zscore["median_detect_share"]["zscore"] == 0.02
    good = ps.pipeline([_record("isolation_forest", 0.5), _record("zscore", 0.02, ident="e")])
    assert good["median_detect_share"] == {"zscore": 0.02, "isolation_forest": 0.5}
    assert good["datasets_above"] == 2 and good["failed"] == []


def _write_severity(folder, low, high, names):
    payloads = {
        severity: {
            "data": [[v] for v in values],
            "index": names,
            "columns": ["multivariate_outlier"],
        }
        for severity, values in (("0.5", low), ("4.0", high))
    }
    (folder / "a.json").write_text(json.dumps({"recall_by_severity": payloads}))


def test_p3_ignores_the_two_non_learned_rows_and_needs_strictly_more_recall_at_four(tmp_path):
    names = ["isolation_forest", "drift", "transform_dedup"]
    _write_severity(tmp_path, [0.2, 0.9, 0.9], [0.5, 0.1, 0.1], names)
    out = ps.severity(tmp_path)
    assert out["supported"] is True and out["detectors"] == 1 and out["higher_at_4"] == 1
    assert set(out) == {"supported", "detectors", "higher_at_4", "median_multivariate_recall"}
    _write_severity(tmp_path, [0.5, 0.0], [0.5, 0.0], ["isolation_forest", "drift"])
    assert ps.severity(tmp_path)["supported"] is False
    _write_severity(tmp_path, [0.9], [0.1], ["transform_dedup"])
    assert ps.severity(tmp_path)["supported"] is False


def test_p1_needs_a_strictly_lower_f1_and_names_its_fields():
    runs = [
        _run("p", {f"m{i}": [_row(1, 0.4, 0.4 if i < 12 else 0.3)] for i in range(13)}),
    ]
    out = ps.fixed_threshold(runs)
    assert set(out) == {"supported", "lower_at_fixed", "detectors", "by_detector"}
    assert out["lower_at_fixed"] == 1 and out["supported"] is False and out["detectors"] == 13
    twelve = [_run("p", {f"m{i}": [_row(1, 0.4, 0.3)] for i in range(12)})]
    assert ps.fixed_threshold(twelve)["supported"] is True


@pytest.mark.parametrize(
    ("rho", "expected"), [(0.9899999999, True), (0.98999999, False), (0.99, True)]
)
def test_p2_rounds_the_rank_correlation_to_nine_places_and_accepts_equality(
    monkeypatch, rho, expected
):
    runs = [
        _run(
            "p",
            {
                "a": [_row(1, 0.2, 0.1, pr=0.2, curve=0.2)],
                "b": [_row(1, 0.3, 0.1, pr=0.3, curve=0.3)],
            },
        ),
        _run(
            "q",
            {
                "a": [_row(1, 0.2, 0.1, pr=0.25, curve=0.25)],
                "b": [_row(1, 0.3, 0.1, pr=0.35, curve=0.35)],
            },
        ),
    ]
    monkeypatch.setattr(ps, "spearmanr", lambda a, b: SimpleNamespace(statistic=rho))
    out = ps.curve_ranking(runs)
    assert out["supported"] is expected and out["spearman"] == rho
    assert set(out["median_ap"]) == {"a", "b"}


def test_a_failed_file_does_not_stop_the_files_after_it_and_merged_fields_accumulate(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"problem": "x", "failed": "boom"}))
    base = _run("p", {"zscore": [_row(1, 0.2, 0.1)]}) | {"errors": {"lof": ["e"]}, "skipped": ["b"]}
    (tmp_path / "b.json").write_text(json.dumps(base))
    more = _run("p", {"vae": [_row(1, 0.3, 0.2)]}) | {
        "errors": {"knn": ["f"]},
        "skipped": ["a", "b"],
    }
    (tmp_path / "c.json").write_text(json.dumps(more))
    [merged] = ps.load_runs(tmp_path)
    assert merged["problem"] == "p"
    assert set(merged["runs"]) == {"zscore", "vae"}
    assert merged["errors"] == {"lof": ["e"], "knn": ["f"]}
    assert merged["skipped"] == ["a", "b"]


def test_the_contamination_sweep_skips_runs_without_the_forest():
    runs = [_run("p", {"zscore": [_row(1, 0.2, 0.1)]})]
    out = ps.contamination_sweep(runs)
    assert list(out) == list(ps.GRID)
    assert all(pd.isna(v["precision"]) for v in out.values())


def test_latex_rows_are_exact_and_the_rule_after_the_pca_and_expectations_rows_only():
    table = {
        "by_detector": {
            m: {
                "f1": {"prevalence": 0.1, "fixed": 0.2},
                "flagged_pct": {"prevalence": 1.0, "fixed": 2.0},
            }
            for m in ("zscore", "great_expectations", "pca")
        }
    }
    names = {"zscore": "Z", "great_expectations": "GE", "pca": "PCA"}
    rows = ps.fixed_rows(table, names).split("\n")
    assert rows == [
        f"{'Z':<18} & 0.100 & 0.200 & 1.0 & 2.0 \\\\",
        f"{'GE':<18} & 0.100 & 0.200 & 1.0 & 2.0 \\\\",
        r"\midrule",
        f"{'PCA':<18} & 0.100 & 0.200 & 1.0 & 2.0 \\\\",
        r"\midrule",
    ]
    median = {
        "a": {"0.5": 0.1, "1.0": 0.2, "2.0": 0.3, "4.0": 0.4},
        "b": {s: 0.5 for s in ("0.5", "1.0", "2.0", "4.0")},
    }
    assert ps.severity_rows(median, {"a": "A", "b": "B"}).split("\n") == [
        f"{'A':<18} & 0.10 & 0.20 & 0.30 & 0.40 \\\\",
        f"{'B':<18} & 0.50 & 0.50 & 0.50 & 0.50 \\\\",
    ]
    cell = {"precision": 0.125, "recall": 0.018, "f1": 0.032, "flagged_pct": 1.089}
    assert ps.sweep_rows({"0.01": cell, "0.05": cell}).split("\n") == [
        "0.010 & 0.125 & 0.018 & 0.032 & 1.1 \\\\",
        "0.050 & 0.125 & 0.018 & 0.032 & 1.1 \\\\",
    ]


def test_chronological_rows_shorten_the_exclusion_reason_and_count_lower_pairs():
    assert ps._short("12 anomalies in the test partition (at least 20)") == "12 test anomalies"
    results = {
        "kept": {
            **_result([0.1, 0.9], [0.5, 0.5]),
            "partitions": {
                "train": {"prevalence": 0.05},
                "test": {"positives": 40, "prevalence": 0.1},
            },
        },
        "out": {"excluded": "12 anomalies in the test partition (at least 20)"},
    }
    rows = ps.chrono_rows(results, {"kept": "Kept", "out": "Out"}).split("\n")
    assert rows == [
        "Kept & 40 & 5.0 & 10.0 & 1 of 2 \\\\",
        "Out & \\multicolumn{4}{l}{excluded: 12 test anomalies} \\\\",
    ]


def test_the_default_large_limit_is_fifty_thousand_rows_exclusive():
    above = [_record("isolation_forest", 0.5, rows=50_001), _record("zscore", 0.02, rows=50_001)]
    assert ps.pipeline(above)["datasets_above"] == 1
    assert ps.pipeline(above)["supported"] is True
    at = [_record("isolation_forest", 0.5, rows=50_000), _record("zscore", 0.02, rows=50_000)]
    assert ps.pipeline(at)["datasets_above"] == 0


def test_an_excluded_dataset_listed_first_does_not_hide_the_ones_after_it():
    results = {
        "skipped": {"excluded": "12 anomalies in the test partition (at least 20)"},
        "kept": {
            **_result([0.1, 0.9], [0.5, 0.5]),
            "partitions": {
                "train": {"prevalence": 0.05},
                "test": {"positives": 40, "prevalence": 0.1},
            },
        },
    }
    assert ps.chronology(results)["pairs"] == 2 and ps.chronology(results)["lower"] == 1
    rows = ps.chrono_rows(results, {"skipped": "S", "kept": "K"}).split("\n")
    assert rows[0].startswith("S & ") and rows[1] == "K & 40 & 5.0 & 10.0 & 1 of 2 \\\\"


def test_a_merged_problem_holds_exactly_the_fields_of_its_runs(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(_run("p", {"zscore": [_row(1, 0.2, 0.1)]})))
    [merged] = ps.load_runs(tmp_path)
    assert set(merged) == {"problem", "runs", "errors", "skipped"}
    assert merged["errors"] == {} and merged["skipped"] == []
