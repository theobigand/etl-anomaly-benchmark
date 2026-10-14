import numpy as np
import pandas as pd
import pytest

from etl_benchmark.pipeline import detect
from etl_benchmark.quality import ZScoreDetector
from etl_benchmark.quality.base import Detector, numeric_features
from etl_benchmark.quality.ml import IsolationForestDetector

pytestmark = pytest.mark.protocol


class BadDetector:
    name = "bad"

    def fit(self, df):
        return self

    def predict(self, df):
        return pd.Series([True] * len(df), index=range(100, 100 + len(df)))

    def score(self, df):
        return pd.Series(np.zeros(len(df)), index=df.index)


def test_detector_output_index_must_match_input():
    with pytest.raises(ValueError, match="index"):
        detect(pd.DataFrame({"x": [1.0, 2.0]}, index=[10, 11]), BadDetector())


def test_fit_and_test_feature_schema_must_match():
    train = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
    test = train[["y", "x"]]
    with pytest.raises(ValueError, match="schema"):
        detect(test, ZScoreDetector(), fit_df=train)


def test_held_out_values_do_not_affect_fitted_rule_statistics():
    train = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    test = pd.DataFrame({"x": [1000.0, -1000.0]})
    detector = ZScoreDetector()
    detect(test, detector, fit_df=train)
    assert detector._means["x"] == 2.0


def test_ml_imputer_scaler_and_scores_ignore_held_out_values_and_labels():
    train = pd.DataFrame({"x": [0.0, 2.0] * 20, "Class": [0, 1] * 20})
    test = pd.DataFrame({"x": [1000.0, -1000.0], "Class": [0, 1]})
    detector = IsolationForestDetector(contamination=0.1)
    first = detect(test, detector, label_column="Class", fit_df=train)
    assert detector.feature_names_ == ["x"]
    assert detector._imputer.statistics_[0] == 1.0
    assert detector._scaler.mean_[0] == 1.0
    changed_labels = test.assign(Class=[1, 0])
    second = detect(
        changed_labels,
        IsolationForestDetector(contamination=0.1),
        label_column="Class",
        fit_df=train,
    )
    pd.testing.assert_series_equal(first.scores, second.scores)


@pytest.mark.parametrize(
    ("flags", "scores", "message"),
    [
        ([False, True], pd.Series([0.0, 1.0], index=[10, 11]), "flags"),
        (pd.Series([0, 1], index=[10, 11]), pd.Series([0.0, 1.0], index=[10, 11]), "boolean"),
        (pd.Series([False, True], index=[10, 11]), [0.0, 1.0], "scores"),
        (
            pd.Series([False, True], index=[10, 11]),
            pd.Series([0.0, float("inf")], index=[10, 11]),
            "finite",
        ),
    ],
)
def test_detector_contract_rejects_malformed_outputs(flags, scores, message):
    class MalformedDetector:
        name = "malformed"

        def fit(self, _frame):
            return self

        def predict(self, _frame):
            return flags

        def score(self, _frame):
            return scores

    with pytest.raises(ValueError, match=message):
        detect(pd.DataFrame({"x": [1.0, 2.0]}, index=[10, 11]), MalformedDetector())


def test_base_detector_binary_score_and_fit_predict_contract():
    class ThresholdDetector(Detector):
        name = "threshold"

        def fit(self, _frame):
            return self

        def predict(self, frame):
            return frame["x"] > 2

    frame = pd.DataFrame({"x": [1.0, 3.0]}, index=[10, 11])
    detector = ThresholdDetector()
    assert detector.fit_predict(frame).tolist() == [False, True]
    assert detector.score(frame).tolist() == [0.0, 1.0]
    assert detector.score(frame).index.equals(frame.index)


@pytest.mark.parametrize(
    ("columns", "frame", "message"),
    [
        ([], pd.DataFrame({"x": [1.0]}), "at least one"),
        (["x"], pd.DataFrame({"x": ["bad"]}), "numeric"),
    ],
)
def test_numeric_feature_contract_rejects_unusable_schema(columns, frame, message):
    with pytest.raises(ValueError, match=message):
        numeric_features(frame, columns, training=True)
