"""Common interface for all anomaly detectors.

Rule-based, classical ML and deep learning detectors share the same
``fit`` / ``predict`` contract, which mirrors PyOD's ``BaseDetector``
to ease later integration of ``pyod`` estimators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self

import pandas as pd


class Detector(ABC):
    name: str

    @abstractmethod
    def fit(self, df: pd.DataFrame) -> Self:
        """Learn detector parameters from ``df``."""

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> pd.Series:
        """Return a boolean Series: ``True`` where the row is anomalous."""

    def fit_predict(self, df: pd.DataFrame) -> pd.Series:
        return self.fit(df).predict(df)
