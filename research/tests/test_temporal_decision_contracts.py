"""Exact thresholds, metrics, subsampling, intervals, argument routing and loaders of the study."""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import temporal_decision as td  # noqa: E402


def test_the_protocol_constants_are_the_written_ones():
    assert td.BLOCKS == 20 and td.BOOT_BLOCKS == 50 and td.RESAMPLES == 1000
    assert td.BOOT_SEED == 42 and td.POLICIES == ("P0", "P1", "P2")
    assert td.METHODS == ["zscore", "iqr", "great_expectations", "isolation_forest"]


def test_the_rolling_threshold_is_the_quantile_of_at_most_two_block_sizes_of_earlier_scores():
    s_val = np.array([1.0, 2.0, 3.0, 4.0])
    s_test = np.arange(10.0, 18.0)
    thr = td.thresholds(np.arange(5.0), s_val, s_test, pi=0.25, blocks=4)
    stream = np.concatenate([s_val, s_test])
    expected = []
    for start in (0, 2, 4, 6):  # blocks of two rows
        end = 4 + start
        history = stream[max(0, end - 4) : end]
        expected += [float(np.quantile(history, 0.75))] * 2
    assert thr["P2"].tolist() == expected
    assert thr["P0"].tolist() == [float(np.quantile(np.arange(5.0), 0.75))] * 8
    assert thr["P1"].tolist() == [float(np.quantile(s_val, 0.75))] * 8
    assert set(thr) == {"P0", "P1", "P2"}


def test_more_blocks_than_test_rows_leave_the_empty_blocks_without_a_threshold():
    thr = td.thresholds(np.arange(5.0), np.arange(5.0), np.arange(3.0), pi=0.5, blocks=6)
    assert len(thr["P2"]) == 3 and not np.isnan(thr["P2"]).any()


def test_flags_need_a_score_strictly_above_the_threshold_and_every_rate_is_exact():
    y = [1, 1, 1, 0, 0, 0, 0, 0]
    scores = [3.0, 2.0, 1.0, 2.0, 1.0, 0.5, 0.0, 0.0]
    out = td.decision_metrics(y, scores, np.full(8, 1.0))
    assert out == {
        "precision": 2 / 3,
        "recall": 2 / 3,
        "f1": 2 * (2 / 3) * (2 / 3) / (4 / 3),
        "fpr": 1 / 5,
        "flagged_share": 3 / 8,
    }
    assert set(out) == {"precision", "recall", "f1", "fpr", "flagged_share"}


def test_a_detector_that_flags_nothing_or_sees_no_positive_has_zero_not_an_error():
    none = td.decision_metrics([1, 0], [0.0, 0.0], np.ones(2))
    assert none == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "fpr": 0.0, "flagged_share": 0.0}
    no_negative = td.decision_metrics([1, 1], [2.0, 0.0], np.ones(2))
    assert no_negative["fpr"] == 0.0 and no_negative["recall"] == 0.5
    no_positive = td.decision_metrics([0, 0], [2.0, 0.0], np.ones(2))
    assert no_positive["recall"] == 0.0 and no_positive["precision"] == 0.0


def test_matching_a_lower_prevalence_keeps_all_negatives_and_a_rounded_number_of_positives():
    y = np.array([1] * 100 + [0] * 900)
    kept = td.match_prevalence(y, 0.02, np.random.default_rng(0))
    assert kept.tolist() == sorted(kept.tolist())
    assert int((y[kept] == 0).sum()) == 900 and int((y[kept] == 1).sum()) == 18
    higher = td.match_prevalence(y, 0.5, np.random.default_rng(0))
    assert int((y[higher] == 1).sum()) == 100 and int((y[higher] == 0).sum()) == 100


def test_matching_never_keeps_fewer_than_one_row_or_more_than_exist():
    y = np.array([1] + [0] * 99)
    tiny = td.match_prevalence(y, 0.001, np.random.default_rng(0))
    assert int((y[tiny] == 1).sum()) == 1
    labels = np.array([1] * 3 + [0] * 7)
    scarce = td.match_prevalence(labels, 0.9, np.random.default_rng(0))
    assert int((labels[scarce] == 1).sum()) == 3 and int((labels[scarce] == 0).sum()) == 1
    y2 = np.array([1] * 3 + [0] * 97)
    assert int((y2[td.match_prevalence(y2, 0.03, np.random.default_rng(1))] == 1).sum()) == 3


