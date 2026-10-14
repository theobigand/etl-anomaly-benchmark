import re

import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.window_drift import WindowDriftMonitor, event_metrics

pytestmark = pytest.mark.protocol


def _message(text):
    return f"^{re.escape(text)}$"


def _reference(values=(0.0, 4.0), start="2024-01-01"):
    times = pd.date_range(start, periods=len(values), freq="D")
    return pd.DataFrame({"time": times, "value": list(values)})


def _future(values, start="2024-02-01"):
    times = pd.date_range(start, periods=len(values), freq="D")
    return pd.DataFrame({"time": times, "value": list(values)})


def test_constructor_defaults_and_inclusive_bounds():
    monitor = WindowDriftMonitor("time", ["value"])
    assert (monitor.window_size, monitor.threshold) == (20, 2.0)
    WindowDriftMonitor("time", ["value"], window_size=2, threshold=0.5)
    with pytest.raises(ValueError, match=_message("window_size must be at least two")):
        WindowDriftMonitor("time", ["value"], window_size=1)
    for threshold in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match=_message("threshold must be positive and finite")):
            WindowDriftMonitor("time", ["value"], threshold=threshold)


def test_fit_needs_two_reference_rows_and_remembers_the_last_timestamp():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2)
    with pytest.raises(ValueError, match=_message("reference needs at least two rows")):
        monitor.fit(_reference((1.0,)))
    monitor.fit(_reference((0.0, 2.0)))
    assert monitor.reference_end == pd.Timestamp("2024-01-02", tz="UTC")


def test_scores_use_the_population_standard_deviation_of_the_reference():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2, threshold=2.0).fit(_reference())
    windows = monitor.evaluate(_future([8.0, 8.0]))
    assert windows.loc[0, "score"] == 3.0  # (8 - 2) / 2; ddof=1 would give 2.12


def test_an_alert_requires_the_score_to_exceed_the_threshold():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2, threshold=2.0).fit(_reference())
    equal = monitor.evaluate(_future([6.0, 6.0]))
    assert equal.loc[0, "score"] == 2.0
    assert not bool(equal.loc[0, "alert"])
    assert bool(monitor.evaluate(_future([6.5, 6.5])).loc[0, "alert"])


def test_scores_are_standardized_per_feature_by_the_reference_scale():
    reference = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=2),
            "a": [0.0, 10.0],
            "b": [0.0, 4.0],
        }
    )
    future = pd.DataFrame(
        {"time": pd.date_range("2024-02-01", periods=2), "a": [5.0, 5.0], "b": [8.0, 8.0]}
    )
    windows = WindowDriftMonitor("time", ["a", "b"], window_size=2).fit(reference).evaluate(future)
    assert windows.loc[0, "score"] == 3.0  # a moved by 0 sigma, b by 3 sigma (scale 2)


def test_windows_report_their_bounds_size_and_use_the_documented_columns():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2).fit(_reference())
    windows = monitor.evaluate(_future([1.0, 1.0, 1.0, 1.0, 1.0]))
    assert windows.columns.tolist() == ["window_start", "window_end", "n_rows", "score", "alert"]
    assert windows["n_rows"].tolist() == [2, 2]
    assert windows["window_start"].tolist() == list(
        pd.to_datetime(["2024-02-01", "2024-02-03"], utc=True)
    )
    assert windows["window_end"].tolist() == list(
        pd.to_datetime(["2024-02-02", "2024-02-04"], utc=True)
    )
    empty = monitor.evaluate(_future([1.0]))
    assert empty.columns.tolist() == windows.columns.tolist()
    assert empty.empty


def test_windows_follow_time_order_even_when_the_input_is_shuffled():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2).fit(_reference())
    future = _future([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    shuffled = future.sample(frac=1, random_state=3)
    expected = monitor.evaluate(future)
    pd.testing.assert_frame_equal(monitor.evaluate(shuffled), expected)
    assert expected["window_start"].is_monotonic_increasing


def test_ties_inside_one_timestamp_are_ordered_by_feature_values():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2).fit(_reference())
    same_time = pd.Timestamp("2024-02-01")
    future = pd.DataFrame({"time": [same_time] * 4, "value": [9.0, 1.0, 5.0, 3.0]})
    windows = monitor.evaluate(future)
    assert windows["n_rows"].tolist() == [4]
    assert windows.loc[0, "score"] == pytest.approx((4.5 - 2.0) / 2.0)


def test_mixed_timestamp_formats_are_read_as_instants():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2).fit(_reference())
    future = pd.DataFrame(
        {"time": ["2024-02-01", "2024-02-02T12:30:00+02:00"], "value": [1.0, 1.0]}
    )
    windows = monitor.evaluate(future)
    assert windows.loc[0, "window_end"] == pd.Timestamp("2024-02-02T10:30:00", tz="UTC")


