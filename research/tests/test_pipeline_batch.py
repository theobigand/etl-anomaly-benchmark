"""Batch-level pipeline faults: batches, operators with truth, profiles, constraints, metrics."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_batch as pb  # noqa: E402


def _table(n=2400, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    x[:, 1] = 0.8 * x[:, 0] + 0.6 * x[:, 1]
    x[:, 2] += 3
    stamps = pd.date_range("2020-01-01", periods=n, freq="h")
    return pd.DataFrame(x, columns=list("abcd")).assign(**{pb.TIME: stamps})


def _ref(table=None):
    batches = pb.make_batches(table if table is not None else _table())
    r = pb.split_batches(len(batches))[0]
    return batches, pb.Reference([batches[i] for i in r])


def test_batches_are_consecutive_equal_and_drop_only_the_remainder():
    table = _table(2410)
    batches = pb.make_batches(table)
    k = pb.batch_size(2410)
    assert k == 24 and len(batches) == 2410 // 24 and {len(b) for b in batches} == {24}
    assert batches[1][pb.TIME].iloc[0] == table[pb.TIME].iloc[24]
    assert [len(r) for r in pb.split_batches(100)] == [40, 20, 40]


def test_each_fault_changes_what_its_name_says_and_leaves_the_clean_batch_untouched():
    batches, ref = _ref()
    batch, history = batches[50], batches[:50]
    rng = lambda: np.random.default_rng(1)  # noqa: E731

    def fault(mechanism, level=2):
        return pb.apply_fault(batch, mechanism, level, rng(), history=history, sd=ref.sd)

    assert len(fault("partial_load")) == round(len(batch) * 0.1)
    assert len(fault("duplicate_load")) == 2 * len(batch)
    stale = fault("stale_batch", 1)
    assert stale[pb.TIME].max() == history[-3][pb.TIME].max()
    nulls = fault("null_spike", 2)
    assert nulls.drop(columns=pb.TIME).isna().all().sum() == 1
    assert len(fault("schema_drop", 0).columns) == len(batch.columns) - 1
    scaled = fault("unit_change", 2)
    changed = [c for c in "abcd" if not np.allclose(scaled[c], batch[c])]
    assert len(changed) == 1 and np.allclose(scaled[changed[0]], batch[changed[0]] * 1000)
    shifted = fault("distribution_shift", 1)
    delta = [(shifted[c] - batch[c]).mean() for c in "abcd"]
    assert max(delta) == pytest.approx(float(ref.sd[[c for c in "abcd"][int(np.argmax(delta))]]))
    mixed = fault("silent_corruption", 2)
    for c in "abcd":  # marginals are kept: the same values, in another order
        assert sorted(mixed[c]) == sorted(batch[c])
    assert not mixed[list("abcd")].equals(batch[list("abcd")])
    assert batch.equals(batches[50])  # the input is never modified
    with pytest.raises(ValueError):
        pb.apply_fault(batch, "mystery", 0, rng(), history=history, sd=ref.sd)


def test_silent_corruption_breaks_the_correlation_that_the_marginals_keep():
    batches, ref = _ref(_table(6000))
    clean = batches[60]
    raw_clean = ref.raw(clean, batches[59])["corr_dist"]
    bad = pb.apply_fault(
        clean, "silent_corruption", 2, np.random.default_rng(3), history=batches[:60], sd=ref.sd
    )
    assert ref.raw(bad, batches[59])["corr_dist"] > raw_clean


def test_the_reference_is_built_from_the_reference_batches_only():
    batches, ref = _ref()
    r0 = pb.split_batches(len(batches))[0]
    changed = [b.copy() for b in batches]
    for i in range(r0.stop, len(changed)):  # only validation and test batches are altered
        changed[i] = changed[i].assign(a=1e6)
    same = pb.Reference([changed[i] for i in r0])
    assert same.mean.equals(ref.mean) and same.rows == ref.rows and same.lag == ref.lag
    altered = [b.copy() for b in batches]
    altered[0] = altered[0].assign(a=1e6)  # a reference batch altered: the reference must change
    assert not pb.Reference([altered[i] for i in r0]).mean.equals(ref.mean)


def test_a_missing_column_is_counted_and_its_features_are_missing_not_zero():
    batches, ref = _ref()
    dropped = batches[50].drop(columns="b")
    raw = ref.raw(dropped, batches[49])
    assert raw["absent"] == 1.0 and raw["null_b"] == 1.0 and np.isnan(raw["mean_b"])
    assert ref.raw(batches[50], batches[49])["absent"] == 0.0


def test_constraints_learned_on_reference_batches_do_not_flag_them_and_flag_a_partial_load():
    batches, ref = _ref()
    raw_ref = ref.raw_reference
    assert (pb.constraint_scores(ref, raw_ref) == 0).all()
    partial = pb.apply_fault(
        batches[50], "partial_load", 2, np.random.default_rng(0), history=batches[:50], sd=ref.sd
    )
    raw = pb.profile_stream(ref, [partial], batches[49])
    assert pb.constraint_scores(ref, raw)[0] > 0


def test_alert_metrics_use_the_validation_budget_and_report_clean_false_alerts():
    val = np.arange(100.0)  # 95th percentile is 94.05
    scores = np.array([10.0, 20.0, 99.0, 98.0])
    faulty = np.array([False, False, True, True])
    m = pb.alert_metrics(val, scores, faulty)
    assert m["recall"] == 1.0 and m["false_alert_rate"] == 0.0
    assert m["roc_auc"] == 1.0 and m["ap"] == 1.0
    worse = pb.alert_metrics(val, np.array([99.0, 20.0, 10.0, 98.0]), faulty)
    assert worse["false_alert_rate"] == 0.5 and worse["recall"] == 0.5
    only_clean = pb.alert_metrics(val, np.array([1.0, 2.0]), np.array([False, False]))
    assert "roc_auc" not in only_clean


def test_the_test_stream_has_the_stated_share_of_faulty_batches_and_a_truth_mask():
    batches, ref = _ref()
    test = pb.split_batches(len(batches))[2]
    stream, faulty = pb.deliver(batches, test, "partial_load", 2, np.random.default_rng(0), ref)
    assert faulty.sum() == round(pb.FAULT_SHARE * len(test)) and len(stream) == len(test)
    for batch, truth, i in zip(stream, faulty, test, strict=True):
        assert (len(batch) != len(batches[i])) == truth
    clean_stream, none = pb.deliver(batches, test, None, 0, np.random.default_rng(0), ref)
    assert not none.any() and all(
        a.equals(batches[i]) for a, i in zip(clean_stream, test, strict=True)
    )


def test_a_source_run_finds_gross_faults_misses_silent_ones_and_the_random_floor_is_near_chance():
    result = pb.run_source(_table(), seeds=(42, 1), learned=("isolation_forest",))
    res = result["results"]
    assert result["batches"] == {"reference": 40, "validation": 20, "test": 40}
    assert res["constraint_rules"]["partial_load"]["2"]["recall"] >= 0.9
    assert res["constraint_rules"]["null_spike"]["2"]["recall"] >= 0.9
    assert res["constraint_rules"]["silent_corruption"]["2"]["recall"] <= 0.3
    assert res["random"]["partial_load"]["2"]["recall"] <= 0.4
    assert 0.3 <= res["random"]["unit_change"]["2"]["roc_auc"] <= 0.7
    assert "knn" not in result["detectors"] and "isolation_forest" in result["detectors"]


def test_a_contaminated_reference_is_recorded_and_changes_the_reference():
    clean = pb.run_source(_table(), seeds=(42,), learned=("isolation_forest",))
    dirty = pb.run_source(_table(), seeds=(42,), contaminated=True, learned=("isolation_forest",))
    assert clean["contaminated_reference"] is False and dirty["contaminated_reference"] is True
    assert clean["results"] != dirty["results"]


def test_the_compact_profile_has_thirteen_dimensions_and_reads_the_largest_deviation_over_columns():
    batches, ref = _ref()
    raw = pb.profile_stream(ref, [batches[50]], batches[49])
    z = ref.standardise(raw)
    compact = ref.compact(z)
    assert compact.shape == (1, 13) and set(pb.SCALARS) <= set(compact.columns)
    shifted = batches[50].assign(a=batches[50]["a"] + 10 * float(ref.sd["a"]))
    zs = ref.standardise(pb.profile_stream(ref, [shifted], batches[49]))
    assert ref.compact(zs)["mean"].iloc[0] > 5 * max(compact["mean"].iloc[0], 0.5)
    absent = ref.compact(
        ref.standardise(pb.profile_stream(ref, [batches[50].drop(columns="b")], batches[49]))
    )
    assert absent["absent"].iloc[0] > 0 and not absent.isna().any().any()


def test_compact_detectors_are_fitted_on_the_compact_profile_and_reported_under_their_own_name():
    result = pb.run_source(_table(), seeds=(42,), learned=("isolation_forest_compact",))
    assert "isolation_forest_compact" in result["detectors"]
    assert "isolation_forest" not in result["detectors"]
    gross = result["results"]["isolation_forest_compact"]["partial_load"]["2"]["recall"]
    assert gross >= 0.9
    assert pb.FAMILY["isolation_forest_compact"] == "learned"


# ---------------------------------------------------------------------------------------------
# Exact-value tests: tiny frames where every count and statistic has one right answer.
# ---------------------------------------------------------------------------------------------
def _small(n=10, columns="abcd"):
    """``a`` runs 0..n-1 (each row identifiable); the other columns are distinct reals."""
    frame = pd.DataFrame({c: np.arange(n) * (i + 1.0) + 0.5 * i for i, c in enumerate(columns)})
    return frame.assign(**{pb.TIME: pd.date_range("2020-01-01", periods=n, freq="h")})


def _fault(frame, mechanism, level, seed=0, history=(), sd=None):
    sd = sd if sd is not None else frame.drop(columns=pb.TIME).std(ddof=0)
    return pb.apply_fault(
        frame, mechanism, level, np.random.default_rng(seed), history=list(history), sd=sd
    )


def test_an_unknown_mechanism_is_refused_by_name():
    with pytest.raises(ValueError, match=r"^unknown mechanism mystery$"):
        _fault(_small(), "mystery", 0)


def test_the_mechanism_table_and_split_constants_are_the_registered_ones():
    assert pb.PROTOCOL == "pipeline-batch-v1" and pb.SEEDS == (42, 1, 2, 3, 4)
    assert pb.ALERT_BUDGET == 0.05 and pb.FAULT_SHARE == 0.30 and pb.CONTAMINATION_SHARE == 0.05
    assert (pb.REFERENCE_SHARE, pb.VALIDATION_SHARE) == (0.40, 0.20)
    assert (pb.MIN_BATCH, pb.TARGET_BATCHES, pb.MIN_REFERENCE_FOR_NEURAL) == (24, 100, 200)
    assert pb.KS_SAMPLE == 2000 and pb.TIME == "_t" and pb.LEVELS == (0, 1, 2)
    assert (pb.WIDEN, pb.SHARE_FLOOR, pb.RATIO_FLOOR) == (0.20, 0.02, 0.10)
    assert pb.SEVERITY["schema_drop"] == (1, 2, -1) and pb.SEVERITY["stale_batch"] == (1, 3, 10)
    assert pb.SEVERITY["unit_change"] == (2.0, 10.0, 1000.0)
    assert pb.SEVERITY["partial_load"] == (0.7, 0.4, 0.1)
    assert set(pb.SEVERITY) == set(pb.MECHANISMS) and len(pb.MECHANISMS) == 8


def test_a_partial_load_keeps_the_stated_share_of_rows_in_their_original_order_without_repeats():
    frame = _small(10)
    assert [len(_fault(frame, "partial_load", lv)) for lv in (0, 1, 2)] == [7, 4, 2]
    kept = _fault(frame, "partial_load", 1)
    assert list(kept.index) == [0, 1, 2, 3] and "index" not in kept.columns
    assert kept["a"].is_monotonic_increasing and kept["a"].is_unique
    assert set(kept["a"]) <= set(frame["a"])
    assert len(_fault(_small(3), "partial_load", 2)) == 2  # never fewer than two rows


def test_a_duplicate_load_repeats_distinct_rows_and_renumbers_the_index():
    frame = _small(10)
    assert [len(_fault(frame, "duplicate_load", lv)) for lv in (0, 1, 2)] == [12, 15, 20]
    full = _fault(frame, "duplicate_load", 2)
    assert list(full.index) == list(range(20))
    assert sorted(full["a"].iloc[10:]) == sorted(frame["a"])  # every row exactly once more
    assert full.iloc[:10].reset_index(drop=True).equals(frame)
    assert len(_fault(_small(3), "duplicate_load", 0)) == 4  # at least one repeated row


def test_a_stale_batch_replays_the_batch_lag_loads_back_or_the_oldest_available_one():
    frame = _small(10)
    history = [_small(10).assign(a=float(i)) for i in range(5)]
    assert _fault(frame, "stale_batch", 0, history=history).equals(history[-1])
    assert _fault(frame, "stale_batch", 1, history=history).equals(history[-3])
    assert _fault(frame, "stale_batch", 2, history=history).equals(history[0])  # lag capped at 5
    out = _fault(frame, "stale_batch", 0, history=history)
    assert out is not history[-1]
    out["a"] = -1.0
    assert history[-1]["a"].iloc[0] == 4.0
    assert _fault(frame, "stale_batch", 1, history=[]).equals(frame)  # nothing to replay


def test_a_null_spike_blanks_the_stated_share_of_one_column_only():
    frame = _small(10)
    for level, count in ((0, 1), (1, 3), (2, 10)):
        out = _fault(frame, "null_spike", level)
        holes = out.drop(columns=pb.TIME).isna().sum()
        assert holes.sum() == count and (holes > 0).sum() == 1
        assert out[pb.TIME].equals(frame[pb.TIME])
    assert frame.isna().sum().sum() == 0


def test_a_schema_drop_removes_the_stated_number_of_value_columns_and_never_the_last_one():
    four = _small(10, "abcd")
    assert [len(_fault(four, "schema_drop", lv).columns) for lv in (0, 1, 2)] == [4, 3, 4]
    seven = _small(10, "abcdefg")
    assert [len(_fault(seven, "schema_drop", lv).columns) for lv in (0, 1, 2)] == [7, 6, 6]
    # a third of the columns, at least one (4 // 3 = 1) and at most two for seven columns
    assert len(_fault(four, "schema_drop", 2).columns) == 4
    assert len(_fault(_small(10, "abc"), "schema_drop", 1).columns) == 2
    assert len(_fault(_small(10, "ab"), "schema_drop", 1).columns) == 2
    assert pb.TIME in _fault(four, "schema_drop", 2).columns
    assert len(_fault(_small(10, "abcdefgh"), "schema_drop", 0).columns) == 8


def test_a_silent_corruption_permutes_values_inside_exactly_two_columns():
    frame = _small(40, "abcd")
    out = _fault(frame, "silent_corruption", 2)
    changed = [c for c in "abcd" if not out[c].equals(frame[c])]
    assert len(changed) == 2
    for c in "abcd":
        assert sorted(out[c]) == sorted(frame[c])
    one = _fault(_small(40, "ab"), "silent_corruption", 2)
    assert len([c for c in "ab" if not one[c].equals(_small(40, "ab")[c])]) == 2
    small = _fault(_small(10, "abcd"), "silent_corruption", 0, seed=3)
    rows = (small[list("abcd")] != _small(10, "abcd")[list("abcd")]).any(axis=1)
    assert rows.sum() <= 2


def test_the_stream_profile_reads_each_batch_against_the_one_delivered_before_it():
    batches, ref = _ref()
    stream = [batches[50], batches[50]]  # the second load repeats the first
    raw = pb.profile_stream(ref, stream, batches[49])
    assert list(raw.columns) == list(ref.mean.index)
    assert raw["repeat_prev"].iloc[1] == 1.0 and raw["repeat_prev"].iloc[0] == 0.0
    assert raw["lag"].iloc[1] == 0.0
    assert raw["lag"].iloc[0] > 0.0
    first = pb.profile_stream(ref, [batches[50]], None)
    assert first["repeat_prev"].iloc[0] == 0.0 and first["lag"].iloc[0] == 1.0


def _mini_batches():
    """Four reference batches of four rows over hours; columns a and b."""
    stamps = pd.date_range("2020-01-01", periods=16, freq="h")
    a = np.array([1.0, 2, 3, 4, 2, 3, 4, 5, 3, 4, 5, 6, 4, 5, 6, 8])
    b = np.array([10.0, 10, 20, 20, 10, 10, 20, 30, 10, 20, 20, 30, 10, 20, 30, 30])
    table = pd.DataFrame({"a": a, "b": b, pb.TIME: stamps})
    return [table.iloc[i : i + 4].reset_index(drop=True) for i in range(0, 16, 4)]


def test_the_reference_holds_the_pooled_spread_the_typical_size_lag_and_correlation():
    batches = _mini_batches()
    ref = pb.Reference(batches)
    pooled = pd.concat(batches, ignore_index=True)
    assert ref.columns == ["a", "b"]
    assert ref.sd.to_dict() == pytest.approx(pooled[["a", "b"]].std(ddof=0).to_dict())
    assert ref.rows == 4.0
    hour = pd.Timedelta("1h").value
    assert ref.lag == 4.0 * hour  # the batches end four hours apart
    assert ref.corr.shape == (2, 2)
    assert ref.corr[0, 1] == pytest.approx(pooled["a"].corr(pooled["b"]))
    assert ref.corr[0, 0] == pytest.approx(1.0)
    assert set(ref.sample) == {"a", "b"} and sorted(ref.sample["a"]) == sorted(pooled["a"])
    assert len(ref.raw_reference) == 4 and list(ref.raw_reference.index) == [0, 1, 2, 3]
    assert ref.mean.index.equals(ref.raw_reference.columns)


def test_a_constant_column_gets_a_unit_spread_and_a_single_batch_a_unit_lag():
    batches = _mini_batches()
    flat = [b.assign(b=5.0) for b in batches]
    ref = pb.Reference(flat)
    assert ref.sd["b"] == 1.0 and ref.sd["a"] > 1.0
    assert ref.corr[0, 1] == 0.0  # an undefined correlation counts as none
    solo = pb.Reference(batches[:1])
    assert solo.lag == 1.0
    equal_ends = [b.assign(**{pb.TIME: batches[0][pb.TIME]}) for b in batches]
    assert pb.Reference(equal_ends).lag == 1.0  # all gaps are zero: not a usable lag


def test_the_median_rows_and_lag_ignore_one_odd_batch():
    batches = _mini_batches()
    odd = [batches[0], batches[1].iloc[:2], batches[2], batches[3]]
    assert pb.Reference(odd).rows == 4.0
    stamps = pd.date_range("2020-01-01", periods=4, freq="h")
    one_hour = [b.assign(**{pb.TIME: stamps}) for b in batches[:1]]
    assert pb.Reference(one_hour).rows == 4.0


def test_the_ks_sample_is_a_seeded_permutation_capped_at_the_stated_size(monkeypatch):
    batches = _mini_batches()
    monkeypatch.setattr(pb, "KS_SAMPLE", 5)
    ref = pb.Reference(batches)
    pooled = pd.concat(batches, ignore_index=True)
    order = np.random.default_rng(0).permutation(16)[:5]
    assert ref.sample["a"].tolist() == pooled["a"].to_numpy()[order].tolist()
    with_nan = [b.copy() for b in batches]
    with_nan[0].loc[0, "a"] = np.nan
    again = pb.Reference(with_nan)
    assert len(again.sample["a"]) == 5 and not np.isnan(again.sample["a"]).any()


def test_the_reference_scales_features_by_their_spread_and_keeps_their_range():
    ref = pb.Reference(_mini_batches())
    raw = ref.raw_reference
    assert ref.mean.to_dict() == pytest.approx(raw.mean().to_dict())
    assert ref.std.to_dict() == pytest.approx(raw.std(ddof=0).replace(0, 1.0).fillna(1.0).to_dict())
    assert (ref.std > 0).all()
    assert ref.lo.to_dict() == raw.min().to_dict() and ref.hi.to_dict() == raw.max().to_dict()
    z = ref.standardise(raw)
    assert z["rows"].tolist() == [0.0, 0.0, 0.0, 0.0]  # every batch has the typical size
    assert list(z.columns) == list(ref.mean.index)


def test_raw_profile_features_of_a_delivered_batch_are_computed_against_the_reference():
    batches = _mini_batches()
    ref = pb.Reference(batches)
    delivered = batches[1].iloc[:3].reset_index(drop=True).copy()
    delivered.loc[2, "a"] = np.nan
    row = ref.raw(delivered, batches[0])
    assert row["rows"] == 3 / 4
    assert row["dup_share"] == 0.0 and row["absent"] == 0.0
    assert row["null_a"] == pytest.approx(1 / 3) and row["null_b"] == 0.0
    clean_a = delivered["a"].dropna()
    assert row["mean_a"] == pytest.approx(clean_a.mean())
    assert row["std_a"] == pytest.approx(clean_a.std(ddof=0))
    q05, q50, q95 = clean_a.quantile([0.05, 0.5, 0.95])
    assert (row["q05_a"], row["q50_a"], row["q95_a"]) == pytest.approx((q05, q50, q95))
    from scipy.stats import ks_2samp

    assert row["ks_a"] == pytest.approx(ks_2samp(clean_a.to_numpy(), ref.sample["a"]).statistic)
    gap = delivered[pb.TIME].max().value - batches[0][pb.TIME].max().value
    assert row["lag"] == pytest.approx(gap / ref.lag)
    assert row["repeat_prev"] == pytest.approx(1 / 3)  # only the row (2, 10) was delivered before
    assert row["corr_dist"] == row["corr_dist"]  # not NaN: two columns and three rows


def test_duplicates_repeats_of_the_previous_load_and_missing_columns_are_counted():
    batches = _mini_batches()
    ref = pb.Reference(batches)
    doubled = pd.concat([batches[1], batches[1].iloc[:2]], ignore_index=True)
    row = ref.raw(doubled, batches[0])
    assert row["dup_share"] == pytest.approx(2 / 6) and row["rows"] == 6 / 4
    same = ref.raw(batches[1], batches[1])
    assert same["repeat_prev"] == 1.0 and same["lag"] == 0.0
    half = pd.concat([batches[1].iloc[:2], batches[2].iloc[:2].assign(a=99.0)], ignore_index=True)
    assert ref.raw(half, batches[1])["repeat_prev"] == 0.5
    near = batches[1].copy()
    near["a"] = near["a"] + 1e-12
    assert ref.raw(near, batches[1])["repeat_prev"] == 1.0  # rounded to nine decimals
    gone = batches[1].drop(columns="b")
    out = ref.raw(gone, batches[0])
    assert out["absent"] == 1.0 and out["null_b"] == 1.0
    assert all(np.isnan(out[f"{s}_b"]) for s in ("mean", "std", "q05", "q50", "q95", "ks"))
    assert np.isnan(out["corr_dist"])  # one column left: no correlation
    assert ref.raw(gone, batches[1])["repeat_prev"] == 1.0  # only the shared columns are compared


def test_an_all_missing_column_and_a_tiny_batch_have_no_value_statistics_or_correlation():
    batches = _mini_batches()
    ref = pb.Reference(batches)
    empty = batches[1].assign(a=np.nan)
    row = ref.raw(empty, batches[0])
    assert row["null_a"] == 1.0 and np.isnan(row["mean_a"]) and np.isnan(row["ks_a"])
    assert not np.isnan(row["mean_b"])
    tiny = ref.raw(batches[1].iloc[:2], batches[0])
    assert np.isnan(tiny["corr_dist"])
    three = ref.raw(batches[1].iloc[:3], batches[0])
    assert not np.isnan(three["corr_dist"])
    no_rows = ref.raw(batches[1].iloc[:0], batches[0])
    assert no_rows["dup_share"] == 0.0 and no_rows["rows"] == 0.0 and no_rows["repeat_prev"] == 0.0


def test_the_correlation_distance_is_the_mean_absolute_change_of_the_correlation_matrix():
    batches = _mini_batches()
    ref = pb.Reference(batches)
    flipped = batches[1].assign(b=batches[1]["b"].to_numpy()[::-1])
    local = flipped[["a", "b"]].corr().fillna(0.0).to_numpy()
    expected = float(np.abs(local - ref.corr).mean())
    assert ref.raw(flipped, batches[0])["corr_dist"] == pytest.approx(expected)
    reversed_cols = flipped[["b", "a"]]
    sub = ref.raw(reversed_cols.assign(**{pb.TIME: flipped[pb.TIME]}), batches[0])
    assert sub["corr_dist"] == pytest.approx(expected)


# ---------------------------------------------------------------------------------------------
# Constraints, detector scores, fitting, delivery, metrics
# ---------------------------------------------------------------------------------------------
class _Stub:
    """The part of a Reference that the constraint rule reads."""

    def __init__(self, lo, hi, columns=("a",)):
        self.columns = list(columns)
        names = ["rows", "dup_share", "repeat_prev", "lag", "absent"]
        names += [f"null_{c}" for c in columns] + [f"mean_{c}" for c in columns]
        self.lo = pd.Series({n: lo.get(n, 0.0) for n in names})
        self.hi = pd.Series({n: hi.get(n, 0.0) for n in names})
        self.names = names


def _raw_row(stub, **values):
    row = {n: float(stub.lo[n] + stub.hi[n]) / 2 for n in stub.names}
    row.update(values)
    return pd.DataFrame([row])


def _score(stub, **values):
    return float(pb.constraint_scores(stub, _raw_row(stub, **values))[0])


def test_the_absent_column_count_has_a_half_column_floor():
    stub = _Stub({}, {})
    assert _score(stub, absent=0.0) == 0.0
    # allowed interval [-0.5, 0.5], half-width 0.5: one absent column is two half-widths over
    assert _score(stub, absent=1.0) == pytest.approx(1.0)
    assert _score(stub, absent=3.0) == pytest.approx(5.0)


def test_row_count_and_lag_have_a_ratio_floor_and_shares_a_small_floor():
    stub = _Stub({"rows": 1.0, "lag": 1.0}, {"rows": 1.0, "lag": 1.0})
    assert _score(stub, rows=1.5) == pytest.approx((1.5 - 1.1) / 0.1)
    assert _score(stub, lag=0.5) == pytest.approx((0.9 - 0.5) / 0.1)
    assert _score(stub, rows=1.1) == 0.0
    flat = _Stub({}, {})
    for name in ("null_a", "dup_share", "repeat_prev"):
        assert _score(flat, **{name: 0.12}) == pytest.approx((0.12 - 0.02) / 0.02)
        assert _score(flat, **{name: 0.02}) == 0.0


def test_other_features_have_no_floor_and_the_range_is_widened_by_a_fifth_of_its_width():
    stub = _Stub({"mean_a": 0.0}, {"mean_a": 2.0})
    # slack 0.4: allowed [-0.4, 2.4]; half-width 1.4
    assert _score(stub, mean_a=3.4) == pytest.approx(1.0 / 1.4)
    assert _score(stub, mean_a=-1.4) == pytest.approx(1.0 / 1.4)
    assert _score(stub, mean_a=2.4) == 0.0
    point = _Stub({"mean_a": 1.0}, {"mean_a": 1.0})
    assert _score(point, mean_a=1.5) == pytest.approx(0.5 / 1e-12)  # a degenerate interval


def test_a_missing_value_is_no_violation_and_the_largest_excess_decides():
    stub = _Stub({"mean_a": 0.0}, {"mean_a": 2.0})
    assert _score(stub, mean_a=np.nan) == 0.0
    both = _score(stub, mean_a=3.4, absent=3.0)
    assert both == pytest.approx(5.0)
    rows = pd.concat([_raw_row(stub), _raw_row(stub, mean_a=3.4)], ignore_index=True)
    assert pb.constraint_scores(stub, rows).tolist() == pytest.approx([0.0, 1.0 / 1.4])


def test_each_column_adds_its_own_null_and_mean_constraints():
    stub = _Stub({}, {}, columns=("a", "b"))
    assert _score(stub, null_b=0.12, mean_b=0.0) == pytest.approx(5.0)
    assert _score(stub, mean_b=5.0) == pytest.approx(5.0 / 1e-12)


class _Scorer:
    def __init__(self, scores):
        self.scores, self.seen = scores, []

    def score(self, frame):
        self.seen.append(frame.copy())
        return pd.Series(self.scores(frame), index=frame.index)


def test_each_detector_reads_its_own_slice_of_the_standardised_profile():
    batches, ref = _ref()
    raw = pb.profile_stream(ref, [batches[50], batches[51]], batches[49])
    z = ref.standardise(raw)
    rules = pb.detector_scores("constraint_rules", ref, raw, {}, 1)
    assert rules.tolist() == pb.constraint_scores(ref, raw).tolist()
    volume = pb.detector_scores("volume_freshness", ref, raw, {}, 1)
    assert volume.tolist() == np.nanmax(np.abs(z[["rows", "lag"]].to_numpy()), axis=1).tolist()
    ks = pb.detector_scores("distribution_distance", ref, raw, {}, 1)
    expected = np.nanmax(z[[f"ks_{c}" for c in ref.columns]].to_numpy(), axis=1)
    assert ks.tolist() == expected.tolist()


def test_the_distribution_distance_ignores_missing_columns_and_the_floor_is_seeded_noise():
    batches, ref = _ref()
    gone = [batches[50].drop(columns=c) for c in ("a",)]
    raw = pb.profile_stream(ref, gone, batches[49])
    assert np.isnan(ref.standardise(raw)["ks_a"].iloc[0])
    score = pb.detector_scores("distribution_distance", ref, raw, {}, 1)
    assert not np.isnan(score).any() and score[0] >= 0.0
    only_a = raw.copy()
    only_a[[c for c in raw.columns if c.startswith("ks_")]] = np.nan
    assert pb.detector_scores("distribution_distance", ref, only_a, {}, 1).tolist() == [0.0]
    r1 = pb.detector_scores("random", ref, raw, {}, 7)
    assert r1.tolist() == np.random.default_rng(7).random(1).tolist()
    assert pb.detector_scores("random", ref, raw, {}, 8).tolist() != r1.tolist()
    two = pb.profile_stream(ref, [batches[50]] * 3, batches[49])
    assert len(pb.detector_scores("random", ref, two, {}, 7)) == 3


def test_learned_detectors_score_the_profile_and_compact_ones_the_compact_profile():
    batches, ref = _ref()
    raw = pb.profile_stream(ref, [batches[50]], batches[49])
    z = ref.standardise(raw)
    full, compact = _Scorer(lambda f: [1.5] * len(f)), _Scorer(lambda f: [2.5] * len(f))
    fitted = {"isolation_forest": full, "isolation_forest_compact": compact}
    assert pb.detector_scores("isolation_forest", ref, raw, fitted, 1).tolist() == [1.5]
    assert pb.detector_scores("isolation_forest_compact", ref, raw, fitted, 1).tolist() == [2.5]
    assert full.seen[0].equals(z) and compact.seen[0].equals(ref.compact(z))
    assert pb.detector_scores("isolation_forest", ref, raw, fitted, 1).dtype == float


def test_fitting_builds_each_detector_with_the_budget_and_seed_and_trains_on_its_profile(
    monkeypatch,
):
    import types

    built, fits = [], []

    class Detector:
        def fit(self, frame):
            fits.append(frame)

    def build(name, contamination, seed):
        built.append((name, contamination, seed))
        return Detector()

    monkeypatch.setitem(sys.modules, "deep_support", types.SimpleNamespace(build=build))
    batches, ref = _ref()
    z = ref.standardise(ref.raw_reference)
    fitted = pb.fit_learned(ref, 9, ("isolation_forest", "isolation_forest_compact"))
    assert built == [("isolation_forest", 0.05, 9), ("isolation_forest", 0.05, 9)]
    assert list(fitted) == ["isolation_forest", "isolation_forest_compact"]
    assert fits[0].equals(z)
    assert fits[1].equals(ref.compact(z)) and fits[1].shape == (40, 13)
    built.clear()
    pb.fit_learned(ref, 1)
    assert [b[0] for b in built] == [n.removesuffix("_compact") for n in (*pb.LEARNED, *pb.COMPACT)]
    assert {b[2] for b in built} == {1}


def test_alert_metrics_need_both_kinds_of_batch_for_the_ranking_scores():
    val = np.arange(100.0)
    all_faulty = pb.alert_metrics(val, np.array([99.0, 98.0]), np.array([True, True]))
    assert set(all_faulty) == {"recall", "false_alert_rate"} or "roc_auc" not in all_faulty
    assert "roc_auc" not in all_faulty and "ap" not in all_faulty
    assert all_faulty["recall"] == 1.0
    equal = pb.alert_metrics(val, np.array([94.05, 99.0]), np.array([False, True]))
    assert equal["false_alert_rate"] == 0.0  # a score equal to the threshold is not an alert
    just_above = pb.alert_metrics(val, np.array([94.06, 99.0]), np.array([False, True]))
    assert just_above["false_alert_rate"] == 1.0


def test_delivery_faults_at_least_one_batch_and_the_share_applies_to_the_stream_length():
    batches, ref = _ref()
    indices = range(10, 12)
    _, faulty = pb.deliver(batches, indices, "partial_load", 2, np.random.default_rng(0), ref)
    assert faulty.sum() == 1
    ten = range(10, 20)
    _, faulty = pb.deliver(batches, ten, "partial_load", 2, np.random.default_rng(0), ref)
    assert faulty.sum() == 3
    _, faulty = pb.deliver(
        batches, ten, "partial_load", 2, np.random.default_rng(0), ref, share=0.6
    )
    assert faulty.sum() == 6
    stream, faulty = pb.deliver(batches, ten, "stale_batch", 1, np.random.default_rng(0), ref)
    for batch, truth, i in zip(stream, faulty, ten, strict=True):
        if truth:
            assert batch[pb.TIME].max() == batches[i - 3][pb.TIME].max()  # three loads back
        else:
            assert batch.equals(batches[i])


# ---------------------------------------------------------------------------------------------
# run_source: the wiring between the stages, observed through spies on the real functions
# ---------------------------------------------------------------------------------------------
def _spy(monkeypatch, name):
    calls = []
    original = getattr(pb, name)

    def wrapper(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(pb, name, wrapper)
    return calls


def test_a_source_run_reports_its_protocol_sizes_detectors_and_the_neural_note():
    result = pb.run_source(_table(), seeds=(42,), learned=("isolation_forest",))
    assert result["protocol"] == "pipeline-batch-v1"
    assert result["contaminated_reference"] is False
    assert result["batch_rows"] == 24 and result["seeds"] == [42]
    assert result["batches"] == {"reference": 40, "validation": 20, "test": 40}
    assert result["faulty_test_batches"] == 12
    assert result["detectors"] == [
        "constraint_rules",
        "volume_freshness",
        "distribution_distance",
        "isolation_forest",
        "random",
    ]
    assert result["neural"] == "not run: fewer than MIN_REFERENCE_FOR_NEURAL reference batches"
    assert list(result["results"]) == result["detectors"]
    for by_mechanism in result["results"].values():
        assert list(by_mechanism) == list(pb.MECHANISMS)
        for by_level in by_mechanism.values():
            assert list(by_level) == ["0", "1", "2"]
            for cell in by_level.values():
                assert set(cell) == {"recall", "false_alert_rate", "roc_auc", "ap"}


def test_the_number_of_features_is_the_profile_width_of_the_reference():
    table = _table()
    batches, ref = _ref(table)
    result = pb.run_source(table, seeds=(42,), learned=())
    assert result["features"] == len(ref.mean)
    assert result["detectors"] == [
        "constraint_rules",
        "volume_freshness",
        "distribution_distance",
        "random",
    ]


def test_cells_average_the_seeds_and_a_second_seed_is_not_a_repeat_of_the_first():
    table = _table()
    both = pb.run_source(table, seeds=(42, 1), learned=())["results"]
    one = pb.run_source(table, seeds=(42,), learned=())["results"]
    two = pb.run_source(table, seeds=(1,), learned=())["results"]
    for d in ("constraint_rules", "random"):
        for m in ("partial_load", "silent_corruption"):
            for lv in ("0", "2"):
                for key in ("recall", "false_alert_rate", "roc_auc", "ap"):
                    want = (one[d][m][lv][key] + two[d][m][lv][key]) / 2
                    assert both[d][m][lv][key] == pytest.approx(want)
    assert (
        one["random"]["partial_load"]["0"]["recall"] != two["random"]["partial_load"]["0"]["recall"]
    )


def test_the_stages_receive_the_seed_the_previous_batch_and_a_stream_specific_generator(
    monkeypatch,
):
    table = _table()
    batches = pb.make_batches(table)
    fits = _spy(monkeypatch, "fit_learned")
    scores = _spy(monkeypatch, "detector_scores")
    streams = _spy(monkeypatch, "profile_stream")
    deliveries = _spy(monkeypatch, "deliver")
    pb.run_source(table, seeds=(7,), learned=("isolation_forest",))
    assert len(fits) == 1 and fits[0][0][1] == 7 and fits[0][0][2] == ("isolation_forest",)
    assert {args[4] for args, _ in scores} == {7}
    # one validation stream then 24 test streams (8 mechanisms x 3 severities)
    assert len(streams) == 1 + 24
    validation_previous = streams[0][0][2]
    assert validation_previous.equals(batches[39])  # the last reference batch, not a later one
    assert len(streams[0][0][1]) == 20 and streams[0][0][1][0].equals(batches[40])
    for args, _ in streams[1:]:
        assert args[2].equals(batches[59])  # the last validation batch precedes the test stream
    for k, (args, _) in enumerate(deliveries):
        mechanism, level = args[2], args[3]
        assert mechanism == pb.MECHANISMS[k // 3] and level == k % 3
        assert args[1] == range(60, 100)


def test_the_generator_of_each_stream_is_keyed_by_seed_mechanism_and_severity(monkeypatch):
    table = _table()
    states = []

    def capture(clean, indices, mechanism, level, rng, ref, share=pb.FAULT_SHARE):
        states.append((mechanism, level, rng.bit_generator.state["state"]["state"]))
        raise RuntimeError("stop")

    monkeypatch.setattr(pb, "deliver", capture)
    with pytest.raises(RuntimeError):
        pb.run_source(table, seeds=(7,), learned=())
    mechanism, level, state = states[0]
    assert (mechanism, level) == ("partial_load", 0)
    assert state == np.random.default_rng([7, 0, 0]).bit_generator.state["state"]["state"]
    assert state != np.random.default_rng([7, 0, 1]).bit_generator.state["state"]["state"]
    assert state != np.random.default_rng([8, 0, 0]).bit_generator.state["state"]["state"]


def test_a_contaminated_reference_replaces_the_stated_share_of_its_batches_with_faulty_ones(
    monkeypatch,
):
    table = _table()
    clean = pb.make_batches(table)
    references = _spy(monkeypatch, "Reference")
    pb.run_source(table, seeds=(42,), contaminated=True, learned=())
    assert len(references) == 2
    final = references[1][0][0]
    changed = [i for i, b in enumerate(final) if not b.equals(clean[i])]
    picks = np.random.default_rng(7).choice(40, 2, replace=False)
    assert changed == sorted(int(i) for i in picks)


def test_the_contaminating_faults_follow_the_seeded_draws_and_see_only_earlier_batches(
    monkeypatch,
):
    table = _table()
    clean = pb.make_batches(table)
    faults = _spy(monkeypatch, "apply_fault")
    pb.run_source(table, seeds=(42,), contaminated=True, learned=())
    sd = pb.Reference(clean[:40]).sd
    rng = np.random.default_rng(7)
    picks = rng.choice(40, 2, replace=False)
    for k, i in enumerate(picks):
        mechanism = pb.MECHANISMS[int(rng.integers(len(pb.MECHANISMS)))]
        level = int(rng.integers(3))
        args, kwargs = faults[k]
        assert (args[1], args[2]) == (mechanism, level)
        assert len(kwargs["history"]) == i
        assert kwargs["sd"].equals(sd)
        pb.apply_fault(clean[i], mechanism, level, rng, history=clean[:i], sd=sd)  # same draws


# ---------------------------------------------------------------------------------------------
# load_table, run_one, main
# ---------------------------------------------------------------------------------------------
def _pool(tmp_path, monkeypatch, frame, uci_id=9001, min_rows=50, spec=None):
    import json

    import chrono_injected as ci

    registry = tmp_path / "verification/evidence/dataset_registry"
    registry.mkdir(parents=True)
    meta = {
        "uci_id": uci_id,
        "name": "Toy",
        "tasks": ["Classification"],
        "target_col": ["y"],
        "variables": [{"name": "id", "role": "ID"}, {"name": "y", "role": "Target"}],
    }
    (registry / "uci_curated.json").write_text(
        json.dumps({"kept": [{"uci_id": 1, "name": "x"}, meta]})
    )
    (tmp_path / "data" / "pool").mkdir(parents=True)
    frame.to_csv(tmp_path / "data" / "pool" / f"{uci_id}.csv", index=False)
    monkeypatch.setattr(pb, "ROOT", tmp_path)
    monkeypatch.setitem(
        ci.TIME_SPECS, uci_id, spec or {"date": "date", "format": "%Y-%m-%d %H:%M:%S"}
    )
    monkeypatch.setattr(ci, "MIN_ROWS", min_rows)
    return meta


def _raw_frame(n=60, seed=0):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(rng.normal(size=(n, 5)), columns=[f"f{i}" for i in range(1, 6)])
    stamps = pd.date_range("2020-01-01", periods=n, freq="h")
    frame.insert(0, "date", stamps.strftime("%Y-%m-%d %H:%M:%S"))
    frame["id"] = np.arange(n)
    frame["trend"] = np.arange(n) * 1.0
    frame["y"] = rng.integers(0, 2, n)
    return frame


def test_a_table_is_loaded_sorted_by_time_without_ids_targets_trends_and_incomplete_rows(
    tmp_path, monkeypatch
):
    frame = _raw_frame().sample(frac=1, random_state=3).reset_index(drop=True)
    frame.loc[frame.index[5], "f1"] = np.nan
    twin = frame.index[10]
    frame.loc[twin, [f"f{i}" for i in range(1, 6)]] = frame.loc[
        frame.index[11], [f"f{i}" for i in range(1, 6)]
    ].to_numpy()
    _pool(tmp_path, monkeypatch, frame)
    table, info = pb.load_table(9001)
    columns = [f"f{i}" for i in range(1, 6)]
    assert list(table.columns) == [*columns, pb.TIME]
    assert info == {"name": "Toy", "rows": 58, "columns": columns}
    assert len(table) == 58 and list(table.index) == list(range(58))
    assert table[pb.TIME].is_monotonic_increasing
    assert table[columns].notna().all().all() and table[columns].duplicated().sum() == 0
    assert set(table[pb.TIME].dt.strftime("%Y-%m-%d %H:%M:%S")) <= set(frame["date"])
    assert pd.api.types.is_datetime64_any_dtype(table[pb.TIME])
    assert all(pd.api.types.is_float_dtype(table[c]) for c in columns)


def test_a_table_with_unreadable_timestamps_is_not_eligible_and_says_how_many(
    tmp_path, monkeypatch
):
    import injection as inj

    frame = _raw_frame()
    frame.loc[[3, 4, 9], "date"] = "not a time"
    _pool(tmp_path, monkeypatch, frame)
    with pytest.raises(inj.NotEligible, match=r"^3 timestamps could not be read$"):
        pb.load_table(9001)


def test_a_table_needs_at_least_four_continuous_columns_after_the_trend_is_dropped(
    tmp_path, monkeypatch
):
    import injection as inj

    four = _raw_frame().drop(columns="f5")
    _pool(tmp_path, monkeypatch, four)
    table, info = pb.load_table(9001)
    assert len(info["columns"]) == 4
    three = _raw_frame().drop(columns=["f4", "f5"])
    _pool(tmp_path / "again", monkeypatch, three)
    with pytest.raises(inj.NotEligible, match=r"^only 3 continuous columns$"):
        pb.load_table(9001)


def test_a_table_needs_the_minimum_number_of_rows_after_cleaning(tmp_path, monkeypatch):
    import injection as inj

    frame = _raw_frame()
    frame.loc[0, "f1"] = np.nan
    _pool(tmp_path, monkeypatch, frame, min_rows=59)
    assert len(pb.load_table(9001)[0]) == 59
    _pool(tmp_path / "again", monkeypatch, frame, min_rows=60)
    with pytest.raises(inj.NotEligible, match=r"^only 59 rows after cleaning$"):
        pb.load_table(9001)


def test_a_date_and_a_time_column_are_read_together_by_the_registered_format(tmp_path, monkeypatch):
    frame = _raw_frame()
    frame["day"] = frame["date"].str[:10]
    frame["clock"] = frame["date"].str[11:]
    frame = frame.drop(columns="date")
    _pool(
        tmp_path,
        monkeypatch,
        frame,
        spec={"date": "day", "time": "clock", "format": "%Y-%m-%d %H:%M:%S"},
    )
    table, _ = pb.load_table(9001)
    assert table[pb.TIME].iloc[0] == pd.Timestamp("2020-01-01 00:00:00")
    assert "day" not in table.columns and "clock" not in table.columns


def test_a_run_of_one_table_runs_both_reference_arms_with_the_same_seeds_and_detectors(
    monkeypatch,
):
    table = _table(240)
    calls = []

    def fake_run(t, seeds=pb.SEEDS, contaminated=False, learned=pb.LEARNED):
        calls.append((t, seeds, contaminated, learned))
        return {"arm": "dirty" if contaminated else "clean"}

    monkeypatch.setattr(pb, "load_table", lambda uci_id: (table, {"name": "T", "rows": 240}))
    monkeypatch.setattr(pb, "run_source", fake_run)
    out = pb.run_one(7, seeds=(1, 2), learned=("knn",))
    assert out == {
        "id": "uci:7",
        "name": "T",
        "rows": 240,
        "arms": {
            "clean_reference": {"arm": "clean"},
            "contaminated_reference": {"arm": "dirty"},
        },
    }
    assert [c[1:] for c in calls] == [((1, 2), False, ("knn",)), ((1, 2), True, ("knn",))]
    assert all(c[0] is table for c in calls)
    calls.clear()
    pb.run_one(7)
    assert [c[1:] for c in calls] == [(pb.SEEDS, False, pb.LEARNED), (pb.SEEDS, True, pb.LEARNED)]


def test_the_parser_requires_an_output_directory_and_reads_the_only_list_as_integers():
    parser = pb.build_parser()
    assert parser.description == pb.__doc__
    args = parser.parse_args(["--output", "out"])
    assert args.output == Path("out") and isinstance(args.output, Path)
    assert args.only is None and args.compact is False
    custom = parser.parse_args(["--output", "o", "--only", "247", "275", "--compact"])
    assert custom.only == [247, 275] and custom.compact is True
    assert parser.parse_args(["--output", "o", "--only"]).only == []
    with pytest.raises(SystemExit):
        parser.parse_args([])
    assert "learned detectors on the compact profile" in parser.format_help()


@pytest.fixture
def cli(monkeypatch):
    import chrono_injected as ci
    import injection as inj

    seen = []

    def fake_run_one(uci_id, learned):
        seen.append((uci_id, learned))
        if uci_id == 2:
            raise inj.NotEligible("too small")
        return {"id": f"uci:{uci_id}", "b": 1, "a": [uci_id]}

    monkeypatch.setattr(ci, "TIME_SPECS", {1: {}, 2: {}, 3: {}})
    monkeypatch.setattr(pb, "run_one", fake_run_one)
    return seen


def test_main_writes_one_result_per_eligible_table_and_a_list_of_the_skipped_ones(
    cli, tmp_path, capsys
):
    out = tmp_path / "deep" / "out"
    assert pb.main(["--output", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["skipped_all.json", "uci_1.json", "uci_3.json"]
    assert (out / "uci_1.json").read_text() == '{"a": [1], "b": 1, "id": "uci:1"}\n'
    assert (out / "skipped_all.json").read_text() == '{"uci:2": "too small"}\n'
    assert capsys.readouterr().out == "1\n3\n"
    assert cli == [(1, pb.LEARNED), (2, pb.LEARNED), (3, pb.LEARNED)]
    pb.main(["--output", str(out)])  # an existing directory is fine


def test_main_can_restrict_the_tables_and_switch_to_the_compact_profile(cli, tmp_path, capsys):
    out = tmp_path / "out"
    assert pb.main(["--output", str(out), "--only", "1", "3", "--compact"]) == 0
    assert cli == [(1, pb.COMPACT), (3, pb.COMPACT)]
    assert (out / "skipped_1_3.json").read_text() == "{}\n"
    assert not (out / "uci_2.json").exists()
    assert capsys.readouterr().out == "1\n3\n"
    assert pb.main(["--output", str(out), "--only", "2"]) == 0
    assert (out / "skipped_2.json").read_text() == '{"uci:2": "too small"}\n'
