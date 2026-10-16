"""The verification figures in the manuscript match the recorded claims and the live matrix."""

import json
import re
from pathlib import Path

from tests.test_fault_matrix import FAULTS

ROOT = Path(__file__).resolve().parents[1]
PAPER = (ROOT / "paper" / "main.tex").read_text()
CLAIMS = json.loads((ROOT / "verification" / "claims.json").read_text())

WORDS = {23: "twenty-three", 14: "fourteen", 9: "nine", 3: "three"}


def _n(value):
    return f"{value:,}"


def _percent(killed, total):
    return f"{100 * killed / total:.2f}"


def test_the_fault_count_in_the_claims_is_the_live_matrix():
    assert CLAIMS["faults"] == len(FAULTS)
    assert f"{WORDS[len(FAULTS)]} deliberate" in PAPER
    assert f"All {WORDS[len(FAULTS)]} deliberate defects are caught" in PAPER


def test_fast_figures_match():
    fast = CLAIMS["fast"]
    assert f"runs {fast['tests']} tests" in PAPER
    assert f"{_n(fast['line_covered'])} of\n{_n(fast['line_coverable'])} executable lines" in PAPER
    assert f"{fast['branch_covered']} of {fast['branch_coverable']} branches" in PAPER
    assert fast["line_covered"] == fast["line_coverable"]
    assert fast["branch_covered"] == fast["branch_coverable"]
    assert f"plus {WORDS[CLAIMS['real_tests']]} that need" in PAPER


def test_verifier_figures_are_reported_apart_from_the_scientific_coverage():
    verifier = CLAIMS["verifier"]
    assert f"{verifier['line']} of {verifier['line']} lines" in PAPER
    assert f"{verifier['branch']} of {verifier['branch']} branches" in PAPER


def test_mutation_figures_match_and_add_up():
    m = CLAIMS["mutation"]
    assert m["scientific_total"] + m["other_total"] == m["total"]
    assert m["scientific_killed"] + m["other_killed"] == m["killed"]
    assert m["total"] - m["killed"] == m["survived"]
    assert f"kills {_n(m['killed'])} of {_n(m['total'])} mutants" in PAPER
    assert f"${_percent(m['killed'], m['total'])}\\%$" in PAPER
    assert f"kill {_n(m['scientific_killed'])} of {_n(m['scientific_total'])}" in PAPER
    assert f"${_percent(m['scientific_killed'], m['scientific_total'])}\\%$" in PAPER
    assert f"kills {_n(m['other_killed'])} of {_n(m['other_total'])}" in PAPER
    assert f"The {m['survived']} survivors count as failures" in PAPER


def test_the_scientific_scope_is_not_hidden_behind_the_aggregate():
    m = CLAIMS["mutation"]
    assert m["scientific_killed"] / m["scientific_total"] >= 0.95
    assert "higher than the score\nof the scientific computation alone" in PAPER


def test_no_superseded_verification_figure_is_left_in_the_paper():
    for stale in ("561 tests", "1,467", "4,487", "4,594", "107 survivors", "fourteen deliberate"):
        assert stale not in PAPER, stale
    assert not re.search(r"each one we examined leaves", PAPER)


def test_the_benchmark_comparison_does_not_misstate_adbench():
    # ADBench reports train/inference runtimes and generates local, global,
    # dependency and clustered anomalies; the paper must not deny either.
    assert "ADBench\nreports training and inference times" in PAPER
    assert "local, global,\ndependency and clustered anomalies" in PAPER
    assert "evaluate algorithms \\emph{in vacuum}" not in PAPER


def test_latency_is_described_as_the_detection_stage_only():
    assert "extraction, transformation and loading are not timed" in PAPER
    assert "not the latency of a whole ETL run" in PAPER