def test_input_errors_name_the_failed_contract():
    monitor = WindowDriftMonitor("time", ["value"], window_size=2)
    with pytest.raises(ValueError, match=_message("invalid timestamp")):
        monitor.fit(_reference().assign(time=["x", "y"]))
    with pytest.raises(ValueError, match=_message("missing timestamp")):
        monitor.fit(_reference().assign(time=[pd.Timestamp("2024-01-01"), pd.NaT]))
    with pytest.raises(ValueError, match=_message("missing feature column")):
        monitor.fit(_reference().drop(columns="value"))
    with pytest.raises(ValueError, match=_message("feature columns must be numeric")):
        monitor.fit(_reference().assign(value=["a", "b"]))
    with pytest.raises(ValueError, match=_message("feature columns must be finite")):
        monitor.fit(_reference().assign(value=[1.0, np.inf]))
    monitor.fit(_reference())
    with pytest.raises(ValueError, match=_message("future period is empty")):
        monitor.evaluate(_future([]))
    with pytest.raises(ValueError, match=_message("future period overlaps the reference")):
        monitor.evaluate(_reference())
    with pytest.raises(RuntimeError, match=_message("monitor not fitted")):
        WindowDriftMonitor("time", ["value"]).evaluate(_future([1.0, 2.0]))


def test_a_monitor_without_features_is_rejected():
    with pytest.raises(ValueError, match=_message("missing feature column")):
        WindowDriftMonitor("time", [], window_size=2).fit(_reference())


def _alerts(ends, alerts):
    return pd.DataFrame({"window_end": pd.to_datetime(ends), "alert": alerts})


def test_event_metrics_compare_instants_across_time_zones():
    windows = _alerts(["2024-01-01", "2024-01-02", "2024-01-03"], [True, False, True])
    # 2024-01-02T01:00+02:00 is 2024-01-01T23:00 UTC: only the first window ends before it.
    aware = event_metrics(windows, pd.Timestamp("2024-01-02T01:00:00+02:00"))
    assert aware["false_alarm_rate"] == 1.0
    assert aware["detection_delay"] == pd.Timedelta(days=1, hours=1)
    naive = event_metrics(windows, pd.Timestamp("2024-01-02T01:00:00"))
    assert naive["false_alarm_rate"] == 0.5
    assert naive["detection_delay"] == pd.Timedelta(hours=23)


def test_event_metrics_without_alerts_or_prechange_windows():
    quiet = event_metrics(_alerts(["2024-01-05"], [False]), "2024-01-01")
    assert quiet["detected"] is False
    assert pd.isna(quiet["detection_delay"])
    assert np.isnan(quiet["false_alarm_rate"])
    late = event_metrics(_alerts(["2024-01-01", "2024-01-05"], [False, True]), "2024-01-03")
    assert late["detected"] is True
    assert late["false_alarm_rate"] == 0.0
    assert late["detection_delay"] == pd.Timedelta(days=2)


def test_event_metrics_reject_missing_or_non_boolean_window_results():
    message = _message("window results are required")
    with pytest.raises(ValueError, match=message):
        event_metrics(_alerts([], []).astype({"alert": bool}), "2024-01-01")
    with pytest.raises(ValueError, match=message):
        event_metrics(pd.DataFrame({"window_end": ["2024-01-01"]}), "2024-01-01")
    with pytest.raises(ValueError, match=message):
        event_metrics(pd.DataFrame({"alert": [True]}), "2024-01-01")
    with pytest.raises(ValueError, match=_message("alert must be boolean")):
        event_metrics(_alerts(["2024-01-01"], [1]), "2024-01-01")
