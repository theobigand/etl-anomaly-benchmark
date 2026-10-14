import re

import numpy as np
import pandas as pd
import pytest

from etl_benchmark import config
from etl_benchmark.quality import (
    GreatExpectationsDetector,
    IQRDetector,
    IsolationForestDetector,
    LOFDetector,
    OneClassSVMDetector,
    ZScoreDetector,
)
from etl_benchmark.quality.base import numeric_features

pytestmark = pytest.mark.protocol


def _message(text):
    return f"^{re.escape(text)}$"


def _two_columns():
    return pd.DataFrame({"x": np.arange(30.0), "y": [9.0] * 29 + [90.0]})


def test_rule_defaults_are_the_documented_thresholds():
    assert ZScoreDetector().threshold == 3.0
    assert IQRDetector().multiplier == 1.5


@pytest.mark.parametrize(
    "make",
    [ZScoreDetector, IQRDetector, IsolationForestDetector, LOFDetector, GreatExpectationsDetector],
)
def test_explicit_columns_restrict_what_a_detector_reads(make):
    frame = _two_columns()
    detector = make(columns=["x"]).fit(frame)
    blind_to_y = frame.assign(y=np.where(frame.index % 2 == 0, 1e9, -1e9))
    pd.testing.assert_series_equal(detector.score(frame), detector.score(blind_to_y))


@pytest.mark.parametrize("make", [ZScoreDetector, IQRDetector])
def test_rule_detectors_report_the_unfitted_state_by_name(make):
    detector = make()
    expected = f"{detector.name} detector not fitted. Call fit() first."
    for method in (detector.predict, detector.score):
        with pytest.raises(RuntimeError, match=_message(expected)):
            method(_two_columns())


def test_gx_and_pyod_report_the_unfitted_state_by_name():
    for detector in (GreatExpectationsDetector(), IsolationForestDetector()):
        expected = f"{detector.name} detector not fitted. Call fit() first."
        with pytest.raises(RuntimeError, match=_message(expected)):
            detector.predict(_two_columns())
        with pytest.raises(RuntimeError, match=_message(expected)):
            detector.score(_two_columns())


def test_missing_values_at_evaluation_time_are_never_flagged_and_score_zero():
    train = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0, 4.0], "y": [5.0, 6.0, 7.0, 8.0, 9.0]})
    test = pd.DataFrame({"x": [np.nan, np.nan], "y": [np.nan, 7.0]})
    for detector in (ZScoreDetector().fit(train), IQRDetector().fit(train)):
        assert detector.predict(test).tolist() == [False, False]
        assert detector.score(test).tolist() == [0.0, 0.0]


def test_zscore_uses_a_standard_deviation_of_exactly_one():
    train = pd.DataFrame({"x": [0.0, 1.0, 2.0]})
    detector = ZScoreDetector(threshold=3.0).fit(train)
    probe = pd.DataFrame({"x": [1.0, 100.0]})
    assert detector.score(probe).tolist() == [0.0, 99.0]
    assert detector.predict(probe).tolist() == [False, True]


def test_zscore_constant_training_column_scores_zero_and_is_never_flagged():
    detector = ZScoreDetector().fit(pd.DataFrame({"x": [4.0, 4.0, 4.0]}))
    probe = pd.DataFrame({"x": [4.0, 400.0]})
    assert detector.score(probe).tolist() == [0.0, 0.0]
    assert detector.predict(probe).tolist() == [False, False]


def test_iqr_scores_distance_beyond_the_fence_in_iqr_units():
    detector = IQRDetector().fit(pd.DataFrame({"x": [0.0, 1.0, 2.0]}))  # IQR is exactly 1
    probe = pd.DataFrame({"x": [1.0, 3.5, -2.0]})  # fences are -1.0 and 3.0
    assert detector.score(probe).tolist() == [0.0, 0.5, 1.0]
    assert detector.predict(probe).tolist() == [False, True, True]


def test_iqr_constant_training_column_scores_zero():
    detector = IQRDetector().fit(pd.DataFrame({"x": [4.0, 4.0, 4.0]}))
    assert detector.score(pd.DataFrame({"x": [4.0, 400.0]})).tolist() == [0.0, 0.0]


def test_pyod_outputs_follow_the_input_index_and_float_scores():
    train = pd.DataFrame({"x": np.arange(30.0), "y": np.arange(30.0)[::-1]})
    probe = train.iloc[:4].set_axis([40, 41, 42, 43])
    detector = LOFDetector(contamination=0.1).fit(train)
    assert detector.predict(probe).index.tolist() == [40, 41, 42, 43]
    assert detector.score(probe).index.tolist() == [40, 41, 42, 43]
    assert detector.score(probe).dtype == float


