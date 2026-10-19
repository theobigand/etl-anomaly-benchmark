"""Paired bootstrap, by blocks of time, of the average-precision difference of two scorers."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ORIGIN = pd.Timestamp("1970-01-01", tz="UTC")


def paired_block_bootstrap(y, scores_a, scores_b, times, block_seconds, resamples, seed):
    """Difference ``AP(a) - AP(b)`` with a 95 % percentile interval; blocks shared by a and b."""
    y = np.asarray(y)
    a, b = np.asarray(scores_a, dtype=float), np.asarray(scores_b, dtype=float)
    if not len(y) == len(a) == len(b) == len(times):
        raise ValueError("labels, scores and times must have equal length")
    if y.min() == y.max():
        raise ValueError("both classes are required")
    seconds = (pd.to_datetime(times, utc=True) - ORIGIN).dt.total_seconds()
    blocks = (seconds // block_seconds).astype(int).to_numpy()
    members = {k: np.flatnonzero(blocks == k) for k in np.unique(blocks)}
    keys = list(members)
    rng = np.random.default_rng(seed)
    gaps = []
    for _ in range(resamples):
        index = np.concatenate([members[keys[k]] for k in rng.choice(len(keys), len(keys))])
        if y[index].min() != y[index].max():
            gaps.append(
                average_precision_score(y[index], a[index])
                - average_precision_score(y[index], b[index])
            )
    low, high = np.percentile(gaps, [2.5, 97.5])
    return {
        "ap_a": float(average_precision_score(y, a)),
        "ap_b": float(average_precision_score(y, b)),
        "difference": float(average_precision_score(y, a) - average_precision_score(y, b)),
        "ci_low": float(low),
        "ci_high": float(high),
        "resamples_used": len(gaps),
    }
