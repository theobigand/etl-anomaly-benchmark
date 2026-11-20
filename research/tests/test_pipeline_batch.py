"""Batch-level pipeline faults: batches, operators with ground truth, profiles, constraints, metrics."""

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
    bad = pb.apply_fault(clean, "silent_corruption", 2, np.random.default_rng(3), history=batches[:60], sd=ref.sd)
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
    partial = pb.apply_fault(batches[50], "partial_load", 2, np.random.default_rng(0), history=batches[:50], sd=ref.sd)
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
    assert not none.any() and all(a.equals(batches[i]) for a, i in zip(clean_stream, test, strict=True))


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
