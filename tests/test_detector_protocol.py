import numpy as np
import pandas as pd
import pytest

from etl_benchmark.pipeline import detect
from etl_benchmark.quality import ZScoreDetector
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
