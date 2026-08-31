"""A time-aware detector for distributional drift.

The other detectors ignore the order of the rows. This one uses a
timestamp column. In :meth:`fit` it learns a per-feature baseline from the
oldest ``reference_frac`` of the rows. In :meth:`score` it measures how
far the *recent* window's mean has moved from that baseline, on the
features that actually moved (the window drift ``w``), and, for each
recent row, how strongly the row leans in the same direction. A row
scores high only when the window has drifted *and* the row contributes to
that drift; a row that a single feature makes a gross outlier is
excluded, so this detector stays out of the univariate detectors' lane.

Injected drift is subtle on purpose: the shifted values stay inside the
global range, and after dilution by the many clean recent rows the window
shift is only about a tenth of a standard deviation. At that magnitude
this detector, like every other, recovers almost none of it, which is the
point: drift is a windowed-monitoring problem, not a per-row one. The
severity sweep shows its recall climbing once the injected shift is a few
times larger.

On a dataset without the timestamp column the detector fits to a silent
no-op, so it can sit in a shared detector list without special-casing.
"""

from __future__ import annotations

from typing import Self

import numpy as np
import pandas as pd

from etl_benchmark.quality.base import Detector


class TemporalDriftDetector(Detector):
    name = "drift"

    def __init__(
        self,
        time_column: str = "signup_date",
        columns: list[str] | None = None,
        reference_frac: float = 0.6,
        threshold: float = 0.35,
        outlier_z: float = 5.0,
    ) -> None:
        self.time_column = time_column
        self._user_columns = columns
        self.reference_frac = reference_frac
        self.threshold = threshold
        self.outlier_z = outlier_z
        self._fitted = False
        self._active = False
        self._cutoff: object | None = None
        self._means: pd.Series | None = None
        self._stds: pd.Series | None = None

    def fit(self, df: pd.DataFrame) -> Self:
        self._fitted = True
        if self.time_column not in df.columns:
            self._active = False
            return self

        self._active = True
        order = df[self.time_column].sort_values()
        cut = min(max(int(len(order) * self.reference_frac), 1), len(order) - 1)
        self._cutoff = order.iloc[cut]
        reference = df.loc[order.index[:cut]]

        cols = self._user_columns or reference.select_dtypes(include=np.number).columns.tolist()
        self._means = reference[cols].mean()
        self._stds = reference[cols].std().replace(0, np.nan)
        return self

    def _guard(self) -> None:
        if not self._fitted:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")

    def _z(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = self._means.index
        return (df[cols] - self._means) / self._stds

    def _is_recent(self, df: pd.DataFrame) -> pd.Series:
        return df[self.time_column] >= self._cutoff

    def _row_score(self, df: pd.DataFrame) -> pd.Series:
        z = self._z(df)
        recent = self._is_recent(df)

        window = z.loc[recent]
        if len(window) < 20:
            return pd.Series(0.0, index=df.index)

        shift = window.mean()  # per-feature mean shift of the recent window, in ref-std units
        moved = shift.abs() > 0.03  # features that actually drifted
        if not moved.any():
            return pd.Series(0.0, index=df.index)
        w = float(shift[moved].abs().max())
        direction = np.sign(shift[moved])

        # how strongly each row leans in the drift direction, on the drifted features only
        lean = (z.loc[:, moved.index[moved]] * direction).clip(0.0, 4.0).mean(axis=1)
        gross = z.abs().max(axis=1) > self.outlier_z  # leave single-feature outliers to others
        row = w * lean
        row[gross] = 0.0
        # keep a faint signal on non-recent rows so the ranking is still ordered
        return (row * np.where(recent, 1.0, 0.2)).fillna(0.0)

    def predict(self, df: pd.DataFrame) -> pd.Series:
        self._guard()
        if not self._active:
            return pd.Series(False, index=df.index)
        return (self._row_score(df) > self.threshold) & self._is_recent(df)

    def score(self, df: pd.DataFrame) -> pd.Series:
        self._guard()
        if not self._active:
            return pd.Series(0.0, index=df.index)
        return self._row_score(df)
