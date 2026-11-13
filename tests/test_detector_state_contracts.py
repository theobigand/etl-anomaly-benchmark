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
