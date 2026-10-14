"""Evaluation metrics shared by the real and synthetic benchmarks."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(y, flags, scores) -> dict[str, float]:
    """Return held-out metrics; reject undefined or malformed evaluations.

    ``pr_auc`` is average precision, not trapezoidal PR area. Higher scores
    must indicate more anomalous observations.
    """
    y = np.asarray(y)
    flags = np.asarray(flags)
    scores = np.asarray(scores)
    if y.ndim != 1 or flags.ndim != 1 or scores.ndim != 1:
        raise ValueError("labels, flags and scores must be one-dimensional")
    if len(y) == 0 or len(y) != len(flags) or len(y) != len(scores):
        raise ValueError("labels, flags and scores must have equal nonzero length")
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("ROC-AUC and average precision require both binary classes")
    if flags.dtype.kind != "b":
        raise ValueError("flags must be boolean")
    if not np.isfinite(scores.astype(float)).all():
        raise ValueError("scores must be finite")
    return {
        "precision": float(precision_score(y, flags, zero_division=0)),
        "recall": float(recall_score(y, flags)),
        "f1": float(f1_score(y, flags)),
        "roc_auc": float(roc_auc_score(y, scores)),
        "pr_auc": float(average_precision_score(y, scores)),
        "flagged_pct": 100.0 * float(np.mean(flags)),
    }
