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


def test_detect_fits_on_sample_but_scores_every_row():
    # fit frame: mild spread, no gross outlier
    fit_df = pd.DataFrame({"x": [9.0, 10.0, 11.0] * 100, "label": [0] * 300})
    full = pd.DataFrame({"x": [9.0, 10.0, 11.0] * 100 + [10_000.0], "label": [0] * 301})
    det = ZScoreDetector(threshold=3.0)

    res = detect(full, det, label_column="label", fit_df=fit_df)

    assert list(det._means.index) == ["x"]  # label kept out of the fit features
    assert len(res.flags) == len(full)  # scored on the full frame
    assert bool(res.flags.iloc[-1])  # the row absent from the fit sample is still flagged
    assert not res.flags.iloc[:-1].any()
