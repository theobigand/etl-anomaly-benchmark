import logging

import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.gx import GreatExpectationsDetector

logging.getLogger("great_expectations").setLevel(logging.ERROR)


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "amount": rng.normal(50.0, 5.0, size=200),
            "label": rng.integers(0, 2, size=200).astype(float),
        }
    )


def test_gx_flags_null_and_out_of_range():
    df = _frame()
    # Fit the range check to the exact observed span so only injected
    # violations are flagged, keeping the assertion deterministic.
    det = GreatExpectationsDetector(bounds_quantiles=(0.0, 1.0)).fit(df)

    probe = df.copy()
    probe.loc[0, "amount"] = 10_000.0  # far outside the fitted quantile band
    probe.loc[1, "amount"] = np.nan  # violates not-null

    flags = det.predict(probe)

    assert bool(flags.iloc[0])
    assert bool(flags.iloc[1])
    assert not flags.iloc[2:].any()


def test_gx_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        GreatExpectationsDetector().predict(_frame())


def test_gx_score_within_unit_interval():
    df = _frame()
    det = GreatExpectationsDetector().fit(df)

    probe = df.copy()
    probe.loc[0, "amount"] = np.nan
    scores = det.score(probe)

    assert scores.between(0.0, 1.0).all()
    assert scores.iloc[0] > 0.0


def test_gx_preserves_index():
    df = _frame()
    df.index = df.index + 1000
    det = GreatExpectationsDetector().fit(df)

    flags = det.predict(df)

    assert flags.index.equals(df.index)


def test_constant_feature_has_no_spurious_range_expectation():
    frame = pd.DataFrame({"constant": [2.0] * 30})
    detector = GreatExpectationsDetector().fit(frame)
    assert detector._bounds == {}
    assert not detector.predict(frame).any()
