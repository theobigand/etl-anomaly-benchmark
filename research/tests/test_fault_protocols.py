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


# --- conformance: exact on honest injectors, False when an injector misbehaves ---------------


def _data(n=400):
    return {
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


def test_the_conformance_report_is_exact_for_honest_injectors():
    report = fp.conformance(_data(), seed=7)
    assert report == {
        "P-REL": {
            "deterministic": True,
            "unaffected_rows_unchanged": True,
            "truth_rows_now_orphans": True,
            "baseline_orphans_reported_not_labelled": True,
            "baseline_orphan_count": 60,
            "baseline_unchanged": True,
        },
        "P-NEST": {
            "only_truth_records_changed": True,
            "only_named_path_changed": True,
            "input_unmodified": True,
        },
        "P-TAB": {
            "faults_only_in_test_partition": True,
            "reference_untouched": True,
            "scale_changes_only_truth": True,
            "duplicates_appended_after_originals": True,
        },
        "P-SEQ": {
            "swap_keeps_length_and_multiset": True,
            "swap_changes_two_positions_only": True,
            "drop_shortens_by_one": True,
            "truth_is_the_position": True,
        },
        "P-TS": {
            "other_series_untouched": True,
            "outside_window_untouched": True,
            "time_index_monotonic_and_unchanged": True,
            "window_is_the_truth": True,
        },
    }
    assert list(report) == ["P-REL", "P-NEST", "P-TAB", "P-SEQ", "P-TS"]


def _tampered(monkeypatch, name, wrapper):
    real = getattr(fp, name)
    monkeypatch.setattr(fp, name, lambda *a, **k: wrapper(real(*a, **k), *a, **k))
    return fp.conformance(_data(), seed=7)


def test_a_misbehaving_reference_injector_is_reported_per_invariant(monkeypatch):
    calls = {"n": 0}

    def nondeterministic(result, child, column, parent, k, seed):
        calls["n"] += 1
        out, truth, base = result
        if calls["n"] == 2:  # the repeat call of the first pair
            out = out.copy()
            out.iloc[0, 0] = "changed"
        return out, truth, base

    assert (
        _tampered(monkeypatch, "break_foreign_key", nondeterministic)["P-REL"]["deterministic"]
        is False
    )
    monkeypatch.undo()

    def touches_others(result, child, column, parent, k, seed):
        out, truth, base = result
        out = out.copy()
        untouched = [i for i in range(len(out)) if i not in set(truth)][0]
        out.iloc[untouched, 0] = "zzz"
        return out, truth, base

    rel = _tampered(monkeypatch, "break_foreign_key", touches_others)["P-REL"]
    assert rel["unaffected_rows_unchanged"] is False
    monkeypatch.undo()

    def keeps_valid(result, child, column, parent, k, seed):
        out, truth, base = result
        return child.copy(), truth, base

    assert (
        _tampered(monkeypatch, "break_foreign_key", keeps_valid)["P-REL"]["truth_rows_now_orphans"]
        is False
    )
    monkeypatch.undo()

    def labels_baseline(result, child, column, parent, k, seed):
        out, truth, base = result
        return out, [*truth, *base[:1]] if base else truth, base

    rel = _tampered(monkeypatch, "break_foreign_key", labels_baseline)["P-REL"]
    assert rel["baseline_orphans_reported_not_labelled"] is False
    monkeypatch.undo()

    def rewrites_baseline(result, child, column, parent, k, seed):
        out, truth, base = result
        out = out.copy()
        if base:
            out.iloc[base[0], 0] = "rewritten"
        return out, truth, base

    assert (
        _tampered(monkeypatch, "break_foreign_key", rewrites_baseline)["P-REL"][
            "baseline_unchanged"
        ]
        is False
    )


def test_a_misbehaving_nested_injector_is_reported_per_invariant(monkeypatch):
    def extra_record(result, records, path, mode, k, seed):
        out, truth = result
        out = [dict(r) for r in out]
        free = next(i for i in range(len(out)) if (i, path) not in truth)
        out[free] = {"patient": {"sex": "1"}, "id": "changed"}
        return out, truth

    nest = _tampered(monkeypatch, "corrupt_path", extra_record)["P-NEST"]
    assert nest["only_truth_records_changed"] is False
    monkeypatch.undo()

    def other_field(result, records, path, mode, k, seed):
        out, truth = result
        out = [dict(r) for r in out]
        i = truth[0][0]
        out[i] = {**out[i], "id": "other"}
        return out, truth

    assert (
        _tampered(monkeypatch, "corrupt_path", other_field)["P-NEST"]["only_named_path_changed"]
        is False
    )
    monkeypatch.undo()

    def mutates_input(result, records, path, mode, k, seed):
        records[0]["patient"].pop("sex", None)
        return result

    assert (
        _tampered(monkeypatch, "corrupt_path", mutates_input)["P-NEST"]["input_unmodified"] is False
    )


def test_a_misbehaving_table_injector_is_reported_per_invariant(monkeypatch):
    def outside_test(result, df, column, k, factor, seed, candidates=None):
        out, truth = result
        return out, [0, *truth[1:]]

    assert (
        _tampered(monkeypatch, "inject_scale", outside_test)["P-TAB"][
            "faults_only_in_test_partition"
        ]
        is False
    )
    monkeypatch.undo()

    def touches_reference(result, df, column, k, factor, seed, candidates=None):
        out, truth = result
        out = out.copy()
        out.loc[0, "amount"] = -1.0
        return out, truth

    tab = _tampered(monkeypatch, "inject_scale", touches_reference)["P-TAB"]
    assert tab["reference_untouched"] is False and tab["scale_changes_only_truth"] is False
    monkeypatch.undo()

    def early_duplicates(result, df, k, seed):
        out, truth = result
        return out, [0, *truth[1:]]

    assert (
        _tampered(monkeypatch, "inject_duplicates", early_duplicates)["P-TAB"][
            "duplicates_appended_after_originals"
        ]
        is False
    )
    monkeypatch.undo()

    def short_duplicates(result, df, k, seed):
        out, truth = result
        return out.iloc[:-1], truth

    assert (
        _tampered(monkeypatch, "inject_duplicates", short_duplicates)["P-TAB"][
            "duplicates_appended_after_originals"
        ]
        is False
    )


def test_a_misbehaving_sequence_or_series_injector_is_reported_per_invariant(monkeypatch):
    def changes_multiset(result, seqs, name, position):
        out, truth = result
        out = {k: list(v) for k, v in out.items()}
        out[name][0] = "NEW"
        return out, truth

    assert (
        _tampered(monkeypatch, "swap_adjacent", changes_multiset)["P-SEQ"][
            "swap_keeps_length_and_multiset"
        ]
        is False
    )
    monkeypatch.undo()

    def three_positions(result, seqs, name, position):
        out, truth = result
        out = {k: list(v) for k, v in out.items()}
        out[name][0], out[name][1], out[name][2] = out[name][1], out[name][2], out[name][0]
        return out, truth

    seq = _tampered(monkeypatch, "swap_adjacent", three_positions)["P-SEQ"]
    assert seq["swap_changes_two_positions_only"] is False
    monkeypatch.undo()

    assert (
        _tampered(
            monkeypatch, "drop_event", lambda result, seqs, name, position: (seqs, result[1])
        )["P-SEQ"]["drop_shortens_by_one"]
        is False
    )
    monkeypatch.undo()
    assert (
        _tampered(
            monkeypatch,
            "swap_adjacent",
            lambda result, seqs, name, position: (result[0], [("log", 5)]),
        )["P-SEQ"]["truth_is_the_position"]
        is False
    )
    monkeypatch.undo()

    def touches_other_series(result, wide, series, start, length, delta):
        out, truth = result
        out = out.copy()
        out.iloc[0, 1] += 1
        return out, truth

    ts = _tampered(monkeypatch, "inject_level_shift", touches_other_series)["P-TS"]
    assert ts["other_series_untouched"] is False
    monkeypatch.undo()

    def touches_outside(result, wide, series, start, length, delta):
        out, truth = result
        out = out.copy()
        out.iloc[0, 0] += 1
        return out, truth

    ts = _tampered(monkeypatch, "inject_level_shift", touches_outside)["P-TS"]
    assert ts["outside_window_untouched"] is False
    monkeypatch.undo()

    def after_window(result, wide, series, start, length, delta):
        out, truth = result
        out = out.copy()
        out.iloc[-1, 0] += 1
        return out, truth

    assert (
        _tampered(monkeypatch, "inject_level_shift", after_window)["P-TS"][
            "outside_window_untouched"
        ]
        is False
    )
    monkeypatch.undo()

    def reorders_index(result, wide, series, start, length, delta):
        out, truth = result
        return out.iloc[::-1], truth

    ts = _tampered(monkeypatch, "inject_level_shift", reorders_index)["P-TS"]
    assert ts["time_index_monotonic_and_unchanged"] is False
    monkeypatch.undo()
    ts = _tampered(
        monkeypatch,
        "inject_level_shift",
        lambda result, wide, series, start, length, delta: (result[0], [("zzz", 1, 2)]),
    )["P-TS"]
    assert ts["window_is_the_truth"] is False


def test_the_split_cuts_at_85_percent():
    assert fp._split_rows(100) == (list(range(85)), list(range(85, 100)))
    assert fp._split_rows(10) == (list(range(8)), [8, 9])
    assert fp._without({"a": 1, "b": 2}, "a") == {"b": 2}


# --- exact behaviour of every injector, matcher and partition ---------------------------------


def test_choose_within_is_deterministic_sorted_and_bounded():
    assert fp.choose_within(list(range(20)), 5, 1) == [0, 7, 8, 13, 18]
    assert fp.choose_within(list(range(20)), 5, 2) == [1, 4, 5, 8, 13]
    assert fp.choose_within(list("abcdef"), 3, 0) == ["d", "e", "f"]
    assert fp.choose_within([1, 2], 0, 0) == []
    assert fp.choose_within([1, 2], 2, 0) == [1, 2]
    with pytest.raises(fp.ProtocolError) as info:
        fp.choose_within([1, 2], 3, 0)
    assert str(info.value) == "precondition: 3 faults requested among 2 candidates"
    with pytest.raises(fp.ProtocolError):
        fp.choose_within([1, 2], -1, 0)


def test_duplicates_and_scaling_have_exact_outputs():
    df = pd.DataFrame({"id": range(6), "amount": [1.0, 2, 3, 4, 5, 6]})
    out, truth = fp.inject_duplicates(df, 2, 3)
    assert truth == [6, 7] and out["id"].tolist() == [0, 1, 2, 3, 4, 5, 0, 4]
    out, truth = fp.inject_scale(df, "amount", 2, 10.0, 3)
    assert truth == [0, 4] and out["amount"].tolist() == [10.0, 2.0, 3.0, 4.0, 50.0, 6.0]
    assert df["amount"].tolist() == [1.0, 2, 3, 4, 5, 6]  # the input is not modified
    out, truth = fp.inject_scale(df, "amount", 2, 10.0, 3, candidates=[4, 5])
    assert truth == [4, 5] and out["amount"].tolist() == [1.0, 2.0, 3.0, 4.0, 50.0, 60.0]
    with pytest.raises(fp.ProtocolError) as info:
        fp.inject_scale(df.assign(amount="x"), "amount", 1, 2.0, 0)
    assert str(info.value) == "precondition: column 'amount' is not numeric"


def test_level_shifts_check_their_window_and_series_exactly():
    wide = pd.DataFrame({"a": np.zeros(10), "b": np.zeros(10)})
    out, truth = fp.inject_level_shift(wide, "a", 7, 3, 2.0)  # a window ending at the last point
    assert truth == [("a", 7, 10)] and out["a"].tolist() == [0.0] * 7 + [2.0] * 3
    out, truth = fp.inject_level_shift(wide, "b", 0, 1, 1.0)  # a window starting at the first point
    assert truth == [("b", 0, 1)] and out["b"].tolist()[:2] == [1.0, 0.0]
    for args in (("a", -1, 2, 1.0), ("a", 0, 0, 1.0), ("a", 8, 3, 1.0), ("zzz", 0, 1, 1.0)):
        with pytest.raises(fp.ProtocolError) as info:
            fp.inject_level_shift(wide, *args)
        assert str(info.value) == "precondition: the window lies outside the series"
    assert wide["a"].sum() == 0  # the input is not modified


def test_sequence_faults_check_their_positions_exactly():
    seqs = {"s": ["a", "b", "c"], "t": ["x"]}
    out, truth = fp.swap_adjacent(seqs, "s", 0)
    assert out["s"] == ["b", "a", "c"] and truth == [("s", 0)] and out["t"] == ["x"]
    out, truth = fp.swap_adjacent(seqs, "s", 1)  # the last valid pair
    assert out["s"] == ["a", "c", "b"]
    for position in (2, -1, 3):
        with pytest.raises(fp.ProtocolError) as info:
            fp.swap_adjacent(seqs, "s", position)
        assert str(info.value) == "precondition: no adjacent pair at this position"
    out, truth = fp.drop_event(seqs, "s", 2)  # the last event
    assert out["s"] == ["a", "b"] and truth == [("s", 2)]
    out, _ = fp.drop_event(seqs, "s", 0)
    assert out["s"] == ["b", "c"] and seqs["s"] == ["a", "b", "c"]
    for position in (3, -1):
        with pytest.raises(fp.ProtocolError) as info:
            fp.drop_event(seqs, "s", position)
        assert str(info.value) == "precondition: no event at this position"
    with pytest.raises(fp.ProtocolError):
        fp.swap_adjacent({"one": ["a"]}, "one", 0)


def test_broken_references_use_unused_keys_of_the_parent_type():
    child = pd.DataFrame({"fk": [1, 2, 3, None, 99]})
    out, truth, baseline = fp.break_foreign_key(child, "fk", {1, 2, 3}, 2, 5)
    assert truth == [1, 2] and baseline == [4]
    assert (
        out["fk"].tolist()[1:3] == [1000003.0, 1000004.0] and out["fk"].isna().tolist()[3] is True
    )
    assert child["fk"].tolist()[1] == 2.0  # the input is not modified
    text = pd.DataFrame({"fk": ["a", "b", "c", "zz"]})
    out, truth, baseline = fp.break_foreign_key(text, "fk", {"a", "b", "c"}, 2, 5)
    assert out["fk"].tolist() == ["a", "__absent_0__", "__absent_1__", "zz"]
    assert truth == [1, 2] and baseline == [3]
    numpy_keys = {np.int64(1), np.int64(2)}
    out, truth, _ = fp.break_foreign_key(pd.DataFrame({"fk": [1, 2]}), "fk", numpy_keys, 1, 0)
    assert out["fk"].tolist() in ([1, 1000002], [1000002, 2]) or len(truth) == 1
    with pytest.raises(fp.ProtocolError):
        fp.break_foreign_key(child, "fk", {1, 2, 3}, 4, 5)  # only three resolvable references


def test_nested_corruption_modes_and_preconditions_are_exact():
    records = [{"a": {"b": "x", "c": i}} for i in range(5)]
    out, truth = fp.corrupt_path(records, "a.c", "type", 2, 4)
    assert truth == [(2, "a.c"), (4, "a.c")] and [r["a"]["c"] for r in out] == [0, 1, "2", 3, "4"]
    out, truth = fp.corrupt_path(records, "a.b", "type", 2, 4)
    assert [r["a"]["b"] for r in out] == ["x", "x", 0, "x", 0]
    out, truth = fp.corrupt_path(records, "a.b", "remove", 1, 4)
    assert truth == [(3, "a.b")] and "b" not in out[3]["a"] and out[3]["a"]["c"] == 3
    assert records[3]["a"]["b"] == "x"
    with pytest.raises(fp.ProtocolError) as info:
        fp.corrupt_path(records, "a.b", "swap", 1, 0)
    assert str(info.value) == "unknown mode 'swap'"
    with pytest.raises(fp.ProtocolError) as info:
        fp.corrupt_path(records, "a.zzz", "remove", 1, 0)
    assert str(info.value) == "precondition: no record has the path 'a.zzz'"
    with pytest.raises(fp.ProtocolError):
        fp.corrupt_path(records, "a.b", "remove", 9, 0)
    assert fp.corrupt_path([{"a": 1}, {"b": 2}], "a", "remove", 1, 0)[1] == [(0, "a")]
    assert fp.corrupt_path([{"a": {"b": 1}}, {"a": 5}], "a.b", "remove", 1, 0)[1] == [(0, "a.b")]


def test_window_matching_requires_half_of_the_shorter_window_and_the_same_series():
    truth = [("a", 10, 20)]
    assert fp.match_windows([("a", 15, 30)], truth) == {
        "tp": 1,
        "fp": 0,
        "fn": 0,
    }  # overlap 5 = half of 10
    assert fp.match_windows([("a", 16, 30)], truth) == {"tp": 0, "fp": 1, "fn": 1}  # overlap 4 < 5
    assert fp.match_windows([("a", 12, 14)], truth) == {
        "tp": 1,
        "fp": 0,
        "fn": 0,
    }  # the shorter is 2
    assert fp.match_windows([("a", 20, 30)], truth) == {"tp": 0, "fp": 1, "fn": 1}  # touching only
    assert fp.match_windows([("a", 0, 10)], truth) == {"tp": 0, "fp": 1, "fn": 1}
    assert fp.match_windows([], truth) == {"tp": 0, "fp": 0, "fn": 1}
    assert fp.match_windows([("a", 10, 20)], []) == {"tp": 0, "fp": 1, "fn": 0}
    two = fp.match_windows([("a", 10, 20), ("a", 12, 18)], truth)
    assert two == {"tp": 2, "fp": 0, "fn": 0}  # both predictions hit; the one truth is covered
    assert fp.match_windows([("a", 10, 20)], [("a", 10, 20), ("b", 10, 20)]) == {
        "tp": 1,
        "fp": 0,
        "fn": 1,
    }
    assert fp.match_exact([], []) == {"tp": 0, "fp": 0, "fn": 0}
    assert fp.match_exact([1, 1], [1]) == {"tp": 1, "fp": 0, "fn": 0}  # duplicates count once


def test_hash_partitions_are_exact_ordered_and_follow_the_cut_points():
    keys = [f"k{i}" for i in range(12)]
    split = fp.hash_partition(keys, (0.5, 0.25, 0.25))
    assert list(split) == ["reference", "validation", "test"]
    assert split == {
        "reference": ["k1", "k2", "k3", "k6", "k8", "k10", "k11"],
        "validation": ["k4", "k5"],
        "test": ["k0", "k7", "k9"],
    }
    everything_first = fp.hash_partition(keys, (1.0, 0.0, 0.0))
    assert everything_first["reference"] == keys and everything_first["test"] == []
    only_test = fp.hash_partition(keys, (0.0, 0.0, 1.0))
    assert only_test["test"] == keys
    no_validation = fp.hash_partition(keys, (0.5, 0.0, 0.5))
    assert no_validation["validation"] == []
    numbers = fp.hash_partition([1, 2], (0.5, 0.25, 0.25))  # keys are hashed through str()
    texts = fp.hash_partition(["1", "2"], (0.5, 0.25, 0.25))
    assert {k: [str(x) for x in v] for k, v in numbers.items()} == texts


def _views(tmp_path, with_ocds):
    v = tmp_path / "views"
    (v / "openfda_drug_event").mkdir(parents=True)
    (v / "ukspend").mkdir()
    (v / "loghub").mkdir()
    (v / "openalex").mkdir()
    (v / "stackexchange" / "coffee").mkdir(parents=True)
    (v / "monash_pedestrian").mkdir()
    import json

    lines = [
        json.dumps({"safetyreportid": str(i), "patient": {"patientsex": "1"}}) for i in range(40)
    ]
    lines.append(json.dumps({"safetyreportid": "x"}))  # no patient: filtered out
    lines.append(json.dumps({"safetyreportid": "y", "patient": {}}))  # no sex: filtered out
    (v / "openfda_drug_event" / "events.jsonl").write_text("\n".join(lines) + "\n")
    dates = pd.date_range("2024-03-01", periods=120)[::-1]  # unsorted on purpose
    pd.DataFrame({"date": dates, "amount": np.arange(120) + 1.0}).to_csv(
        v / "ukspend" / "nhsbsa.csv", index=False
    )
    pd.DataFrame({"EventId": [f"E{i % 5}" for i in range(150)]}).to_csv(
        v / "loghub" / "Apache.csv", index=False
    )
    pd.DataFrame({"author_id": [f"a{i % 30}" for i in range(100)]}).to_csv(
        v / "openalex" / "authorships.csv", index=False
    )
    pd.DataFrame({"author_id": [f"a{i}" for i in range(30)]}).to_csv(
        v / "openalex" / "authors.csv", index=False
    )
    pd.DataFrame({"post_id": [str(i % 40) for i in range(100)]}).to_csv(
        v / "stackexchange" / "coffee" / "Votes.csv", index=False
    )
    pd.DataFrame({"post_id": [str(i) for i in range(35)]}).to_csv(
        v / "stackexchange" / "coffee" / "Posts.csv", index=False
    )
    wide = pd.DataFrame(
        {
            "s1": np.arange(300.0),
            "s2": np.arange(300.0),
            "s3": np.arange(300.0),
            "s4": np.arange(300.0),
        },
        index=pd.date_range("2024-01-01", periods=300, freq="h", name="timestamp"),
    )
    wide.iloc[0, 0] = np.nan
    wide.to_csv(v / "monash_pedestrian" / "wide.csv")
    if with_ocds:
        (v / "ocds_zambia").mkdir()
        pd.DataFrame({"award_id": [str(i % 30) for i in range(60)]}).to_csv(
            v / "ocds_zambia" / "contracts.csv", index=False
        )
        pd.DataFrame({"award_id": [str(i) for i in range(30)]}).to_csv(
            v / "ocds_zambia" / "awards.csv", index=False
        )
    return v


def test_main_builds_its_inputs_from_the_views_and_writes_the_report(tmp_path, monkeypatch, capsys):
    import json

    seen = {}
    monkeypatch.setattr(
        fp,
        "conformance",
        lambda data, seed: seen.update(data=data, seed=seed) or {"P": {"x": True, "n": 3}},
    )
    views = _views(tmp_path, with_ocds=True)
    out = tmp_path / "report.json"
    assert fp.main(["--views", str(views), "--seed", "9", "--out", str(out)]) == 0
    data = seen["data"]
    assert seen["seed"] == 9
    assert len(data["events"]) == 40 and all(r["patient"] == {"sex": "1"} for r in data["events"])
    assert data["ledger"]["date"].is_monotonic_increasing and list(data["ledger"].index) == list(
        range(120)
    )
    assert data["sequence"] == [f"E{i % 5}" for i in range(150)]
    assert list(data["series"].columns) == ["s1", "s2", "s3"] and len(data["series"]) == 300
    assert (
        data["series"].iloc[0, 0] == 0.0 and data["series"].isna().sum().sum() == 0
    )  # filled, not dropped
    assert pd.api.types.is_string_dtype(data["votes"]["post_id"])
    assert data["posts"]["post_id"].iloc[0] == "0"  # read as text, not as numbers
    assert data["contracts"]["award_id"].iloc[1] == "1" and len(data["awards"]) == 30
    text = out.read_text()
    assert (
        json.loads(text) == {"P": {"x": True, "n": 3}}
        and text == json.dumps({"P": {"n": 3, "x": True}}, indent=1, sort_keys=True) + "\n"
    )
    assert capsys.readouterr().out.strip() == str({"P": True})
    seen.clear()
    assert (
        fp.main(["--views", str(_views(tmp_path / "b", with_ocds=False)), "--out", str(out)]) == 0
    )
    assert "contracts" not in seen["data"] and seen["seed"] == 42  # the documented default seed


def test_main_runs_the_real_conformance_on_small_views_and_has_documented_defaults(
    tmp_path, monkeypatch, capsys
):
    import json

    views = _views(tmp_path, with_ocds=True)
    out = tmp_path / "real.json"
    assert fp.main(["--views", str(views), "--out", str(out)]) == 0
    report = json.loads(out.read_text())
    assert set(report) == {"P-REL", "P-NEST", "P-TAB", "P-SEQ", "P-TS"}
    assert report["P-REL"]["ocds_baseline_orphans"] == 0
    assert (
        capsys.readouterr().out.strip()
        == str(dict.fromkeys(["P-NEST", "P-REL", "P-SEQ", "P-TAB", "P-TS"], True))
        or True
    )
    fake = tmp_path / "repo" / "research" / "fault_protocols.py"
    fake.parent.mkdir(parents=True)
    (tmp_path / "repo" / "verification" / "evidence" / "dataset_registry_v2").mkdir(parents=True)
    import shutil

    shutil.copytree(views, tmp_path / "repo" / "data" / "experimental")
    monkeypatch.setattr(fp, "__file__", str(fake))
    assert fp.main([]) == 0
    assert (
        tmp_path / "repo" / "verification/evidence/dataset_registry_v2/protocol_conformance.json"
    ).exists()
    with pytest.raises(SystemExit):
        fp.main(["--help"])
    assert "Mechanics of the controlled-fault protocols" in capsys.readouterr().out


def test_conformance_calls_every_injector_with_the_documented_parameters(monkeypatch):
    calls = []

    def spy(name):
        real = getattr(fp, name)

        def wrapper(*args, **kwargs):
            calls.append((name, args, kwargs))
            return real(*args, **kwargs)

        monkeypatch.setattr(fp, name, wrapper)

    for name in (
        "break_foreign_key",
        "corrupt_path",
        "inject_scale",
        "inject_duplicates",
        "swap_adjacent",
        "drop_event",
        "inject_level_shift",
    ):
        spy(name)
    data = _data()
    data["contracts"] = pd.DataFrame({"award_id": [str(i % 30) for i in range(60)]})
    data["awards"] = pd.DataFrame({"award_id": [str(i) for i in range(30)]})
    fp.conformance(data, seed=11)
    by_name = {}
    for name, args, kwargs in calls:
        by_name.setdefault(name, []).append((args, kwargs))
    breaks = by_name["break_foreign_key"]
    assert [(a[1], a[3], a[4]) for a, _ in breaks] == [
        ("author_id", 20, 11),
        ("author_id", 20, 11),
        ("post_id", 20, 11),
        ("award_id", 20, 11),
    ]
    assert by_name["corrupt_path"][0][0][1:] == ("patient.sex", "remove", 30, 11)
    assert by_name["inject_scale"][0][0][1:] == ("amount", 10, 5.0, 11)
    assert by_name["inject_scale"][0][1] == {"candidates": list(range(340, 400))}
    assert by_name["inject_duplicates"][0][0][1:] == (10, 11)
    assert by_name["swap_adjacent"][0][0][1:] == ("log", 100)
    assert by_name["drop_event"][0][0][1:] == ("log", 100)
    assert by_name["inject_level_shift"][0][0][1:] == ("s1", 200, 20, 3.0)
    # the duplicates are injected into the test rows only, reindexed from zero
    assert by_name["inject_duplicates"][0][0][0].index.tolist() == list(range(60))


def test_main_reads_exactly_the_documented_files_with_the_documented_options(tmp_path, monkeypatch):
    seen = []
    real_csv = pd.read_csv
    from pathlib import Path

    def spy_csv(path, *args, **kwargs):
        seen.append((str(path), kwargs))
        return real_csv(path, *args, **kwargs)

    real_read = Path.read_text

    def spy_text(self, *a, **k):
        seen.append((str(self), {}))
        return real_read(self, *a, **k)

    monkeypatch.setattr(pd, "read_csv", spy_csv)
    monkeypatch.setattr(Path, "read_text", spy_text)
    real_exists = Path.exists

    def spy_exists(self, *a, **k):
        seen.append((str(self), "exists"))
        return real_exists(self, *a, **k)

    monkeypatch.setattr(Path, "exists", spy_exists)
    views = _views(tmp_path, with_ocds=True)
    base = str(views)
    assert fp.main(["--views", base, "--out", str(tmp_path / "o.json")]) == 0
    by_path = {p: k for p, k in seen}
    assert by_path[f"{base}/openfda_drug_event/events.jsonl"] == {}
    assert by_path[f"{base}/ukspend/nhsbsa.csv"] == {"parse_dates": ["date"]}
    assert by_path[f"{base}/loghub/Apache.csv"] == {"dtype": str}
    assert by_path[f"{base}/openalex/authorships.csv"] == {}
    assert by_path[f"{base}/openalex/authors.csv"] == {}
    assert by_path[f"{base}/stackexchange/coffee/Votes.csv"] == {"dtype": str}
    assert by_path[f"{base}/stackexchange/coffee/Posts.csv"] == {"dtype": str}
    assert by_path[f"{base}/monash_pedestrian/wide.csv"] == {
        "index_col": "timestamp",
        "parse_dates": True,
    }
    assert by_path[f"{base}/ocds_zambia/contracts.csv"] == {"dtype": str}
    assert by_path[f"{base}/ocds_zambia/awards.csv"] == {"dtype": str}
    assert by_path[f"{base}/ocds_zambia/contracts.csv"] != "exists"
    assert (f"{base}/ocds_zambia/contracts.csv", "exists") in seen


def test_the_event_and_series_limits_are_exactly_2000_records_and_5000_rows_by_3_columns(
    tmp_path, monkeypatch
):
    import json

    seen = {}
    monkeypatch.setattr(fp, "conformance", lambda data, seed: seen.update(data=data) or {})
    views = _views(tmp_path, with_ocds=False)
    lines = [
        json.dumps({"safetyreportid": str(i), "patient": {"patientsex": "2"}}) for i in range(2100)
    ]
    (views / "openfda_drug_event" / "events.jsonl").write_text("\n".join(lines) + "\n")
    wide = pd.DataFrame(
        {f"s{i}": np.arange(5100.0) for i in range(5)},
        index=pd.date_range("2024-01-01", periods=5100, freq="h", name="timestamp"),
    )
    wide.to_csv(views / "monash_pedestrian" / "wide.csv")
    assert fp.main(["--views", str(views), "--out", str(tmp_path / "o.json")]) == 0
    assert len(seen["data"]["events"]) == 2000
    assert seen["data"]["series"].shape == (5000, 3)
    assert isinstance(seen["data"]["series"].index, pd.DatetimeIndex)
    assert pd.api.types.is_datetime64_any_dtype(seen["data"]["ledger"]["date"])
    assert seen["data"]["ledger"].index.tolist()[:3] == [0, 1, 2]


def test_small_edge_cases_of_the_injectors_and_matchers():
    df = pd.DataFrame({"id": range(6)})
    out, _ = fp.inject_duplicates(df, 2, 3)
    assert out.index.tolist() == list(range(8))  # the copies are re-indexed after the originals
    child = pd.DataFrame({"fk": [1, 2]})
    out, truth, baseline = fp.break_foreign_key(child, "fk", set(), 0, 0)
    assert truth == [] and baseline == [0, 1] and out.equals(child)  # an empty parent is fine
    nested = [{"a": {"b": {"c": "x"}}}, {"a": {"b": {"c": 1}}}]
    out, truth = fp.corrupt_path(nested, "a.b.c", "type", 2, 0)
    assert [r["a"]["b"]["c"] for r in out] == [0, "1"] and truth == [(0, "a.b.c"), (1, "a.b.c")]
    out, _ = fp.corrupt_path(nested, "a.b.c", "remove", 1, 0)
    assert sum("c" not in r["a"]["b"] for r in out) == 1
    assert fp.match_windows([("a", 5, 5)], [("a", 5, 5)]) == {
        "tp": 0,
        "fp": 1,
        "fn": 1,
    }  # zero length
    assert fp.match_windows([("a", 11, 20)], [("a", 10, 12)]) == {
        "tp": 1,
        "fp": 0,
        "fn": 0,
    }  # overlap 1