def test_scores_come_from_a_detector_built_for_the_prevalence_and_fitted_on_the_capped_train(
    monkeypatch,
):
    calls = {}

    class Detector:
        def fit(self, frame):
            calls["fit"] = frame

        def score(self, frame):
            return pd.Series(np.arange(len(frame), dtype=int))

    def build(method, contamination, seed):
        calls["build"] = (method, contamination, seed)
        return Detector()

    monkeypatch.setattr(td, "build", build)
    monkeypatch.setattr(
        td, "capped", lambda frame, method, seed: calls.update(cap=(method, seed)) or frame.head(2)
    )
    train, other = pd.DataFrame({"a": range(5)}), pd.DataFrame({"a": range(3)})
    out = td._scores("zscore", 0.0, train, [train, other], seed=7)
    assert calls["build"] == ("zscore", td.clip_contamination(0.0), 7)
    assert calls["cap"] == ("zscore", 7) and len(calls["fit"]) == 2
    assert [o.dtype for o in out] == [np.float64, np.float64] and [len(o) for o in out] == [5, 3]
    td._scores("zscore", 0.1, train, [train])
    assert calls["build"][2] == 42


def test_the_block_interval_resamples_blocks_and_keeps_only_mixed_label_draws(monkeypatch):
    monkeypatch.setattr(td, "BOOT_BLOCKS", 4)
    monkeypatch.setattr(td, "RESAMPLES", 25)
    y = np.array([0, 0, 1, 1, 0, 0, 0, 1])
    scores = np.array([0.1, 0.2, 0.9, 0.8, 0.3, 0.2, 0.1, 0.7])
    out = td._block_ci(y, scores)
    members = [np.arange(0, 2), np.arange(2, 4), np.arange(4, 6), np.arange(6, 8)]
    rng = np.random.default_rng(td.BOOT_SEED)
    values = []
    for _ in range(25):
        index = np.concatenate([members[k] for k in rng.integers(0, 4, 4)])
        if y[index].min() != y[index].max():
            values.append(average_precision_score(y[index], scores[index]))
    low, high = np.percentile(values, [2.5, 97.5])
    assert out == {"ci_low": float(low), "ci_high": float(high), "resamples_used": len(values)}


def test_the_description_of_a_partition_is_its_size_positives_and_prevalence():
    assert td._describe(np.array([1, 0, 0, 1])) == {"rows": 4, "positives": 2, "prevalence": 0.5}


def _stub_scores(monkeypatch, calls):
    def scores(method, pi, train, parts, seed=42):
        calls.append((method, pi, len(train), [len(p) for p in parts], seed))
        return [p["a"].to_numpy(dtype=float) for p in parts]

    monkeypatch.setattr(td, "_scores", scores)
    monkeypatch.setattr(
        td, "_block_ci", lambda y, s: {"ci_low": 0.1, "ci_high": 0.9, "resamples_used": 3}
    )


