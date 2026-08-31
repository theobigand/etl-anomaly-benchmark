import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.ml import (
    IsolationForestDetector,
    LOFDetector,
    OneClassSVMDetector,
)

ML_DETECTORS = [IsolationForestDetector, LOFDetector, OneClassSVMDetector]


def _blob_with_outliers(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, size=(n, 3))
    x[-5:] += 25.0  # five gross outliers
    return pd.DataFrame(x, columns=["a", "b", "c"])


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_flags_planted_outliers(cls):
    df = _blob_with_outliers()

    det = cls(contamination=0.05).fit(df)
    flags = det.predict(df)

    assert flags.iloc[-5:].all()  # every planted outlier is caught
    assert flags.iloc[:-5].mean() < 0.10  # few false positives on the blob


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_score_ranks_outliers_highest(cls):
    df = _blob_with_outliers()

    scores = cls(contamination=0.05).fit(df).score(df)

    assert scores.index.equals(df.index)
    assert scores.iloc[-5:].min() > scores.iloc[:-5].max()


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_predict_before_fit_raises(cls):
    with pytest.raises(RuntimeError):
        cls().predict(_blob_with_outliers())


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_ignores_non_numeric_and_imputes_nans(cls):
    df = _blob_with_outliers()
    df["label"] = "keep"  # non-numeric, must be dropped silently
    df.loc[3, "a"] = np.nan  # must be imputed, not crash

    det = cls(contamination=0.05).fit(df)
    flags = det.predict(df)

    assert det.feature_names_ == ["a", "b", "c"]
    assert len(flags) == len(df)


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_raises_without_numeric_columns(cls):
    df = pd.DataFrame({"city": ["paris", "lyon", "nice"]})

    with pytest.raises(ValueError):
        cls().fit(df)


def test_ml_detectors_have_distinct_names():
    names = {cls().name for cls in ML_DETECTORS}
    assert names == {"isolation_forest", "lof", "ocsvm"}
