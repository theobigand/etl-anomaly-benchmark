"""A fit that raises must not leave a detector that looks fitted.

Contract: ``fit`` either completes and replaces the whole fitted state, or raises and leaves the
detector exactly as it was (unfitted for a first fit, the previous fit for a refit). Scoring or
predicting with an unfitted detector raises ``RuntimeError``; it never returns flags.
"""

import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.autoencoder import AutoencoderDetector
from etl_benchmark.quality.ml import (
    COPODDetector,
    ECODDetector,
    HBOSDetector,
    IsolationForestDetector,
    KNNDetector,
    LOFDetector,
    OneClassSVMDetector,
    PCADetector,
)

pytestmark = pytest.mark.protocol

DETECTORS = [
    IsolationForestDetector,
    LOFDetector,
    OneClassSVMDetector,
    ECODDetector,
    COPODDetector,
    HBOSDetector,
    KNNDetector,
    PCADetector,
    pytest.param(AutoencoderDetector, id="AutoencoderDetector"),
]
# The tail-probability and reconstruction detectors do not validate the contamination before
# their fit, so these are the ones that used to keep a half-built model after the failure.
UNVALIDATED = [ECODDetector, COPODDetector, PCADetector, AutoencoderDetector]
OUT_OF_RANGE = 2.0


def _frame(columns=("a", "b", "c"), rows=120, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(size=(rows, len(columns))), columns=list(columns))


def _fail_to_fit(detector, frame):
    detector.contamination = OUT_OF_RANGE
    with pytest.raises(ValueError):
        detector.fit(frame)


@pytest.mark.parametrize("cls", DETECTORS)
def test_a_valid_fit_still_flags_about_the_contamination_share(cls):
    frame = _frame()
    detector = cls(contamination=0.1).fit(frame)
    flags = detector.predict(frame)
    assert flags.dtype == bool
    assert 0 < flags.sum() < len(frame) / 2
    assert detector.feature_names_ == ["a", "b", "c"]


@pytest.mark.parametrize("cls", UNVALIDATED)
def test_an_out_of_range_contamination_fails_the_fit(cls):
    with pytest.raises(ValueError):
        cls(contamination=OUT_OF_RANGE).fit(_frame())


@pytest.mark.parametrize("cls", DETECTORS)
@pytest.mark.parametrize("method", ["predict", "score"])
def test_a_detector_whose_first_fit_failed_refuses_to_score(cls, method):
    detector = cls(contamination=0.1)
    frame = _frame()
    _fail_to_fit(detector, frame)
    with pytest.raises(RuntimeError, match="not fitted"):
        getattr(detector, method)(frame)


@pytest.mark.parametrize("cls", DETECTORS)
def test_a_failed_first_fit_leaves_no_partial_state(cls):
    detector = cls(contamination=0.1)
    _fail_to_fit(detector, _frame())
    assert detector.feature_names_ is None
    assert detector._model is None
    assert detector._imputer is None
    assert detector._scaler is None


@pytest.mark.parametrize("cls", DETECTORS)
def test_a_fit_rejected_for_its_data_leaves_no_feature_names(cls):
    frame = _frame()
    frame["c"] = np.nan  # an all-missing training column is refused after the columns are chosen
    detector = cls(contamination=0.1)
    with pytest.raises(ValueError, match="all-missing"):
        detector.fit(frame)
    assert detector.feature_names_ is None
    with pytest.raises(RuntimeError, match="not fitted"):
        detector.predict(frame)


@pytest.mark.parametrize("cls", DETECTORS)
def test_a_failed_refit_keeps_the_previous_fit_unchanged(cls):
    first = _frame(("a", "b", "c"), seed=1)
    other = _frame(("x", "y"), seed=2)
    detector = cls(contamination=0.1).fit(first)
    before_scores = detector.score(first)
    before_flags = detector.predict(first)
    before_model = detector._model

    _fail_to_fit(detector, other)

    assert detector._model is before_model
    assert detector.feature_names_ == ["a", "b", "c"]
    pd.testing.assert_series_equal(detector.score(first), before_scores)
    pd.testing.assert_series_equal(detector.predict(first), before_flags)


@pytest.mark.parametrize("cls", DETECTORS)
def test_a_successful_refit_replaces_the_whole_state(cls):
    detector = cls(contamination=0.1).fit(_frame(("a", "b", "c"), seed=1))
    other = _frame(("x", "y"), seed=2)
    detector.fit(other)
    assert detector.feature_names_ == ["x", "y"]
    assert len(detector.predict(other)) == len(other)
    with pytest.raises(ValueError, match="missing feature columns"):
        detector.predict(_frame(("a", "b", "c")))
