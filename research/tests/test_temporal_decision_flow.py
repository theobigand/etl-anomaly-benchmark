"""Subsampling, bootstrap bounds, split arguments and the two real loaders of the decision study."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import temporal_decision as td  # noqa: E402


def test_a_precision_and_a_false_alarm_rate_are_zero_only_without_any_flag_or_negative():
    out = td.decision_metrics(np.array([1, 0, 0, 1]), np.array([5.0, 5.0, 0.0, 0.0]), 1.0)
    assert out["precision"] == 0.5 and out["recall"] == 0.5 and out["fpr"] == 0.5
    assert out["flagged_share"] == 0.5 and out["f1"] == 0.5
    nothing = td.decision_metrics(np.array([1, 0]), np.array([0.0, 0.0]), 1.0)
    assert nothing["precision"] == 0.0 and nothing["f1"] == 0.0
    no_negative = td.decision_metrics(np.array([1, 1]), np.array([5.0, 5.0]), 1.0)
    assert no_negative["fpr"] == 0.0


def _y(pos, neg):
    return np.array([1] * pos + [0] * neg)


def test_an_over_represented_positive_class_is_thinned_to_the_target_share_of_the_negatives():
    y = _y(30, 70)
    keep = td.match_prevalence(y, 0.2, np.random.default_rng(1))
    assert (y[keep] == 1).sum() == 18 and (y[keep] == 0).sum() == 70
    assert keep.tolist() == sorted(set(keep.tolist()))


def test_an_under_represented_positive_class_thins_the_negatives_instead():
    y = _y(5, 95)
    keep = td.match_prevalence(y, 0.2, np.random.default_rng(1))
    assert (y[keep] == 1).sum() == 5 and (y[keep] == 0).sum() == 20
    assert len(set(keep.tolist())) == len(keep)


@pytest.mark.parametrize(("pos", "neg", "target"), [(2, 98, 0.001), (98, 2, 0.999)])
def test_at_least_one_row_of_the_thinned_class_is_kept(pos, neg, target):
    y = _y(pos, neg)
    keep = td.match_prevalence(y, target, np.random.default_rng(3))
    thinned = (y[keep] == 1).sum() if pos / len(y) > target else (y[keep] == 0).sum()
    assert thinned == 1


def test_a_class_is_never_drawn_with_replacement():
    for pos, neg, target in ((6, 94, 0.05), (50, 50, 0.9)):
        y = _y(pos, neg)
        for seed in range(5):
            keep = td.match_prevalence(y, target, np.random.default_rng(seed))
            assert len(set(keep.tolist())) == len(keep)


def test_the_block_interval_is_the_two_and_a_half_to_ninety_seven_and_a_half_percentiles(
    monkeypatch,
):
    monkeypatch.setattr(td, "RESAMPLES", 400)
    monkeypatch.setattr(td, "BOOT_BLOCKS", 10)
    rng = np.random.default_rng(5)
    y = (rng.random(100) < 0.3).astype(int)
    scores = rng.random(100) + 0.4 * y
    out = td._block_ci(y, scores)
    members = [np.arange(i * 10, (i + 1) * 10) for i in range(10)]
    draw = np.random.default_rng(td.BOOT_SEED)
    values = []
    for _ in range(400):
        index = np.concatenate([members[k] for k in draw.integers(0, 10, 10)])
        if y[index].min() != y[index].max():
            values.append(average_precision_score(y[index], scores[index]))
    low, high = np.percentile(values, [2.5, 97.5])
    assert out["ci_low"] == pytest.approx(low) and out["ci_high"] == pytest.approx(high)
    assert out["resamples_used"] == len(values)


def _frame_for_run(n=100, seed=2):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.3).astype(int)
    x = pd.DataFrame({"a": rng.normal(size=n) + y}, index=rng.permutation(n) + 1000)
    times = pd.Series(pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"), index=x.index)
    return x, y, times


def test_the_stratified_arm_splits_seventy_fifty_with_the_labels_and_the_seed(monkeypatch):
    splits = []
    real = td.train_test_split

    def spy(array, **kwargs):
        splits.append(
            {k: v for k, v in kwargs.items() if k != "stratify"}
            | {"stratified": kwargs.get("stratify") is not None}
        )
        return real(array, **kwargs)

    monkeypatch.setattr(td, "train_test_split", spy)
    monkeypatch.setattr(
        td, "_block_ci", lambda y, s: {"ci_low": 0.0, "ci_high": 1.0, "resamples_used": 1}
    )
    x, y, times = _frame_for_run()
    td.run_frame(x, y, times, ["zscore"], seeds=(7,))
    assert splits == [
        {"train_size": 0.70, "random_state": 7, "stratified": True},
        {"train_size": 0.5, "random_state": 7, "stratified": True},
    ]


def test_each_stratified_fold_is_scored_with_its_own_prevalence_and_matched_to_the_test_share(
    monkeypatch,
):
    scored, matched = [], []
    real_scores = td._scores

    def scores(method, pi, train, parts, seed=42):
        scored.append((pi, list(train.columns), train.index.min()))
        return real_scores(method, pi, train, parts, seed)

    monkeypatch.setattr(td, "_scores", scores)
    real_match = td.match_prevalence
    monkeypatch.setattr(
        td,
        "match_prevalence",
        lambda y, target, rng: matched.append(target) or real_match(y, target, rng),
    )
    monkeypatch.setattr(
        td, "_block_ci", lambda y, s: {"ci_low": 0.0, "ci_high": 1.0, "resamples_used": 1}
    )
    x, y, times = _frame_for_run()
    td.run_frame(x, y, times, ["zscore"], seeds=(1, 2))
    order = np.argsort(times.to_numpy(), kind="stable")
    ys = y[order]
    n = len(ys)
    pi = ys[: int(n * 0.70)].mean()
    assert scored[0] == (pi, ["a"], 0)
    assert all(columns == ["a"] for _, columns, _low in scored)
    assert len(scored) == 3 and scored[1][0] != pi
    assert matched == [ys[int(n * 0.85) :].mean()] * 2


def test_the_spread_over_seeds_is_the_sample_deviation_and_zero_for_a_single_seed(monkeypatch):
    monkeypatch.setattr(
        td, "_block_ci", lambda y, s: {"ci_low": 0.0, "ci_high": 1.0, "resamples_used": 1}
    )
    x, y, times = _frame_for_run()
    two = td.run_frame(x, y, times, ["zscore"], seeds=(1, 2))["stratified"]["zscore"]
    assert two["pr_auc_std"] > 0
    one = td.run_frame(x, y, times, ["zscore"], seeds=(1,))["stratified"]["zscore"]
    assert (
        one["pr_auc_std"] == 0.0 and one["roc_auc_std"] == 0.0 and one["pr_auc_matched_std"] == 0.0
    )


def test_rows_are_ordered_by_time_and_the_old_index_is_not_kept_as_a_column(monkeypatch):
    seen = []
    real = td._scores

    def scores(method, pi, train, parts, seed=42):
        seen.append(list(train.columns))
        return real(method, pi, train, parts, seed)

    monkeypatch.setattr(td, "_scores", scores)
    monkeypatch.setattr(
        td, "_block_ci", lambda y, s: {"ci_low": 0.0, "ci_high": 1.0, "resamples_used": 1}
    )
    x, y, times = _frame_for_run()
    td.run_frame(x, y, times, ["zscore"], seeds=(1,))
    assert all(columns == ["a"] for columns in seen)


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def test_the_bank_months_become_dated_minutes_that_roll_into_the_next_year(monkeypatch, tmp_path):
    import uci_loader as ul

    months = [*MONTHS, "jan", "jan", "feb"]
    frame = pd.DataFrame(
        {
            "month": months,
            "y": ["yes", "no"] * 7 + ["yes"],
            "age": range(len(months)),
            "job": ["a", "b", None] * 5,
        }
    )
    monkeypatch.setattr(ul, "read_table", lambda path: frame)
    x, y, times = td.bank_marketing(tmp_path / "x.csv")
    assert times.dt.tz is not None and str(times.dt.tz) == "UTC"
    assert times.iloc[0] == pd.Timestamp("2008-01-01", tz="UTC")
    for i, name in enumerate(MONTHS):
        assert times.iloc[i] == pd.Timestamp(2008, i + 1, 1, tz="UTC"), name
    assert times.iloc[12] == pd.Timestamp("2009-01-01", tz="UTC")
    assert times.iloc[13] == pd.Timestamp("2009-01-01 00:01", tz="UTC")
    assert times.iloc[14] == pd.Timestamp("2009-02-01", tz="UTC")
    assert y.tolist() == [1 if v == "yes" else 0 for v in frame["y"]]
    assert "month" not in x.columns and "y" not in x.columns
    assert "age" in x.columns and {"job_a", "job_b", "job_nan"} <= set(x.columns)
    assert all(dtype is np.dtype(float) for dtype in x.drop(columns="age").dtypes)


def test_the_credit_card_rows_follow_time_and_carry_the_label_and_utc_time(monkeypatch):
    import temporal_pilot as tp

    from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS

    seen = {}
    raw = pd.DataFrame(
        {tp.TIME_UTC: pd.to_datetime(["2020-01-03", "2020-01-01", "2020-01-02"], utc=True),
         ANOMALY_COLUMN: [1, 0, 1], "v": [3.0, 1.0, 2.0]}
    )  # fmt: skip

    def load(spec):
        seen["load"] = spec
        return raw

    def features(spec, frame):
        seen["features"] = spec
        return frame[["v"]]

    monkeypatch.setattr(tp, "load", load)
    monkeypatch.setattr(tp, "features", features)
    x, y, times = td.credit_card()
    assert seen["load"] is DATASETS["credit_card"] and seen["features"] is DATASETS["credit_card"]
    assert x["v"].tolist() == [1.0, 2.0, 3.0] and x.index.equals(pd.RangeIndex(3))
    assert y.tolist() == [0, 1, 1] and times.index.equals(pd.RangeIndex(3))
    assert times.is_monotonic_increasing


def _result(strat, chrono, matched, p0=0.5, p2=0.5, errors=(0.3, 0.2, 0.1)):
    def policy(f1, error):
        return {"f1": f1, "share_error": error}

    def method(offset):
        return {
            "pr_auc": chrono + offset,
            "policies": {
                "P0": policy(p0, errors[0]),
                "P1": policy(0.5, errors[1]),
                "P2": policy(p2, errors[2]),
            },
        }

    return {
        "chronological": {"m1": method(0.0), "m2": method(0.1)},
        "stratified": {
            "m1": {"pr_auc": strat, "pr_auc_matched": matched},
            "m2": {"pr_auc": strat + 0.1, "pr_auc_matched": matched + 0.1},
        },
    }


def test_h2_needs_the_rolling_policy_strictly_below_the_validation_policy():
    tied = {"d": _result(0.75, 0.25, 0.5, errors=(0.3, 0.1, 0.1))}
    assert td.hypotheses(tied)["H2"]["supported"] is False
    strict = {"d": _result(0.75, 0.25, 0.5, errors=(0.3, 0.2, 0.1))}
    assert td.hypotheses(strict)["H2"]["supported"] is True


def test_h3_needs_the_rolling_policy_to_do_at_least_as_well_in_half_of_the_pairs():
    wins = _result(0.75, 0.25, 0.5)
    loses = _result(0.75, 0.25, 0.5, p0=0.6, p2=0.5)
    out = td.hypotheses({"a": wins, "b": loses, "c": loses})
    assert out["H3"] == {"supported": False, "p2_at_least_p0": 2, "pairs": 6}


def test_h4_accepts_exactly_half_of_the_stratified_gap_with_exact_numbers():
    exact = {"d": _result(0.75, 0.25, 0.5)}
    row = td.hypotheses(exact)["H4"]["by_dataset"]["d"]
    assert row["gap_stratified"] == 0.5 and row["gap_matched"] == 0.25 and row["ok"] is True


def test_each_stratified_fold_is_scored_with_the_prevalence_of_its_own_training_rows(monkeypatch):
    prevalences = []
    real = td._scores

    def scores(method, pi, train, parts, seed=42):
        prevalences.append(pi)
        return real(method, pi, train, parts, seed)

    monkeypatch.setattr(td, "_scores", scores)
    monkeypatch.setattr(
        td, "_block_ci", lambda y, s: {"ci_low": 0.0, "ci_high": 1.0, "resamples_used": 1}
    )
    x, y, times = _frame_for_run()
    td.run_frame(x, y, times, ["zscore"], seeds=(5,))
    ordered = y[np.argsort(times.to_numpy(), kind="stable")]
    train, _rest = td.train_test_split(
        np.arange(len(ordered)), train_size=0.70, stratify=ordered, random_state=5
    )
    assert prevalences[1] == pytest.approx(ordered[train].mean())


def test_the_spread_over_seeds_is_the_sample_deviation_of_the_per_seed_values(monkeypatch):
    monkeypatch.setattr(
        td, "_block_ci", lambda y, s: {"ci_low": 0.0, "ci_high": 1.0, "resamples_used": 1}
    )
    x, y, times = _frame_for_run()
    each = [
        td.run_frame(x, y, times, ["zscore"], seeds=(seed,))["stratified"]["zscore"]["pr_auc"]
        for seed in (1, 2)
    ]
    both = td.run_frame(x, y, times, ["zscore"], seeds=(1, 2))["stratified"]["zscore"]
    assert both["pr_auc_std"] == pytest.approx(np.std(each, ddof=1))
    assert both["pr_auc"] == pytest.approx(np.mean(each))
