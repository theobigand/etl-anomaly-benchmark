import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fault_protocols as fp  # noqa: E402


def table(n=50):
    return pd.DataFrame(
        {"id": range(n), "amount": np.arange(n, dtype=float) + 10, "k": [i % 5 for i in range(n)]}
    )


def test_row_duplicates_are_appended_copies_with_truth_on_the_copies_only():
    df = table()
    out, truth = fp.inject_duplicates(df, k=4, seed=1)
    assert len(out) == len(df) + 4 and list(truth) == list(range(50, 54))
    pd.testing.assert_frame_equal(out.iloc[:50].reset_index(drop=True), df)  # originals untouched
    assert (
        out.iloc[truth]
        .reset_index(drop=True)
        .equals(df.loc[out.iloc[truth]["id"]].reset_index(drop=True))
    )
    again, truth2 = fp.inject_duplicates(df, k=4, seed=1)
    pd.testing.assert_frame_equal(out, again)
    assert list(truth) == list(truth2)
    assert not out.equals(fp.inject_duplicates(df, k=4, seed=2)[0])


def test_amount_outliers_change_only_the_chosen_cells_by_the_stated_severity():
    df = table()
    out, truth = fp.inject_scale(df, "amount", k=5, factor=10.0, seed=3)
    changed = np.flatnonzero((out["amount"] != df["amount"]).to_numpy())
    assert sorted(truth) == list(changed) and len(truth) == 5
    assert np.allclose(out.loc[truth, "amount"], df.loc[truth, "amount"] * 10)
    assert out.drop(columns="amount").equals(df.drop(columns="amount"))
    with pytest.raises(fp.ProtocolError, match="precondition"):
        fp.inject_scale(df, "amount", k=999, factor=2.0, seed=0)
    with pytest.raises(fp.ProtocolError, match="precondition"):
        fp.inject_scale(df.assign(amount="x"), "amount", k=1, factor=2.0, seed=0)


def test_a_level_shift_touches_one_series_in_one_window_and_keeps_time_order():
    idx = pd.date_range("2024-01-01", periods=100, freq="h")
    wide = pd.DataFrame({"a": np.arange(100.0), "b": np.arange(100.0) * 2}, index=idx)
    out, truth = fp.inject_level_shift(wide, "a", start=40, length=10, delta=5.0)
    assert truth == [("a", 40, 50)]
    assert np.allclose(out["a"].iloc[40:50], wide["a"].iloc[40:50] + 5)
    assert out["a"].iloc[:40].equals(wide["a"].iloc[:40]) and out["a"].iloc[50:].equals(
        wide["a"].iloc[50:]
    )
    assert out["b"].equals(wide["b"]) and out.index.equals(wide.index)
    with pytest.raises(fp.ProtocolError, match="precondition"):
        fp.inject_level_shift(wide, "a", start=95, length=10, delta=1.0)


def test_sequence_faults_stay_inside_their_sequence_and_report_positions():
    seqs = {"s1": list("ABCDEFGH"), "s2": list("ABCDEFGH")}
    out, truth = fp.swap_adjacent(seqs, "s1", position=2)
    assert out["s1"] == list("ABDCEFGH") and out["s2"] == seqs["s2"] and truth == [("s1", 2)]
    out, truth = fp.drop_event(seqs, "s2", position=0)
    assert out["s2"] == list("BCDEFGH") and truth == [("s2", 0)] and len(out["s1"]) == 8
    assert seqs["s1"] == list("ABCDEFGH")  # the input is not modified
    with pytest.raises(fp.ProtocolError, match="precondition"):
        fp.swap_adjacent(seqs, "s1", position=7)


def test_broken_references_exclude_natural_orphans_and_never_point_at_an_existing_parent():
    parent = {1, 2, 3, 4}
    child = pd.DataFrame({"id": range(10), "fk": [1, 2, 3, 4, 1, 2, 99, 98, None, 3]})
    out, truth, baseline = fp.break_foreign_key(child, "fk", parent, k=3, seed=0)
    assert baseline == [6, 7]  # natural orphans are reported and never labelled
    assert not set(truth) & set(baseline) and len(truth) == 3
    assert all(out.loc[i, "fk"] not in parent for i in truth)
    untouched = out.drop(index=truth)
    assert untouched.equals(child.drop(index=truth))
    assert out["fk"].isna().sum() == 1  # missing keys are not turned into faults
    with pytest.raises(fp.ProtocolError, match="precondition"):
        fp.break_foreign_key(child, "fk", parent, k=50, seed=0)


