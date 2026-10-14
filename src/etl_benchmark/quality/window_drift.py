"""Chronological window monitoring, separate from row-level detectors."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def _times(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        raise ValueError(f"missing timestamp column {column!r}")
    try:
        times = pd.to_datetime(frame[column], utc=True, format="mixed")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid timestamp") from exc
    if times.isna().any():
        raise ValueError("missing timestamp")
    return times


def _numeric(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    if not columns or any(column not in frame for column in columns):
        raise ValueError("missing feature column")
    values = frame[list(columns)]
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in values.dtypes):
        raise ValueError("feature columns must be numeric")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("feature columns must be finite")
    return values


class WindowDriftMonitor:
    """Score complete future windows against a fixed training baseline.

    This is a distributional alert, not a per-row anomaly detector. Equal
    timestamps stay together, so each window may contain more than the
    requested minimum number of rows.
    """

    def __init__(
        self,
        time_column: str,
        columns: Sequence[str],
        *,
        window_size: int = 20,
        threshold: float = 2.0,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least two")
        if not np.isfinite(threshold) or threshold <= 0:
            raise ValueError("threshold must be positive and finite")
        self.time_column = time_column
        self.columns = tuple(columns)
        self.window_size = window_size
        self.threshold = threshold
        self.reference_end: pd.Timestamp | None = None
        self._mean: pd.Series | None = None
        self._scale: pd.Series | None = None

    def fit(self, reference: pd.DataFrame) -> WindowDriftMonitor:
        if len(reference) < 2:
            raise ValueError("reference needs at least two rows")
        times = _times(reference, self.time_column)
        values = _numeric(reference, self.columns)
        self.reference_end = times.max()
        self._mean = values.mean()
        self._scale = values.std(ddof=0).replace(0.0, 1.0)
        return self

    def evaluate(self, future: pd.DataFrame) -> pd.DataFrame:
        if self.reference_end is None or self._mean is None or self._scale is None:
            raise RuntimeError("monitor not fitted")
        times = _times(future, self.time_column)
        values = _numeric(future, self.columns)
        if not len(future):
            raise ValueError("future period is empty")
        if times.min() <= self.reference_end:
            raise ValueError("future period overlaps the reference")

        ordered = values.copy()
        ordered["_event_time"] = times.to_numpy()
        ordered = ordered.sort_values(["_event_time", *self.columns])
        rows = []
        groups = []
        count = 0
        for _, group in ordered.groupby("_event_time"):
            groups.append(group)
            count += len(group)
            if count < self.window_size:
                continue
            window = pd.concat(groups)
            shift = (window[list(self.columns)].mean() - self._mean) / self._scale
            score = float(shift.abs().max())
            rows.append(
                {
                    "window_start": window["_event_time"].min(),
                    "window_end": window["_event_time"].max(),
                    "n_rows": count,
                    "score": score,
                    "alert": score > self.threshold,
                }
            )
            groups = []
            count = 0
        return pd.DataFrame(
            rows, columns=["window_start", "window_end", "n_rows", "score", "alert"]
        )


def event_metrics(windows: pd.DataFrame, change_time: pd.Timestamp) -> dict:
    """Report window-level detection delay and pre-change false alarms."""
    if windows.empty or not {"window_end", "alert"}.issubset(windows):
        raise ValueError("window results are required")
    if not pd.api.types.is_bool_dtype(windows["alert"]):
        raise ValueError("alert must be boolean")
    cutoff = pd.Timestamp(change_time)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    ends = pd.to_datetime(windows["window_end"], utc=True)
    before = ends < cutoff
    after_alert = ends[(~before) & windows["alert"]]
    first = after_alert.min()  # NaT when no window alerted after the change
    return {
        "false_alarm_rate": float(windows.loc[before, "alert"].mean()),  # NaN without windows
        "detected": bool(not pd.isna(first)),
        "detection_delay": first - cutoff,
    }
