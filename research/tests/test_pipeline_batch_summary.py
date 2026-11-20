"""Pilot summary: recall by detector and mechanism, and the four preregistered checks."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_batch as pb  # noqa: E402
import pipeline_batch_summary as ps  # noqa: E402


def _arm(rule, learned, stat=0.5):
    """An arm where each detector has one recall per mechanism (same at the three severities)."""
    detectors = ["constraint_rules", "distribution_distance", "isolation_forest", "random"]
    results = {}
    for d in detectors:
        results[d] = {}
        for m in pb.MECHANISMS:
            r = {
                "constraint_rules": rule,
                "isolation_forest": learned,
                "distribution_distance": stat,
            }.get(d, 0.05)
            r = r(m) if callable(r) else r
            results[d][m] = {lv: {"recall": r, "false_alert_rate": 0.05} for lv in ("0", "1", "2")}
    return {"detectors": detectors, "results": results}


def _source(i, rule, learned, dirty_drop=0.1):
    clean = _arm(rule, learned)
    dirty = _arm(lambda m: rule(m) - dirty_drop if callable(rule) else rule - dirty_drop, learned)
    return {"id": f"uci:{i}", "arms": {"clean_reference": clean, "contaminated_reference": dirty}}


def test_hypotheses_are_read_from_the_sources_and_few_sources_are_descriptive_only():
    rule = lambda m: 0.95 if m in ps.CLEAR else 0.1  # noqa: E731
    sources = [_source(i, rule, 0.6) for i in range(3)]
    s = ps.summarise(sources)
    assert s["descriptive_only"] is True and len(s["sources"]) == 3
    assert all(v == 1.0 for v in s["B1_share_of_sources_recall_ge_0.9"].values())
    b2 = s["B2_rules_vs_best_learned"]["silent_corruption"]
    assert b2["median_gap"] == pytest.approx(0.5) and b2["share_ge_0.2"] == 1.0
    assert s["B3_best_family_by_mechanism"]["partial_load"] == "rules"
    assert s["B3_best_family_by_mechanism"]["silent_corruption"] == "learned"
    assert s["B3_holds"] is True
    assert s["B4_mean_recall_change_contaminated_minus_clean"]["learned"] == pytest.approx(0.0)
    assert s["B4_mean_recall_change_contaminated_minus_clean"]["rules"] < 0
    assert s["median_recall_at_budget"]["random"]["partial_load"]["high"] == pytest.approx(0.05)


def test_one_family_best_everywhere_fails_b3():
    sources = [_source(i, 0.9, 0.2) for i in range(2)]
    assert ps.summarise(sources)["B3_holds"] is False


def test_the_report_names_every_detector_and_marks_the_pilot_descriptive(tmp_path):
    sources = [_source(i, 0.9, 0.2) for i in range(2)]
    text = ps.render(ps.summarise(sources))
    assert "Descriptive only" in text and "constraint_rules" in text and "B4" in text
    assert text.count("| random |") == 1
