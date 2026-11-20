"""Naturally labelled chronological study: labels, time order, causal features, eligibility."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natural_temporal as nt  # noqa: E402


def _nab_root(tmp_path, values, stamps, windows, family="realTraffic", name="s"):
    folder = tmp_path / "nab" / "data" / family
    folder.mkdir(parents=True)
    pd.DataFrame({"timestamp": stamps, "value": values}).to_csv(folder / f"{name}.csv", index=False)
    labels = tmp_path / "nab" / "labels"
    labels.mkdir(parents=True)
    (labels / "combined_windows.json").write_text(json.dumps({f"{family}/{name}.csv": windows}))
    return {
        "id": f"nab/{family}/{name}",
        "source": "nab",
        "group": "nab_traffic",
        "path": f"nab/data/{family}/{name}.csv",
    }


def test_window_labels_include_both_ends_and_nothing_outside():
    times = pd.Series(pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC"))
    y = nt.window_labels(times, [["2020-01-01 02:00:00", "2020-01-01 04:00:00"]])
    assert y.tolist() == [0, 0, 1, 1, 1, 0, 0, 0, 0, 0]


def test_causal_features_never_read_the_current_or_a_future_value_in_the_spread():
    values = pd.Series(np.r_[np.zeros(30), 100.0, np.zeros(10)])
    f = nt.causal_features(values)
    # the spike is not in the spread of its own row, and enters the spread of the next rows only
    assert f["spread"].iloc[30] == 0.0 and f["spread"].iloc[31] > 0.0
    assert f["deviation"].iloc[30] == 100.0 and f["diff"].iloc[30] == 100.0


def test_unsorted_series_is_sorted_by_time_with_labels_and_features_following(tmp_path):
    stamps = pd.date_range("2020-01-01", periods=60, freq="h").astype(str).tolist()
    values = np.arange(60.0)
    order = np.r_[np.arange(30, 60), np.arange(30)]  # second half first
    spec = _nab_root(
        tmp_path,
        values[order],
        np.array(stamps)[order],
        [[stamps[40], stamps[45]]],
    )
    loaded = nt.load_series(spec, tmp_path)
    assert loaded["info"]["file_in_time_order"] is False
    assert loaded["times"].is_monotonic_increasing
    # the first 24 rows are dropped, the rest are in time order with matching values and labels
    assert loaded["x"]["value"].tolist() == list(range(24, 60))
    assert loaded["y"].tolist() == [1 if 40 <= v <= 45 else 0 for v in range(24, 60)]
    assert loaded["info"]["rows_dropped"] == 24


def test_skab_columns_other_than_sensors_never_reach_the_detectors(tmp_path):
    folder = tmp_path / "skab" / "data" / "other"
    folder.mkdir(parents=True)
    pd.DataFrame(
        {
            "datetime": pd.date_range("2020-03-09", periods=5, freq="s").astype(str),
            "a": [1.0, 2, 3, 4, 5],
            "b": [1.0, 1, 1, 1, 1],
            "anomaly": [0.0, 0, 1, 1, 0],
            "changepoint": [0.0, 0, 1, 0, 0],
        }
    ).to_csv(folder / "1.csv", sep=";", index=False)
    spec = {
        "id": "skab/other/1",
        "source": "skab",
        "group": "skab",
        "path": "skab/data/other/1.csv",
    }
    loaded = nt.load_series(spec, tmp_path)
    assert list(loaded["x"].columns) == ["a"]  # constant column and truth columns are gone
    assert loaded["y"].tolist() == [0, 0, 1, 1, 0]


def test_a_series_needs_anomalous_and_normal_rows_in_the_test_partition():
    times = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="h", tz="UTC"))
    y = np.zeros(1000, dtype=int)
    y[850:] = 1  # the whole test partition is anomalous
    ok, reason = nt.eligible(y, times)
    assert not ok and "normal rows" in reason
    y[:] = 0
    y[850:880] = 1
    assert nt.eligible(y, times) == (True, "")
    y[850:880] = 0
    y[850:860] = 1
    ok, reason = nt.eligible(y, times)
    assert not ok and "anomalies" in reason


def test_source_groups_follow_the_protocol(tmp_path):
    for sub, name in (("valve1", "0"), ("other", "3")):
        folder = tmp_path / "skab" / "data" / sub
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.csv").write_text("x")
    for family, name in (("realKnownCause", "nyc_taxi"), ("realTweets", "Twitter_volume_KO")):
        folder = tmp_path / "nab" / "data" / family
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.csv").write_text("x")
    groups = {s["id"]: s["group"] for s in nt.series_files(tmp_path)}
    assert groups == {
        "skab/valve1/0": "skab",
        "skab/other/3": "skab",
        "nab/realTweets/Twitter_volume_KO": "nab_tweets",
        "nab/realKnownCause/nyc_taxi": "nab_taxi",
    }


def test_a_changed_file_is_reported_by_the_manifest_check(tmp_path):
    (tmp_path / "a.csv").write_text("1")
    (tmp_path / "b.csv").write_text("2")
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                "files": {
                    "a.csv": nt.digest(tmp_path / "a.csv"),
                    "b.csv": nt.digest(tmp_path / "b.csv"),
                }
            }
        )
    )
    assert nt.check_manifest(tmp_path, manifest) == []
    (tmp_path / "b.csv").write_text("changed")
    assert nt.check_manifest(tmp_path, manifest) == ["b.csv"]
    (tmp_path / "a.csv").unlink()
    assert nt.check_manifest(tmp_path, manifest) == ["a.csv", "b.csv"]


def test_run_series_reports_the_reason_when_a_series_is_not_evaluated(tmp_path):
    stamps = pd.date_range("2020-01-01", periods=300, freq="h").astype(str).tolist()
    spec = _nab_root(tmp_path, np.random.default_rng(0).normal(size=300), stamps, [])
    result = nt.run_series(spec, tmp_path)
    assert "anomalies in the test partition" in result["excluded"]
    assert result["group"] == "nab_traffic" and result["rows"] == 276


def test_an_evaluated_series_carries_both_arms_and_a_clean_fit_period_does_not_break_it(tmp_path):
    rng = np.random.default_rng(1)
    n = 700
    values = rng.normal(0, 1, n)
    stamps = pd.date_range("2020-01-01", periods=n, freq="h").astype(str).tolist()
    window = [stamps[600], stamps[660]]  # anomalies only in the last 15 %
    values[600:661] += 8
    spec = _nab_root(tmp_path, values, stamps, [window])
    result = nt.run_series(spec, tmp_path)
    assert result["partitions"]["train"]["positives"] == 0
    assert "isolation_forest" in result["chronological"]
    assert result["chronological"]["isolation_forest"]["pr_auc"] > 0.5
    assert len(result["stratified"]) == len(result["chronological"])
    assert 0.0 <= result["chronological"]["zscore"]["policies"]["P0"]["recall"] <= 1.0
    pytest.approx(result["partitions"]["test"]["prevalence"], abs=0.5)
