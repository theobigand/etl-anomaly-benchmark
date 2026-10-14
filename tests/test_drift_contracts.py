import re

import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality import TemporalDriftDetector

pytestmark = pytest.mark.protocol

_DAY0 = pd.Timestamp("2024-01-01")


def _days(count):
    return _DAY0 + pd.to_timedelta(np.arange(count), unit="D")


# 60 reference rows alternating -1/+1 (mean 0), then 40 recent rows.
_REFERENCE = np.tile([-1.0, 1.0], 30)
_SIGMA = float(np.std(_REFERENCE, ddof=1))


def _message(text):
    return f"^{re.escape(text)}$"


def _stream(recent, extra=None):
    values = np.r_[_REFERENCE, np.asarray(recent, dtype=float)]
    frame = pd.DataFrame({"t": _days(len(values)), "x": values})
    for name, column in (extra or {}).items():
        frame[name] = column
    return frame


def _detector(**kwargs):
    return TemporalDriftDetector(time_column="t", **kwargs)


def test_defaults_are_the_documented_configuration():
    detector = TemporalDriftDetector()
    assert detector.time_column == "signup_date"
    assert (detector.reference_frac, detector.threshold, detector.outlier_z) == (0.6, 0.35, 5.0)


def test_unfitted_detector_names_itself():
    detector = _detector()
    for method in (detector.predict, detector.score):
        with pytest.raises(
            RuntimeError, match=_message("drift detector not fitted. Call fit() first.")
        ):
            method(_stream([0.0] * 40))


def test_recent_rows_score_the_squared_standardized_shift():
    frame = _stream([1.5] * 40)
    scores = _detector().fit(frame).score(frame)
    shift = 1.5 / _SIGMA
    assert scores.iloc[60:].tolist() == pytest.approx([shift * shift] * 40)
    # Older rows keep a faint signal at one fifth of the weight, only on the drift side.
    old = scores.iloc[:60]
    assert old[_REFERENCE == 1.0].tolist() == pytest.approx([shift * (1 / _SIGMA) * 0.2] * 30)
    assert (old[_REFERENCE == -1.0] == 0.0).all()


def test_the_drift_direction_does_not_matter():
    up = _stream([1.5] * 40)
    down = _stream([-1.5] * 40)
    up_scores = _detector().fit(up).score(up).iloc[60:]
    down_scores = _detector().fit(down).score(down).iloc[60:]
    assert down_scores.tolist() == pytest.approx(up_scores.tolist())


def test_a_window_needs_twenty_recent_rows():
    frame = _stream([1.5] * 40)
    detector = _detector().fit(frame)
    assert (detector.score(frame.iloc[:79]) == 0.0).all()
    assert (detector.score(frame.iloc[:80]).iloc[60:] > 0).all()
    assert (detector.predict(frame.iloc[:79]) == False).all()  # noqa: E712


def test_a_row_at_the_cutoff_belongs_to_the_recent_window():
    frame = _stream([1.5] * 40)
    detector = _detector().fit(frame)
    assert detector._cutoff == _days(61)[-1]
    assert detector.predict(frame.iloc[:80]).iloc[60]


def test_only_features_that_moved_enter_the_lean():
    flat = np.tile([-1.0, 1.0], 50)
    frame = _stream([1.5] * 40, extra={"y": flat})
    scores = _detector().fit(frame).score(frame)
    shift = 1.5 / _SIGMA
    assert scores.iloc[60:].tolist() == pytest.approx([shift * shift] * 40)


@pytest.mark.parametrize(("recent_shift", "expected"), [(0.02, 0.0), (0.05, None), (0.5, None)])
def test_negligible_window_shifts_are_ignored(recent_shift, expected):
    frame = _stream([recent_shift * _SIGMA] * 40)
    scores = _detector().fit(frame).score(frame).iloc[60:]
    if expected is None:
        assert (scores > 0).all()
    else:
        assert (scores == 0.0).all()


def test_lean_is_capped_at_four_standard_deviations():
    frame = _stream([10 * _SIGMA] * 40)
    scores = _detector(outlier_z=100.0).fit(frame).score(frame).iloc[60:]
    assert scores.tolist() == pytest.approx([10.0 * 4.0] * 40)


def test_single_feature_outliers_are_left_to_the_univariate_detectors():
    recent = [1.5] * 39 + [5.5 * _SIGMA]
    frame = _stream(recent)
    scores = _detector().fit(frame).score(frame)
    assert scores.iloc[-1] == 0.0
    assert (scores.iloc[60:99] > 0).all()
    inside = _stream([1.5] * 39 + [4.5 * _SIGMA])
    assert _detector().fit(inside).score(inside).iloc[-1] > 0


