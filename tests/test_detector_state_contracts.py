"""Partly fitted rule detectors refuse to score, and the GX failure counts are integers."""

import pandas as pd
import pytest

from etl_benchmark.quality.gx import GreatExpectationsDetector
from etl_benchmark.quality.rules import IQRDetector, ZScoreDetector

pytestmark = pytest.mark.protocol


@pytest.mark.parametrize(
    ("detector", "fields"),
    [
        (IQRDetector, ("_lower", "_upper")),
        (ZScoreDetector, ("_means", "_stds")),
    ],
)
def test_a_detector_with_only_part_of_its_statistics_is_not_fitted(detector, fields):
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})
    for kept in range(2):
        model = detector().fit(frame)
        setattr(model, fields[kept], None)
        with pytest.raises(RuntimeError, match="not fitted"):
            model.score(frame)


def test_the_expectation_failure_counts_are_integers_aligned_to_the_input_index():
    train = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [1.0, 2.0, 3.0, 4.0]})
    detector = GreatExpectationsDetector().fit(train)
    test = pd.DataFrame({"a": [2.0, 99.0], "b": [2.0, None]}, index=["x", "y"])
    counts = detector._failures_per_row(test)
    assert counts.dtype.kind == "i"
    assert counts.to_dict() == {"x": 0, "y": 2}


def _drifting_frame():
    import numpy as np

    rng = np.random.default_rng(5)
    times = pd.date_range("2024-01-01", periods=120, freq="D")
    values = rng.normal(0.0, 1.0, size=120)
    values[72:] += 1.0
    return pd.DataFrame({"signup_date": times, "f": values})


def test_a_row_exactly_at_the_outlier_limit_is_still_scored_and_one_beyond_it_is_not():
    from etl_benchmark.quality.drift import TemporalDriftDetector

    frame = _drifting_frame()
    detector = TemporalDriftDetector().fit(frame)
    spread = detector._z(frame).abs().max(axis=1)
    recent = detector._is_recent(frame)
    row = spread[recent].idxmax()
    detector.outlier_z = float(spread[row])
    assert detector.score(frame)[row] > 0.0
    detector.outlier_z = float(spread[row]) - 1e-9
    assert detector.score(frame)[row] == 0.0


def test_a_single_feature_gets_one_reconstruction_error_per_row_and_integer_flags():
    import numpy as np

    from etl_benchmark.quality.autoencoder import ReconstructionModel

    x = np.linspace(-2.0, 2.0, 40).reshape(-1, 1)
    model = ReconstructionModel(contamination=0.1, random_state=0, max_iter=50).fit(x)
    errors = model.decision_function(x)
    assert errors.shape == (40,)
    expected = (x[:, 0] - model.network_.predict(x)) ** 2
    assert np.allclose(errors, expected)
    flags = model.predict(x)
    assert flags.dtype.kind == "i" and set(flags.tolist()) <= {0, 1}