def _frame(n=200):
    rng = np.random.default_rng(3)
    y = (rng.random(n) < 0.2).astype(int)
    x = pd.DataFrame({"a": rng.normal(size=n) + 2 * y})
    times = pd.Series(pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"))
    return x, y, times


def test_the_chronological_arm_splits_seventy_fifteen_fifteen_in_time_order(monkeypatch):
    calls = []
    _stub_scores(monkeypatch, calls)
    x, y, times = _frame()
    order = np.random.default_rng(0).permutation(len(y))
    out = td.run_frame(
        x.iloc[order].reset_index(drop=True), y[order], times.iloc[order], ["zscore"], seeds=(1,)
    )
    assert [out["partitions"][k]["rows"] for k in ("train", "validation", "test")] == [140, 30, 30]
    assert out["partitions"]["train"]["positives"] == int(y[:140].sum())
    method, pi, rows, parts, seed = calls[0]
    assert (method, rows, parts, seed) == ("zscore", 140, [140, 30, 30], 42)
    assert pi == float(y[:140].mean())
    row = out["chronological"]["zscore"]
    assert set(row) == {"pr_auc", "roc_auc", "pr_ci", "policies"}
    assert row["pr_ci"] == {
        "estimate": row["pr_auc"],
        "ci_low": 0.1,
        "ci_high": 0.9,
        "resamples_used": 3,
    }
    assert set(row["policies"]["P0"]) == {
        "precision",
        "recall",
        "f1",
        "fpr",
        "flagged_share",
        "share_error",
    }


def test_share_error_is_the_absolute_log_ratio_of_flagged_share_to_the_training_prevalence(
    monkeypatch,
):
    calls = []
    _stub_scores(monkeypatch, calls)
    x, y, times = _frame()
    out = td.run_frame(x, y, times, ["zscore"], seeds=(1,))
    pi = calls[0][1]
    for policy in out["chronological"]["zscore"]["policies"].values():
        expected = abs(math.log(max(policy["flagged_share"], 1e-6) / pi))
        assert policy["share_error"] == pytest.approx(expected)


def test_each_seed_adds_a_stratified_arm_trained_on_seventy_percent_and_a_matched_control(
    monkeypatch,
):
    calls = []
    _stub_scores(monkeypatch, calls)
    x, y, times = _frame()
    out = td.run_frame(x, y, times, ["zscore"], seeds=(1, 2))
    stratified_calls = calls[1:]
    assert len(stratified_calls) == 2
    assert all(c[2] == 140 and c[3] == [30] for c in stratified_calls)
    row = out["stratified"]["zscore"]
    assert set(row) == {
        "pr_auc", "roc_auc", "pr_auc_matched", "pr_auc_std", "roc_auc_std", "pr_auc_matched_std",
    }  # fmt: skip
    assert row["pr_auc_std"] >= 0.0
    single = td.run_frame(x, y, times, ["zscore"], seeds=(1,))
    assert single["stratified"]["zscore"]["pr_auc_std"] == 0.0
    assert single["stratified"]["zscore"]["pr_auc_matched_std"] == 0.0


def _result(strat, chrono, matched, p0=0.5, p1=0.5, p2=0.5, errors=(0.3, 0.2, 0.1)):
    def policy(f1, error):
        return {"f1": f1, "share_error": error}

    return {
        "chronological": {
            "m1": {
                "pr_auc": chrono,
                "policies": {
                    "P0": policy(p0, errors[0]),
                    "P1": policy(p1, errors[1]),
                    "P2": policy(p2, errors[2]),
                },
            },
            "m2": {
                "pr_auc": chrono + 0.1,
                "policies": {
                    "P0": policy(p0, errors[0]),
                    "P1": policy(p1, errors[1]),
                    "P2": policy(p2, errors[2]),
                },
            },
        },
        "stratified": {
            "m1": {"pr_auc": strat, "pr_auc_matched": matched},
            "m2": {"pr_auc": strat + 0.1, "pr_auc_matched": matched + 0.1},
        },
    }


def test_the_four_hypotheses_apply_their_written_comparisons():
    ok = {"d": _result(0.8, 0.4, 0.5)}
    out = td.hypotheses(ok)
    assert out["H1"]["spearman"] == {"d": pytest.approx(1.0)} and out["H1"]["supported"] is True
    assert out["H2"] == {
        "supported": True,
        "by_dataset": {"d": {"median_share_error": {"P0": 0.3, "P1": 0.2, "P2": 0.1}, "ok": True}},
    }
    assert out["H3"] == {"supported": True, "p2_at_least_p0": 2, "pairs": 2}
    assert out["H4"]["by_dataset"]["d"] == {
        "gap_stratified": pytest.approx(0.4), "gap_matched": pytest.approx(0.1), "ok": True,
    }  # fmt: skip
    tied = {"d": _result(0.8, 0.4, 0.5, errors=(0.2, 0.2, 0.1))}
    assert td.hypotheses(tied)["H2"]["supported"] is False
    loses = {"d": _result(0.8, 0.4, 0.5, p0=0.6, p2=0.5)}
    assert td.hypotheses(loses)["H3"] == {"supported": False, "p2_at_least_p0": 0, "pairs": 2}
    half = {"a": _result(0.8, 0.4, 0.5), "b": _result(0.8, 0.4, 0.5, p0=0.6, p2=0.5)}
    assert td.hypotheses(half)["H3"] == {"supported": True, "p2_at_least_p0": 2, "pairs": 4}


def test_h4_accepts_a_matched_gap_of_exactly_half_the_stratified_gap():
    exact = {"d": _result(0.9, 0.5, 0.7)}
    assert td.hypotheses(exact)["H4"]["by_dataset"]["d"]["ok"] is True
    over = {"d": _result(0.9, 0.5, 0.8)}
    assert td.hypotheses(over)["H4"]["by_dataset"]["d"]["ok"] is False


def test_credit_card_orders_by_time_and_returns_features_labels_and_times(monkeypatch):
    import temporal_pilot as tp

    frame = pd.DataFrame(
        {
            tp.TIME_UTC: pd.to_datetime(["2020-01-03", "2020-01-01", "2020-01-02"], utc=True),
            "is_anomaly": [1, 0, 0],
            "v": [3.0, 1.0, 2.0],
        }  # fmt: skip
    )
    monkeypatch.setattr(tp, "load", lambda spec: frame)
    monkeypatch.setattr(tp, "features", lambda spec, f: f[["v"]])
    x, y, times = td.credit_card()
    assert x["v"].tolist() == [1.0, 2.0, 3.0] and y.tolist() == [0, 0, 1]
    assert times.tolist() == sorted(frame[tp.TIME_UTC].tolist()) and times.index.tolist() == [
        0,
        1,
        2,
    ]
    assert x.index.tolist() == [0, 1, 2]


def test_bank_marketing_dates_rows_by_month_with_year_rollover_and_encodes_the_categories(tmp_path):
    table = pd.DataFrame(
        {
            "month": ["nov", "nov", "dec", "jan", "jan", "feb"],
            "job": ["a", None, "b", "a", "b", "a"],
            "age": [30, 40, 50, 60, 70, 80],
            "y": ["yes", "no", "no", "yes", "no", "no"],
        }
    )
    path = tmp_path / "222.csv"
    table.to_csv(path, index=False)
    x, y, times = td.bank_marketing(path)
    assert y.tolist() == [1, 0, 0, 1, 0, 0]
    assert [t.strftime("%Y-%m-%d %H:%M") for t in times] == [
        "2008-11-01 00:00", "2008-11-01 00:01", "2008-12-01 00:00",
        "2009-01-01 00:00", "2009-01-01 00:01", "2009-02-01 00:00",
    ]  # fmt: skip
    assert str(times.dt.tz) == "UTC"
    assert "y" not in x and "month" not in x and "age" in x
    assert {"job_a", "job_b", "job_nan"} <= set(x.columns) and x["job_nan"].tolist()[1] == 1.0
    assert x["job_a"].dtype == np.float64


def test_the_command_runs_both_datasets_writes_the_results_and_reports_each_name(
    tmp_path, monkeypatch, capsys
):
    data = (pd.DataFrame({"a": [1.0]}), np.array([0]), pd.Series([pd.Timestamp("2020", tz="UTC")]))
    seen = {}
    monkeypatch.setattr(td, "credit_card", lambda: data)
    monkeypatch.setattr(td, "bank_marketing", lambda path: seen.update(bank=path) or data)
    monkeypatch.setattr(td, "run_frame", lambda x, y, t: {"ok": 1})
    monkeypatch.setattr(td, "hypotheses", lambda results: {"H": list(results)})
    out = tmp_path / "new" / "dir"
    assert td.main(["--output", str(out)]) == 0
    assert capsys.readouterr().out == "credit_card\nbank_marketing\n"
    assert seen["bank"] == td.ROOT / "data" / "pool" / "222.csv"
    text = (out / "temporal_decision_results.json").read_text()
    document = json.loads(text)
    assert text == json.dumps(document, indent=1, sort_keys=True) + "\n"
    assert document == {
        "datasets": {"credit_card": {"ok": 1}, "bank_marketing": {"ok": 1}},
        "hypotheses": {"H": ["credit_card", "bank_marketing"]},
    }
    td.main(["--output", str(out), "--bank", str(tmp_path / "b.csv")])
    assert seen["bank"] == tmp_path / "b.csv"
    with pytest.raises(SystemExit) as stop:
        td.main([])
    assert stop.value.code == 2
