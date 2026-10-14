import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest
from sklearn.exceptions import UndefinedMetricWarning

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

import run_benchmark  # noqa: E402


def test_golden_metrics_use_continuous_scores():
    metrics = run_benchmark.compute_metrics(
        np.array([0, 1, 0, 1]),
        np.array([False, True, True, False]),
        np.array([0.1, 0.9, 0.8, 0.2]),
    )
    assert metrics == pytest.approx(
        {
            "precision": 0.5,
            "recall": 0.5,
            "f1": 0.5,
            "roc_auc": 0.75,
            "pr_auc": 5 / 6,
            "flagged_pct": 50.0,
        }
    )


@pytest.mark.parametrize(
    ("labels", "flags", "scores"),
    [
        ([], [], []),
        ([0, 0], [False, False], [0.1, 0.2]),
        ([1, 1], [True, False], [0.1, 0.2]),
        ([0, 1], [False], [0.1, 0.9]),
        ([0, 1], [False, True], [0.1, float("nan")]),
    ],
)
def test_undefined_metrics_fail_explicitly(labels, flags, scores):
    with pytest.raises(ValueError):
        run_benchmark.compute_metrics(np.array(labels), np.array(flags), np.array(scores))


@pytest.mark.parametrize(
    ("labels", "flags", "scores"),
    [
        ([[0], [1]], [False, True], [0.1, 0.9]),
        ([0, 1], [[False], [True]], [0.1, 0.9]),
        ([0, 1], [False, True], [[0.1], [0.9]]),
        ([0, 1], [False, True, False], [0.1, 0.9]),
        ([0, 1], [False, True], [0.1, 0.9, 0.2]),
    ],
)
def test_metric_vectors_have_matching_flat_shape(labels, flags, scores):
    with pytest.raises(ValueError):
        run_benchmark.compute_metrics(labels, flags, scores)


def test_precision_with_no_flags_is_zero():
    metrics = run_benchmark.compute_metrics([0, 1], [False, False], [0.1, 0.9])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0


def test_integer_flags_are_rejected_even_when_they_are_zero_or_one():
    with pytest.raises(ValueError, match="boolean"):
        run_benchmark.compute_metrics([0, 1], [0, 1], [0.1, 0.9])


def _message(text):
    return f"^{re.escape(text)}$"


def test_invalid_metric_inputs_report_the_failed_contract():
    shape = _message("labels, flags and scores must be one-dimensional")
    length = _message("labels, flags and scores must have equal nonzero length")
    with pytest.raises(ValueError, match=shape):
        run_benchmark.compute_metrics([[0], [1]], [False, True], [0.1, 0.9])
    with pytest.raises(ValueError, match=length):
        run_benchmark.compute_metrics([0, 1], [False], [0.1, 0.9])
    with pytest.raises(ValueError, match=length):
        run_benchmark.compute_metrics([0, 1], [False, True], [0.1])
    with pytest.raises(ValueError, match=length):
        run_benchmark.compute_metrics([], [False], [0.1])
    with pytest.raises(
        ValueError, match=_message("ROC-AUC and average precision require both binary classes")
    ):
        run_benchmark.compute_metrics([1], [True], [0.9])
    with pytest.raises(ValueError, match=_message("flags must be boolean")):
        run_benchmark.compute_metrics([0, 1], [0, 1], [0.1, 0.9])
    with pytest.raises(ValueError, match=_message("scores must be finite")):
        run_benchmark.compute_metrics([0, 1], [False, True], [0.1, float("inf")])


def test_no_positive_predictions_do_not_emit_undefined_metric_warnings():
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        result = run_benchmark.compute_metrics([0, 1], [False, False], [0.1, 0.9])
    assert result["precision"] == 0.0
    assert not any(issubclass(item.category, UndefinedMetricWarning) for item in recorded)
