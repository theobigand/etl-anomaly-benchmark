"""Chronological study on the pool datasets that carry a time (pool_extension.md, study 5)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_chrono as pc  # noqa: E402


def test_a_date_and_a_clock_column_are_joined_and_read_as_utc_timestamps():
    frame = pd.DataFrame({"Date": ["2017/12/22", "2017/12/23"], "Time": ["10:49:41", "09:00:09"]})
    times = pc.read_times(frame, 864)
    assert times.dt.tz is not None and times.iloc[0] < times.iloc[1]
    assert times.iloc[0] == pd.Timestamp("2017-12-22 10:49:41", tz="UTC")


def test_a_month_alone_is_ordered_by_month_and_keeps_the_file_order_inside_it():
    frame = pd.DataFrame({"Month": ["Mar", "Feb", "Mar", "Feb"]})
    times = pc.read_times(frame, 468)
    order = np.argsort(times.to_numpy(), kind="stable")
    assert order.tolist() == [1, 3, 0, 2]  # the two Feb rows first, each group in file order


def test_features_keep_numbers_encode_small_categories_and_drop_constant_or_wide_columns():
    frame = pd.DataFrame(
        {
            "n": np.arange(30.0),
            "c": ["a", "b", "c"] * 10,
            "const": 1.0,
            "wide": [f"id{i}" for i in range(30)],
        }
    )
    out = pc.to_features(frame)
    assert set(out.columns) == {"n", "c_a", "c_b", "c_c"}


def test_a_dataset_with_too_few_test_anomalies_is_excluded_with_its_reason():
    y = np.zeros(1000, dtype=int)
    y[:50] = 1  # all anomalies are in the oldest rows
    times = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="h", tz="UTC"))
    ok, reason = pc.eligible(y, times)
    assert not ok and "0 anomalies in the test partition" in reason
    assert pc.run_dataset(pd.DataFrame({"a": np.arange(1000.0)}), y, times) == {"excluded": reason}


def test_the_neighbour_detectors_are_skipped_on_a_large_train_set_and_listed(monkeypatch):
    monkeypatch.setattr(pc.nm, "LOF_MAX_TRAIN", 100)
    monkeypatch.setattr(pc.nm, "KNN_MAX_TRAIN", 100)
    kept, skipped = pc.methods_for(500, ["zscore", "lof", "knn", "ocsvm"])
    assert kept == ["zscore", "ocsvm"] and skipped == ["lof", "knn"]


def test_a_small_labelled_stream_runs_through_the_chronological_study():
    rng = np.random.default_rng(0)
    n = 1200
    x = pd.DataFrame(rng.normal(size=(n, 3)), columns=list("abc"))
    y = np.zeros(n, dtype=int)
    y[rng.choice(n, 360, replace=False)] = 1
    x.loc[y == 1, "a"] += 4
    times = pd.Series(pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"))
    result = pc.run_dataset(x, y, times, methods=["zscore", "hbos"])
    assert set(result["chronological"]) == {"zscore", "hbos"} and result["skipped"] == []
    assert result["chronological"]["hbos"]["pr_auc"] > 0.3
    assert {"P0", "P1", "P2"} == set(result["chronological"]["hbos"]["policies"])


def test_the_loader_aligns_times_with_the_rows_kept_by_the_labelling_rule(tmp_path):
    n = 400
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2015-02-04", periods=n, freq="min").astype(str),
            "v": rng.normal(size=n),
            "w": rng.normal(size=n),
            "Occupancy": np.r_[np.ones(60), np.zeros(n - 60)],
        }
    )
    path = tmp_path / "357.csv"
    frame.to_csv(path, index=False)
    meta = {"tasks": ["Classification"], "target_col": ["Occupancy"], "variables": []}
    x, y, times, dropped = pc.load_pool_dataset(meta, path, 357)
    assert dropped == 0
    assert len(x) == len(y) == len(times) and set(x.columns) == {"v", "w"}
    # 60 of 400 rows is 15%: the pool rule downsamples the anomaly class to 10% of the kept rows
    assert y.sum() == round(340 * 0.10 / 0.90)
    anomalies = times[y == 1]
    assert (anomalies < pd.Timestamp("2015-02-04 01:00", tz="UTC")).all()  # the first 60 minutes
    assert (times[y == 0] >= pd.Timestamp("2015-02-04 01:00", tz="UTC")).all()


def test_a_stray_header_line_in_the_time_column_is_dropped_and_counted(tmp_path):
    n = 300
    rng = np.random.default_rng(2)
    dates = list(pd.date_range("2015-02-04", periods=n, freq="min").astype(str))
    dates[100] = "Temperature"  # a header line left by a concatenation of files
    frame = pd.DataFrame(
        {
            "date": dates,
            "v": rng.normal(size=n),
            "w": rng.normal(size=n),
            "Occupancy": np.r_[np.ones(20), np.zeros(n - 20)],
        }
    )
    path = tmp_path / "357.csv"
    frame.to_csv(path, index=False)
    meta = {"tasks": ["Classification"], "target_col": ["Occupancy"], "variables": []}
    x, y, times, dropped = pc.load_pool_dataset(meta, path, 357)
    assert dropped == 1 and len(x) == len(y) == len(times)
    assert times.notna().all() and pd.Timestamp("2015-02-04 01:40", tz="UTC") not in set(times)
