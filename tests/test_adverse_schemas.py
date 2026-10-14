import numpy as np
import pandas as pd
import pytest

from etl_benchmark.pipeline import detect
from etl_benchmark.quality.ml import IsolationForestDetector
from etl_benchmark.quality.rules import IQRDetector, ZScoreDetector


@pytest.mark.parametrize("factory", [ZScoreDetector, IQRDetector, IsolationForestDetector])
def test_all_missing_training_feature_fails_explicitly(factory):
    frame = pd.DataFrame({"value": [np.nan] * 20})
    with pytest.raises(ValueError, match="all-missing"):
        detect(frame, factory())


@pytest.mark.parametrize("factory", [ZScoreDetector, IQRDetector, IsolationForestDetector])
def test_infinite_training_value_fails_explicitly(factory):
    frame = pd.DataFrame({"value": [1.0] * 19 + [np.inf]})
    with pytest.raises(ValueError, match="nonfinite"):
        detect(frame, factory())


@pytest.mark.parametrize("factory", [ZScoreDetector, IQRDetector, IsolationForestDetector])
def test_infinite_evaluation_value_fails_explicitly(factory):
    train = pd.DataFrame({"value": np.linspace(0.0, 1.0, 20)})
    test = pd.DataFrame({"value": [0.5, np.inf]})
    with pytest.raises(ValueError, match="nonfinite"):
        detect(test, factory(), fit_df=train)


@pytest.mark.parametrize("factory", [ZScoreDetector, IQRDetector, IsolationForestDetector])
def test_missing_required_feature_fails_explicitly(factory):
    train = pd.DataFrame({"value": np.linspace(0.0, 1.0, 20)})
    detector = factory().fit(train)
    with pytest.raises(ValueError, match="missing feature"):
        detector.predict(pd.DataFrame({"other": [0.5]}))


@pytest.mark.parametrize("factory", [ZScoreDetector, IQRDetector, IsolationForestDetector])
def test_constant_feature_has_finite_output(factory):
    frame = pd.DataFrame({"value": [1.0] * 20, "note": ["same"] * 20})
    result = detect(frame, factory())
    assert result.flags.index.equals(frame.index)
    assert np.isfinite(result.scores).all()


@pytest.mark.parametrize("factory", [ZScoreDetector, IQRDetector, IsolationForestDetector])
def test_detectors_read_features_by_name_so_extra_and_reordered_columns_are_harmless(factory):
    rng = np.random.default_rng(1)
    train = pd.DataFrame({"a": rng.normal(size=40), "b": rng.normal(size=40)})
    probe = pd.DataFrame({"a": [0.1, 5.0], "b": [-0.2, 4.0]})
    detector = factory().fit(train)
    expected = detector.score(probe)
    rearranged = probe[["b", "a"]].assign(note=["x", "y"], extra=[1.0, 2.0])
    pd.testing.assert_series_equal(detector.score(rearranged), expected)


def test_the_pipeline_still_refuses_a_changed_schema_between_fit_and_evaluation():
    train = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]})
    with pytest.raises(ValueError, match="schema must match in order"):
        detect(train[["b", "a"]], ZScoreDetector(), fit_df=train)
    with pytest.raises(ValueError, match="schema must match in order"):
        detect(train.assign(c=0.0), ZScoreDetector(), fit_df=train)
