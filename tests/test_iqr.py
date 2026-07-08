import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.rules import IQRDetector


def test_iqr_flags_extreme_outlier():
    rng = np.random.default_rng(42)
    normal = rng.normal(0.0, 1.0, size=999)
    df = pd.DataFrame({"x": np.concatenate([normal, [100.0]])})

    flags = IQRDetector(multiplier=1.5).fit_predict(df)

    assert bool(flags.iloc[-1])
    assert flags.iloc[:-1].sum() < 50


def test_iqr_ignores_constant_column():
    df = pd.DataFrame({"x": [1.0] * 100, "y": [0.0] * 100})

    flags = IQRDetector().fit_predict(df)

    assert not flags.any()


def test_iqr_predict_before_fit_raises():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})

    with pytest.raises(RuntimeError):
        IQRDetector().predict(df)


def test_iqr_score_grows_with_distance():
    df = pd.DataFrame({"x": list(range(100)) + [10_000.0]})

    det = IQRDetector().fit(df)
    scores = det.score(df)

    assert scores.iloc[-1] == scores.max()
    assert scores.iloc[-1] > scores.iloc[:-1].max()


def test_iqr_restricted_to_user_columns():
    # y carries the outlier; restricting to x must ignore it.
    df = pd.DataFrame({"x": list(range(100)), "y": list(range(100))})
    df.loc[99, "y"] = 10_000.0

    assert not IQRDetector(columns=["x"]).fit_predict(df).any()
    assert bool(IQRDetector(columns=["y"]).fit_predict(df).iloc[-1])
