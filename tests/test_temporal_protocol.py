"""A temporal result must never use future observations as its reference."""

import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.window_drift import WindowDriftMonitor, event_metrics
from etl_benchmark.split import chronological_split


def _timeline(n=120):
    rng = np.random.default_rng(8)
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=n, freq="h"),
            "value": rng.normal(0, 1, n),
            "id": np.arange(n),
        }
    )


def test_chronological_split_is_order_independent_and_never_splits_a_timestamp():
    frame = _timeline(100)
    frame.loc[68:72, "time"] = frame.loc[68, "time"]
    shuffled = frame.sample(frac=1, random_state=3)
    parts = chronological_split(shuffled, "time")
    assert set(pd.concat(parts)["id"]) == set(frame["id"])
    assert max(parts[0]["time"]) < min(parts[1]["time"])
    assert max(parts[1]["time"]) < min(parts[2]["time"])
    assert [set(p["id"]) for p in parts] == [
        set(p["id"]) for p in chronological_split(frame, "time")
    ]


@pytest.mark.parametrize("bad", ["not-a-date", None])
def test_chronological_split_rejects_bad_timestamps(bad):
    frame = _timeline(12)
    frame["time"] = frame["time"].astype(object)
    frame.loc[4, "time"] = bad
    with pytest.raises(ValueError, match="timestamp"):
        chronological_split(frame, "time")


def test_chronological_split_rejects_insufficient_distinct_times():
    frame = _timeline(12)
    frame["time"] = ["2024-01-01"] * 11 + ["2024-01-02"]
    with pytest.raises(ValueError, match="distinct"):
        chronological_split(frame, "time")


def test_window_monitor_detects_abrupt_change_without_reference_updates():
    frame = _timeline(120)
    train, val, test = chronological_split(frame, "time")
    monitor = WindowDriftMonitor("time", ["value"], window_size=5, threshold=2.0).fit(train)
    stationary = monitor.evaluate(val)
    shifted = test.copy()
    shifted["value"] += 5
    drifted = monitor.evaluate(shifted)
    assert not stationary["alert"].any()
    assert drifted["alert"].all()
    assert (drifted["score"] > stationary["score"].max()).all()
    pd.testing.assert_frame_equal(drifted, monitor.evaluate(shifted.sample(frac=1, random_state=4)))
    assert monitor.reference_end == train["time"].max().tz_localize("UTC")


def test_window_monitor_rejects_hindsight_and_bad_inputs():
    train, _, test = chronological_split(_timeline(90), "time")
    monitor = WindowDriftMonitor("time", ["value"], window_size=5).fit(train)
    with pytest.raises(ValueError, match="future"):
        monitor.evaluate(train)
    with pytest.raises(ValueError, match="timestamp"):
        monitor.evaluate(test.assign(time="broken"))
    with pytest.raises(ValueError, match="feature"):
        monitor.evaluate(test.drop(columns="value"))


def test_window_monitor_keeps_equal_timestamps_in_one_window():
    train = _timeline(20)
    future = _timeline(12)
    future["time"] += pd.Timedelta(days=10)
    future.loc[4:7, "time"] = future.loc[4, "time"]
    monitor = WindowDriftMonitor("time", ["value"], window_size=4).fit(train)
    a = monitor.evaluate(future)
    b = monitor.evaluate(future.sample(frac=1, random_state=2))
    pd.testing.assert_frame_equal(a, b)
    assert a["n_rows"].sum() == len(future)


def test_window_monitor_drops_incomplete_tail_and_handles_constant_baseline():
    train = _timeline(20)
    train["value"] = 2.0
    future = _timeline(9)
    future["time"] += pd.Timedelta(days=10)
    future["value"] = 7.0
    windows = WindowDriftMonitor("time", ["value"], window_size=5).fit(train).evaluate(future)
    assert len(windows) == 1
    assert windows.loc[0, "n_rows"] == 5
    assert windows.loc[0, "score"] == 5.0
    assert bool(windows.loc[0, "alert"])


def test_gradual_change_alerts_later_than_stationary_windows():
    train = _timeline(30)
    future = _timeline(30)
    future["time"] += pd.Timedelta(days=10)
    future["value"] = 0.0
    future.loc[10:19, "value"] = 1.0
    future.loc[20:29, "value"] = 4.0
    windows = (
        WindowDriftMonitor("time", ["value"], window_size=10, threshold=2)
        .fit(train)
        .evaluate(future)
    )
    assert windows["alert"].tolist() == [False, False, True]


def test_window_monitor_requires_fit_and_nonoverlapping_future():
    monitor = WindowDriftMonitor("time", ["value"], window_size=5)
    with pytest.raises(RuntimeError, match="not fitted"):
        monitor.evaluate(_timeline(10))
    train = _timeline(20)
    future = _timeline(10)
    future["time"] += pd.Timedelta(days=10)
    monitor.fit(train)
    assert monitor.evaluate(future.iloc[:4]).empty
    with pytest.raises(ValueError, match="future"):
        monitor.evaluate(pd.concat([train.iloc[-1:], future]))


def test_event_metrics_report_delay_and_false_alarms_by_window():
    frame = pd.DataFrame(
        {
            "window_start": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "window_end": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "alert": [True, False, True],
        }
    )
    result = event_metrics(frame, pd.Timestamp("2024-01-02"))
    assert result["false_alarm_rate"] == 1.0
    assert result["detected"] is True
    assert result["detection_delay"] == pd.Timedelta(days=1)
