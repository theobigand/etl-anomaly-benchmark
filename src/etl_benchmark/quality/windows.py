"""Causal sliding windows for sequence models.

A sequence detector scores one event from a window of the rows that precede
it. The window of event ``k`` holds rows ``k - size + 1 .. k`` in time order,
so it never contains a later row. Rows before the start of the partition are
filled by repeating the first row. Windows are built one partition at a time,
which keeps a test window from reaching into the training rows. Events with
equal timestamps keep their input order.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from etl_benchmark.quality.window_drift import _numeric, _times


def causal_windows(
    frame: pd.DataFrame, time_column: str, columns: Sequence[str], size: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(windows, order)``.

    ``windows`` has shape ``(n_events, size, n_features)`` in time order and
    ``order[k]`` is the position, in ``frame``, of the event closing window
    ``k``.
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("window size must be a positive integer")
    times = _times(frame, time_column)
    values = _numeric(frame, columns).to_numpy(dtype=float)
    order = np.argsort(times.to_numpy(), kind="stable")
    ordered = values[order]
    positions = np.arange(len(ordered))[:, None] + np.arange(1 - size, 1)[None, :]
    return ordered[np.clip(positions, 0, None)], order


def scores_to_events(scores: np.ndarray, order: np.ndarray, index: pd.Index) -> pd.Series:
    """Give each window score back to the event that closes it."""
    if len(scores) != len(order):
        raise ValueError("scores and positions must have the same length")
    aligned = np.empty(len(scores), dtype=float)
    aligned[order] = scores
    return pd.Series(aligned, index=index)
