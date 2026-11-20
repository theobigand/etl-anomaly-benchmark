"""Summary of the naturally labelled chronological study: lift, group units, hypotheses."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natural_temporal_summary as ns  # noqa: E402

METHODS = ["zscore", "iqr", "isolation_forest", "lof", "knn", "autoencoder", "vae"]


def _policy(f1, share):
    return {"f1": f1, "share_error": share, "flagged_share": 0.1, "precision": 0.5, "recall": 0.5, "fpr": 0.1}


def _record(name, group, chrono_bias, rng, test_prevalence=0.2):
    base = {m: rng.uniform(0.2, 0.8) for m in METHODS}
    return {
        "id": name,
        "group": group,
        "partitions": {
            "train": {"rows": 700, "positives": 70, "prevalence": 0.1},
            "validation": {"rows": 150, "positives": 15, "prevalence": 0.1},
            "test": {"rows": 150, "positives": 30, "prevalence": test_prevalence},
        },
        "chronological": {
            m: {
                "pr_auc": v + chrono_bias,
                "policies": {"P0": _policy(0.3, 0.9), "P1": _policy(0.3, 0.6), "P2": _policy(0.4, 0.3)},
            }
            for m, v in base.items()
        },
        "stratified": {m: {"pr_auc": v, "pr_auc_matched": v + chrono_bias / 2} for m, v in base.items()},
    }


def test_lift_removes_the_prevalence_baseline_of_each_arm():
    rng = np.random.default_rng(0)
    record = _record("s", "g", -0.1, rng, test_prevalence=0.2)
    out = ns.lifts(record)["zscore"]
    chrono, strat = record["chronological"]["zscore"]["pr_auc"], record["stratified"]["zscore"]["pr_auc"]
    assert out["chronological_lift"] == pytest.approx((chrono - 0.2) / 0.8)
    assert out["stratified_lift"] == pytest.approx((strat - 0.115) / 0.885)  # 115 of 1000 rows

def test_detectors_belong_to_one_of_three_families():
    assert [ns.family(m) for m in ("iqr", "lof", "vae")] == ["rule", "classical", "neural"]


def test_units_are_source_groups_and_a_consistent_loss_is_found():
    rng = np.random.default_rng(1)
    groups = ["a", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    evaluated = [_record(f"s{i}", g, -0.15, rng) for i, g in enumerate(groups)]
    summary = ns.summarise(evaluated, [], draws=200)
    assert summary["independent_sources"] == 11 and summary["series"]["evaluated"] == 12
    n1 = summary["N1"]
    assert n1["chronological_lower_share"] == 1.0 and n1["supported_by_share"] is True
    assert len(n1["detectors_with_interval_below_zero"]) == len(METHODS)
    assert summary["N2"]["median_spearman"] > 0.99 and summary["N2"]["supported"] is True
    assert summary["N4"]["friedman"]["units"] == 11
    assert {tuple(sorted((r["a"], r["b"]))) for r in summary["N4"]["families"]} == {
        ("classical", "neural"), ("classical", "rule"), ("neural", "rule")
    }


def test_no_loss_is_not_reported_as_one():
    rng = np.random.default_rng(2)
    evaluated = [_record(f"s{i}", f"g{i}", 0.05, rng) for i in range(10)]
    n1 = ns.summarise(evaluated, [], draws=200)["N1"]
    assert n1["chronological_lower_share"] == 0.0 and n1["supported_by_share"] is False


def test_excluded_series_are_listed_with_their_reason_and_never_evaluated(tmp_path):
    rng = np.random.default_rng(3)
    (tmp_path / "a.json").write_text(json.dumps(_record("a", "g", 0.0, rng)))
    (tmp_path / "b.json").write_text(json.dumps({"id": "b", "group": "h", "excluded": "0 anomalies"}))
    evaluated, excluded = ns.load(tmp_path)
    assert [r["id"] for r in evaluated] == ["a"] and [r["id"] for r in excluded] == ["b"]
    summary = ns.summarise(evaluated * 1 + [_record("c", "i", 0.0, rng)] * 9, excluded, draws=100)
    assert summary["excluded"] == [{"id": "b", "group": "h", "reason": "0 anomalies"}]
    assert "0 anomalies" in ns.render(summary)
