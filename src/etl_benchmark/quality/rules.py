"""Rule-based anomaly detectors.

Implemented:
    - :class:`ZScoreDetector` — flags rows where any numeric column
      exceeds the configured z-score threshold.

Planned (séance 2):
    - ``IQRDetector`` — Tukey's fences on numeric columns.
    - ``GreatExpectationsDetector`` — wraps a GX expectation suite.
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

    def predict(self, df: pd.DataFrame) -> pd.Series:
        if self._means is None or self._stds is None:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")
        z = (df[self._means.index] - self._means).abs() / self._stds
        return z.gt(self.threshold).any(axis=1).fillna(False)
