"""Chronological summary: paired differences per table, chronological minus random."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrono_injected_summary as cis  # noqa: E402


def _run(ident, fpr_c, fpr_r, rec_c, rec_r):
    def arm(fpr, rec):
        return {"fpr": {"knn": fpr}, "recall": {"knn": {"a": rec, "b": rec}}}

    return {"id": ident, "arms": {"chronological": arm(fpr_c, rec_c), "random": arm(fpr_r, rec_r)}}


def test_differences_are_chronological_minus_random_per_table():
    runs = {"t1": _run("uci:1", 0.2, 0.1, 0.5, 0.6), "t2": _run("uci:2", 0.1, 0.1, 0.4, 0.4)}
    out = cis.paired(runs)["knn"]
    assert list(out["fpr"]) == pytest.approx([0.1, 0.0])
    assert list(out["recall"]) == pytest.approx([-0.1, 0.0])


def test_summary_counts_tables_with_higher_false_positive_rate():
    runs = {f"t{i}": _run(f"uci:{i}", 0.3, 0.1, 0.5, 0.5) for i in range(4)}
    rows = {m: v for m, v in cis.paired(runs).items()}
    assert int((rows["knn"]["fpr"] > 0).sum()) == 4
    assert cis.interval(rows["knn"]["fpr"])[0] == pytest.approx(0.2)
