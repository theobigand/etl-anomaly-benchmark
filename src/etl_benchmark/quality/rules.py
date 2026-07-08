"""Rule-based anomaly detectors.

Implemented:
    - :class:`ZScoreDetector` — flags rows where any numeric column
      exceeds the configured z-score threshold.
    - :class:`IQRDetector` — Tukey's fences on numeric columns.

The declarative Great Expectations detector lives in
:mod:`etl_benchmark.quality.gx`.
"""

from __future__ import annotations

from typing import Self

import numpy as np
import pandas as pd

from etl_benchmark.quality.base import Detector


class ZScoreDetector(Detector):
    name = "zscore"

    def __init__(self, threshold: float = 3.0, columns: list[str] | None = None) -> None:
        self.threshold = threshold
        self._user_columns = columns
        self._means: pd.Series | None = None
        self._stds: pd.Series | None = None

    def fit(self, df: pd.DataFrame) -> Self:
        cols = self._user_columns or df.select_dtypes(include=np.number).columns.tolist()
        self._means = df[cols].mean()
        self._stds = df[cols].std().replace(0, np.nan)
        return self

    def _zscores(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._means is None or self._stds is None:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")
        return (df[self._means.index] - self._means).abs() / self._stds

    def predict(self, df: pd.DataFrame) -> pd.Series:
        return self._zscores(df).gt(self.threshold).any(axis=1).fillna(False)

    def score(self, df: pd.DataFrame) -> pd.Series:
        # Worst standardized deviation across columns; NaN (constant column) -> 0.
        return self._zscores(df).max(axis=1).fillna(0.0)


class IQRDetector(Detector):
    """Tukey's fences: flag values outside ``[Q1 - k*IQR, Q3 + k*IQR]``."""

    name = "iqr"

    def __init__(self, multiplier: float = 1.5, columns: list[str] | None = None) -> None:
        self.multiplier = multiplier
        self._user_columns = columns
        self._lower: pd.Series | None = None
        self._upper: pd.Series | None = None
        self._scale: pd.Series | None = None

    def fit(self, df: pd.DataFrame) -> Self:
        cols = self._user_columns or df.select_dtypes(include=np.number).columns.tolist()
        q1 = df[cols].quantile(0.25)
        q3 = df[cols].quantile(0.75)
        iqr = q3 - q1
        self._lower = q1 - self.multiplier * iqr
        self._upper = q3 + self.multiplier * iqr
        # Column width used to normalize exceedances into a comparable score.
        self._scale = iqr.replace(0, np.nan)
        return self

    def _exceedance(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._lower is None or self._upper is None:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")
        cols = self._lower.index
        below = self._lower - df[cols]
        above = df[cols] - self._upper
        # How far outside the fence, in IQR units; <=0 when inside.
        return np.maximum(below, above).div(self._scale)

    def predict(self, df: pd.DataFrame) -> pd.Series:
        return self._exceedance(df).gt(0).any(axis=1).fillna(False)

    def score(self, df: pd.DataFrame) -> pd.Series:
        return self._exceedance(df).clip(lower=0).max(axis=1).fillna(0.0)
