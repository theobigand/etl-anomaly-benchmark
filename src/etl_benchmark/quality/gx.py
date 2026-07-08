"""Declarative anomaly detection with Great Expectations (GX 1.x API).

Where the statistical rules in :mod:`etl_benchmark.quality.rules` reason
over distributions, this detector encodes a small *expectation suite* — a
declarative contract the data is supposed to satisfy. A row is flagged as
anomalous when it violates at least one expectation.

The default suite learned in :meth:`fit` is:
    - ``expect_column_values_to_not_be_null`` on every column;
    - ``expect_column_values_to_be_between`` on each numeric column, with
      bounds taken from the ``bounds_quantiles`` percentiles of the fit data.

Using inner quantiles (rather than the absolute min/max) turns the range
check into a usable outlier rule instead of a no-op when fit and predict
run on the same frame.

Tested against great_expectations 1.18.
"""

from __future__ import annotations

from typing import Self

import numpy as np
import pandas as pd

from etl_benchmark.quality.base import Detector

_ROW_ID = "__row_id__"


class GreatExpectationsDetector(Detector):
    name = "great_expectations"

    def __init__(
        self,
        columns: list[str] | None = None,
        bounds_quantiles: tuple[float, float] = (0.001, 0.999),
        check_nulls: bool = True,
    ) -> None:
        self.columns = columns
        self.bounds_quantiles = bounds_quantiles
        self.check_nulls = check_nulls
        self._null_columns: list[str] = []
        self._bounds: dict[str, tuple[float, float]] = {}
        self._n_expectations: int = 0

    def fit(self, df: pd.DataFrame) -> Self:
        numeric = self.columns or df.select_dtypes(include=np.number).columns.tolist()
        self._null_columns = list(df.columns) if self.check_nulls else []

        lo_q, hi_q = self.bounds_quantiles
        self._bounds = {}
        for col in numeric:
            lo = df[col].quantile(lo_q)
            hi = df[col].quantile(hi_q)
            if pd.notna(lo) and pd.notna(hi) and lo < hi:
                self._bounds[col] = (float(lo), float(hi))

        self._n_expectations = len(self._null_columns) + len(self._bounds)
        return self

    def _failures_per_row(self, df: pd.DataFrame) -> pd.Series:
        """Number of violated expectations for each row (index-aligned)."""
        if self._n_expectations == 0:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")

        # Import lazily so importing the package never pulls in GX.
        import great_expectations as gx
        from great_expectations import expectations as gxe

        work = df.reset_index(drop=True)
        work[_ROW_ID] = work.index

        context = gx.get_context(mode="ephemeral")
        batch = (
            context.data_sources.add_pandas(name="pandas")
            .add_dataframe_asset(name="asset")
            .add_batch_definition_whole_dataframe(name="batch")
            .get_batch(batch_parameters={"dataframe": work})
        )
        result_format = {"result_format": "COMPLETE", "unexpected_index_column_names": [_ROW_ID]}

        failures = np.zeros(len(work), dtype=np.int64)
        expectations = [
            gxe.ExpectColumnValuesToNotBeNull(column=col) for col in self._null_columns
        ] + [
            gxe.ExpectColumnValuesToBeBetween(column=col, min_value=lo, max_value=hi)
            for col, (lo, hi) in self._bounds.items()
        ]

        for exp in expectations:
            res = batch.validate(exp, result_format=result_format).result
            for row in res.get("unexpected_index_list") or []:
                failures[int(row[_ROW_ID])] += 1

        return pd.Series(failures, index=df.index)

    def predict(self, df: pd.DataFrame) -> pd.Series:
        return self._failures_per_row(df) > 0

    def score(self, df: pd.DataFrame) -> pd.Series:
        # Fraction of the suite each row violates: a graded severity in [0, 1].
        return self._failures_per_row(df) / self._n_expectations