def test_pyod_needs_a_numeric_column_and_names_the_available_ones():
    frame = pd.DataFrame({"label": ["a", "b"], "other": ["c", "d"]})
    with pytest.raises(
        ValueError,
        match=_message(
            "isolation_forest detector needs at least one numeric column; got ['label', 'other']"
        ),
    ):
        IsolationForestDetector().fit(frame)


def test_forest_randomness_defaults_to_the_project_seed_and_can_be_overridden():
    assert IsolationForestDetector()._build_estimator().random_state == config.RANDOM_SEED
    assert IsolationForestDetector(random_state=5)._build_estimator().random_state == 5


def test_gx_counts_every_violated_expectation_once_per_row():
    train = pd.DataFrame({"x": np.arange(100.0), "y": np.arange(100.0)})
    detector = GreatExpectationsDetector(bounds_quantiles=(0.05, 0.95)).fit(train)
    probe = pd.DataFrame({"x": [50.0, 500.0, -500.0], "y": [50.0, 500.0, 50.0]}, index=[7, 8, 9])
    scores = detector.score(probe)
    assert scores.index.tolist() == [7, 8, 9]
    assert scores.tolist() == [0.0, 2 / 4, 1 / 4]
    assert detector.predict(probe).tolist() == [False, True, True]


def test_gx_null_checks_can_be_switched_off():
    train = pd.DataFrame({"x": np.arange(100.0)})
    probe = pd.DataFrame({"x": [np.nan, 50.0]})
    assert GreatExpectationsDetector().fit(train).predict(probe).tolist() == [True, False]
    quiet = GreatExpectationsDetector(check_nulls=False).fit(train)
    assert quiet.predict(probe).tolist() == [False, False]


def test_numeric_feature_checks_name_the_failed_contract():
    frame = pd.DataFrame({"x": [1.0, 2.0], "name": ["a", "b"], "z": [np.nan, np.nan]})
    with pytest.raises(ValueError, match=_message("at least one numeric feature is required")):
        numeric_features(frame, [], training=True)
    with pytest.raises(ValueError, match=_message("feature columns must be numeric")):
        numeric_features(frame, ["x", "name"], training=True)
    with pytest.raises(ValueError, match=_message("nonfinite feature value")):
        numeric_features(pd.DataFrame({"x": [1.0, np.inf]}), ["x"], training=True)
    with pytest.raises(ValueError, match=_message("all-missing training feature")):
        numeric_features(frame, ["x", "z"], training=True)
    assert numeric_features(frame, ["x", "z"], training=False).shape == (2, 2)


def test_only_a_fully_missing_column_blocks_training_not_a_fully_missing_row():
    frame = pd.DataFrame({"x": [np.nan, 1.0], "y": [np.nan, 2.0]})
    assert numeric_features(frame, ["x", "y"], training=True).shape == (2, 2)


def test_pyod_scores_rows_whose_feature_is_missing_after_fitting():
    train = pd.DataFrame({"x": np.arange(40.0), "y": np.arange(40.0)[::-1]})
    probe = pd.DataFrame({"x": [np.nan, np.nan], "y": [1.0, 20.0]})
    detector = IsolationForestDetector(contamination=0.1).fit(train)
    assert np.isfinite(detector.score(probe)).all()
    assert detector.predict(probe).dtype == bool


@pytest.mark.parametrize(
    "make",
    [ZScoreDetector, IQRDetector, IsolationForestDetector, LOFDetector, OneClassSVMDetector],
)
def test_a_rows_score_does_not_depend_on_the_rest_of_the_evaluated_batch(make):
    rng = np.random.default_rng(2)
    train = pd.DataFrame(rng.normal(size=(120, 3)), columns=list("abc"))
    batch = pd.DataFrame(rng.normal(3.0, 2.0, size=(10, 3)), columns=list("abc"))
    detector = make().fit(train)
    together = detector.score(batch)
    alone = pd.concat([detector.score(batch.iloc[[i]]) for i in range(len(batch))])
    np.testing.assert_allclose(together.to_numpy(), alone.to_numpy())
    reordered = detector.score(batch.iloc[::-1])
    np.testing.assert_allclose(together.to_numpy(), reordered.to_numpy()[::-1])
