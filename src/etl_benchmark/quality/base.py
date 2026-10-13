"""Common interface for all anomaly detectors.

Rule-based, classical ML and deep learning detectors share the same
``fit`` / ``predict`` contract, which mirrors PyOD's ``BaseDetector``
to ease later integration of ``pyod`` estimators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self

import numpy as np
import pandas as pd


def numeric_features(df: pd.DataFrame, columns: list[str], *, training: bool) -> pd.DataFrame:
    """Reject unusable numeric inputs before a detector computes statistics."""
    if not columns:
        raise ValueError("at least one numeric feature is required")
    missing = [column for column in columns if column not in df]
    if missing:
        raise ValueError(f"missing feature columns: {missing}")
    selected = df[columns]
    if any(not pd.api.types.is_numeric_dtype(dtype) for dtype in selected.dtypes):
        raise ValueError("feature columns must be numeric")
    values = selected.to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError("nonfinite feature value")
    if training and np.isnan(values).all(axis=0).any():
        raise ValueError("all-missing training feature")
    return selected


class Detector(ABC):
    name: str

    @abstractmethod
    def fit(self, df: pd.DataFrame) -> Self:
        """Learn detector parameters from ``df``."""

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> pd.Series:
        """Return a boolean Series: ``True`` where the row is anomalous."""

    def score(self, df: pd.DataFrame) -> pd.Series:
        """Continuous anomaly score, higher meaning more anomalous.

        Used for threshold-independent metrics (ROC-AUC, PR-AUC). The
        default derives a 0/1 score from :meth:`predict`; detectors that
        can expose a graded score should override this.
        """
        return self.predict(df).astype(float)

    def fit_predict(self, df: pd.DataFrame) -> pd.Series:
        return self.fit(df).predict(df)