def test_nested_corruption_changes_exactly_the_named_path_of_the_chosen_records():
    records = [{"a": {"b": [1, 2], "c": "x"}, "d": i} for i in range(6)]
    snapshot = copy.deepcopy(records)
    out, truth = fp.corrupt_path(records, "a.b", mode="remove", k=2, seed=5)
    assert records == snapshot and len(truth) == 2
    for i, rec in enumerate(out):
        if (i, "a.b") in truth:
            assert "b" not in rec["a"] and rec["a"]["c"] == "x" and rec["d"] == i
        else:
            assert rec == snapshot[i]
    out, truth = fp.corrupt_path(records, "a.c", mode="type", k=1, seed=5)
    ((i, _),) = truth
    assert out[i]["a"]["c"] != "x" and not isinstance(out[i]["a"]["c"], str)
    with pytest.raises(fp.ProtocolError, match="precondition"):
        fp.corrupt_path(records, "a.zzz", mode="remove", k=1, seed=0)


def test_matching_uses_the_detection_unit_of_the_protocol():
    assert fp.match_exact([1, 2, 3], [2, 3, 4]) == {"tp": 2, "fp": 1, "fn": 1}
    truth = [("a", 40, 50)]
    assert (
        fp.match_windows([("a", 45, 60)], truth)["tp"] == 1
    )  # overlap of 5 is half of the shorter 10
    assert fp.match_windows([("a", 49, 60)], truth)["tp"] == 0
    assert fp.match_windows([("b", 40, 50)], truth) == {"tp": 0, "fp": 1, "fn": 1}


def test_hash_partitions_are_deterministic_disjoint_and_faults_stay_in_their_partition():
    keys = [f"k{i}" for i in range(1000)]
    split = fp.hash_partition(keys, (0.7, 0.15, 0.15))
    assert split == fp.hash_partition(keys, (0.7, 0.15, 0.15))
    parts = [set(v) for v in split.values()]
    assert not (parts[0] & parts[1] or parts[0] & parts[2] or parts[1] & parts[2])
    assert sum(len(p) for p in parts) == 1000 and 600 < len(parts[0]) < 800
    allowed = split["test"]
    chosen = fp.choose_within(sorted(allowed), k=5, seed=1)
    assert set(chosen) <= set(allowed) and len(chosen) == 5
    with pytest.raises(fp.ProtocolError, match="precondition"):
        fp.choose_within(["a"], k=2, seed=0)


def test_conformance_checks_report_true_for_every_invariant_on_small_inputs():
    n = 400
    data = {
        "authorships": pd.DataFrame({"author_id": [f"a{i % 40}" for i in range(n)]}),
        "authors": pd.DataFrame({"author_id": [f"a{i}" for i in range(40)]}),
        "votes": pd.DataFrame({"post_id": [str(i % 60) for i in range(n)]}),
        "posts": pd.DataFrame({"post_id": [str(i) for i in range(50)]}),
        "events": [{"patient": {"sex": "1"}, "id": str(i)} for i in range(n)],
        "ledger": pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=n), "amount": np.arange(n) + 1.0}
        ),
        "sequence": [f"E{i % 7}" for i in range(n)],
        "series": pd.DataFrame(
            {"s1": np.arange(n, dtype=float), "s2": np.arange(n, dtype=float)},
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
        ),
    }
    report = fp.conformance(data, seed=7)
    assert set(report) == {"P-REL", "P-NEST", "P-TAB", "P-SEQ", "P-TS"}
    for protocol, checks in report.items():
        assert checks and all(v is True for v in checks.values() if isinstance(v, bool)), protocol
    assert report["P-REL"]["baseline_orphans_reported_not_labelled"] is True
    assert report["P-REL"]["baseline_orphan_count"] > 0


def test_award_references_of_contracts_report_their_natural_orphans_as_a_baseline():
    n = 300
    awards = pd.DataFrame({"award_id": [str(i) for i in range(n)]})
    contracts = pd.DataFrame(
        {"award_id": [str(i % n) for i in range(n)] + ["missing-1", "missing-2"]}
    )
    data = {
        "authorships": pd.DataFrame({"author_id": [f"a{i % 40}" for i in range(n)]}),
        "authors": pd.DataFrame({"author_id": [f"a{i}" for i in range(40)]}),
        "votes": pd.DataFrame({"post_id": [str(i % 60) for i in range(n)]}),
        "posts": pd.DataFrame({"post_id": [str(i) for i in range(50)]}),
        "events": [{"patient": {"sex": "1"}, "id": str(i)} for i in range(n)],
        "ledger": pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=n), "amount": np.arange(n) + 1.0}
        ),
        "sequence": [f"E{i % 7}" for i in range(n)],
        "series": pd.DataFrame(
            {"s1": np.arange(n, dtype=float), "s2": np.arange(n, dtype=float)},
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
        ),
        "contracts": contracts,
        "awards": awards,
    }
    checks = fp.conformance(data, seed=3)["P-REL"]
    assert checks["ocds_baseline_orphans"] == 2
    assert checks["ocds_baseline_not_labelled"] is True
    assert checks["ocds_unaffected_rows_unchanged"] is True