def test_flags_need_a_score_above_the_threshold_and_a_recent_row():
    frame = _stream([1.5] * 40)
    shift_squared = (1.5 / _SIGMA) ** 2
    low = _detector(threshold=shift_squared - 0.1).fit(frame).predict(frame)
    assert low.iloc[60:].all()
    assert not low.iloc[:60].any()  # old rows have a positive score but are never flagged
    high = _detector(threshold=shift_squared + 0.1).fit(frame).predict(frame)
    assert not high.any()
    assert low.index.equals(frame.index)


def test_reference_rows_are_the_oldest_ones_regardless_of_input_order():
    frame = _stream([1.5] * 40)
    shuffled = frame.sample(frac=1, random_state=4)
    expected = _detector().fit(frame).score(frame)
    actual = _detector().fit(shuffled).score(shuffled)
    pd.testing.assert_series_equal(actual.sort_index(), expected)


def test_the_reference_size_is_kept_between_one_row_and_all_but_one():
    frame = pd.DataFrame({"t": _days(10), "x": np.arange(10.0)})
    tiny = _detector(reference_frac=0.01).fit(frame)
    assert tiny._cutoff == _days(2)[-1]
    assert tiny._means["x"] == 0.0
    full = _detector(reference_frac=1.0).fit(frame)
    assert full._cutoff == _days(10)[-1]
    assert full._means["x"] == 4.0


def test_a_reference_standard_deviation_of_exactly_one_is_a_real_scale():
    reference = [0.0, 1.0, 2.0]
    frame = pd.DataFrame({"t": _days(23), "x": reference + [11.0] * 20})
    scores = _detector(reference_frac=0.14, outlier_z=100.0).fit(frame).score(frame).iloc[3:]
    assert scores.tolist() == pytest.approx([10.0 * 4.0] * 20)  # z = 10, lean capped at 4


def test_constant_reference_columns_carry_no_signal():
    frame = _stream([1.5] * 40, extra={"c": 5.0})
    frame = frame[["t", "c", "x"]]
    frame.loc[60:, "c"] = 100.0
    scores = _detector().fit(frame).score(frame)
    shift = 1.5 / _SIGMA
    assert scores.iloc[60:].tolist() == pytest.approx([shift * shift] * 40)
    assert np.isfinite(scores).all()


def test_explicit_columns_limit_the_features():
    frame = _stream([1.5] * 40, extra={"y": np.r_[np.tile([-1.0, 1.0], 30), [50.0] * 40]})
    scores = _detector(columns=["x"]).fit(frame).score(frame)
    shift = 1.5 / _SIGMA
    assert scores.iloc[60:].tolist() == pytest.approx([shift * shift] * 40)


def test_without_the_time_column_the_detector_is_a_silent_no_op():
    frame = _stream([1.5] * 40).drop(columns="t")
    detector = TemporalDriftDetector().fit(frame)
    assert not detector.predict(frame).any()
    assert (detector.score(frame) == 0.0).all()
    assert detector.predict(frame).index.equals(frame.index)
    assert detector.score(frame).index.equals(frame.index)


def test_refitting_without_the_time_column_deactivates_the_detector():
    frame = _stream([1.5] * 40)
    detector = _detector().fit(frame)
    assert detector.score(frame).max() > 0
    detector.fit(frame.drop(columns="t"))
    assert (detector.score(frame.drop(columns="t")) == 0.0).all()


def test_short_windows_and_still_windows_return_zero_scores_on_the_input_index():
    frame = _stream([1.5] * 40).set_axis(range(500, 600))
    detector = _detector().fit(frame)
    short = detector.score(frame.iloc[:70])
    assert short.index.equals(frame.index[:70])
    assert (short == 0.0).all()
    still = _stream([0.0] * 40).set_axis(range(500, 600))
    flat = _detector().fit(still).score(still)
    assert flat.index.equals(still.index)
    assert (flat == 0.0).all()


def test_rows_with_missing_features_score_zero_not_a_default_value():
    recent = [1.5] * 39 + [np.nan]
    frame = _stream(recent)
    scores = _detector().fit(frame).score(frame)
    assert scores.iloc[-1] == 0.0
    assert np.isfinite(scores).all()


def test_a_score_equal_to_the_threshold_is_not_flagged():
    frame = _stream([1.5] * 40)
    boundary = float(_detector().fit(frame).score(frame).iloc[60])
    flagged = _detector(threshold=boundary).fit(frame).predict(frame)
    assert not flagged.any()


def test_inactive_detector_returns_boolean_flags():
    frame = _stream([1.5] * 40).drop(columns="t")
    assert TemporalDriftDetector().fit(frame).predict(frame).dtype == bool
