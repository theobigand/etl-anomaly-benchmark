import numpy as np
import pandas as pd

from etl_benchmark.pipeline import detect
from etl_benchmark.quality import ZScoreDetector


def test_detect_excludes_label_from_features():
    df = pd.DataFrame({"x": [0.0] * 99 + [100.0], "label": [1] * 100})
    det = ZScoreDetector(threshold=3.0)

    res = detect(df, det, label_column="label")

    assert list(det._means.index) == ["x"]  # label not used as a feature
    assert bool(res.flags.iloc[-1])
    assert len(res.flags) == len(df)


def test_detect_without_label_uses_all_columns():
    df = pd.DataFrame({"x": np.arange(100.0), "y": np.arange(100.0)})
    det = ZScoreDetector()

    detect(df, det)

    assert set(det._means.index) == {"x", "y"}


def test_detect_timings_are_consistent():
    df = pd.DataFrame({"x": np.arange(100.0)})

    res = detect(df, ZScoreDetector())

    assert res.fit_s >= 0 and res.predict_s >= 0 and res.score_s >= 0
    assert res.detect_s == res.fit_s + res.predict_s + res.score_s
