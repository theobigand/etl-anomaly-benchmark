import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.rules import ZScoreDetector


def test_zscore_flags_extreme_outlier():
    rng = np.random.default_rng(42)
    normal = rng.normal(0.0, 1.0, size=999)
    df = pd.DataFrame({"x": np.concatenate([normal, [100.0]])})

    flags = ZScoreDetector(threshold=3.0).fit_predict(df)

    assert bool(flags.iloc[-1])
    assert flags.iloc[:-1].sum() < 20


def test_zscore_ignores_constant_column():
    df = pd.DataFrame({"x": [1.0] * 100, "y": [0.0] * 100})

    flags = ZScoreDetector(threshold=3.0).fit_predict(df)

    assert not flags.any()


def test_zscore_predict_before_fit_raises():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})

    with pytest.raises(RuntimeError):
        ZScoreDetector().predict(df)


def test_zscore_restricted_to_user_columns():
    df = pd.DataFrame({"x": [0.0] * 99 + [100.0], "y": [0.0] * 99 + [100.0]})

    flags = ZScoreDetector(threshold=3.0, columns=["x"]).fit_predict(df)

    assert bool(flags.iloc[-1])
