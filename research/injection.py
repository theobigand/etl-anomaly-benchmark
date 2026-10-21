"""Typed anomaly injection on a numeric carrier table.

The six types of the synthetic benchmark are adapted to arbitrary numeric columns. The carrier is
the clean (normal-class) part of a real dataset reduced to its continuous columns; the protocol
and the magnitudes are those written in verification/typed_injection.md before any result.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from etl_benchmark import synthetic

ANOMALY_TYPES: list[str] = list(synthetic.ANOMALY_TYPES)
MIN_DISTINCT, MIN_COLUMNS, MIN_ROWS, MAX_ROWS = 10, 4, 3000, 20_000
RATE, SEVERITY = 0.03, 1.0
META = ("t", "group_id", "anomaly", "anomaly_type")
_BASE = pd.Timestamp("2020-01-01")
_SENTINEL, _SCALE = -999.0, 1000.0


class NotEligible(Exception):
    """The table cannot carry the typed injection under the pre-registered rule."""


def continuous_columns(frame: pd.DataFrame) -> list[str]:
    return [
        c
        for c in frame.columns
        if pd.api.types.is_numeric_dtype(frame[c])
        and not pd.api.types.is_bool_dtype(frame[c])
        and frame[c].nunique() >= MIN_DISTINCT
    ]


def FEATURES_OF(frame: pd.DataFrame) -> list[str]:  # noqa: N802 - reads like a constant table
    return [c for c in frame.columns if c not in META]


def prepare(frame: pd.DataFrame, seed: int, cap: int = MAX_ROWS) -> tuple[pd.DataFrame, dict]:
    columns = continuous_columns(frame)
    if len(columns) < MIN_COLUMNS:
        raise NotEligible(f"only {len(columns)} continuous columns")
    table = frame[columns].astype(float)
    report: dict[str, Any] = {"rows_in": len(table), "columns": columns}
    complete = table.dropna()
    report["rows_incomplete_dropped"] = len(table) - len(complete)
    unique = complete.drop_duplicates()
    report["duplicates_dropped"] = len(complete) - len(unique)
    if len(unique) < MIN_ROWS:
        raise NotEligible(f"only {len(unique)} rows after cleaning")
    if len(unique) > cap:
        unique = unique.sample(n=cap, random_state=seed)
    report["rows_out"] = len(unique)
    return unique.reset_index(drop=True), report


def _pair(ref: pd.DataFrame) -> tuple[str, str, float]:
    corr = ref.corr().abs().to_numpy(copy=True)
    np.fill_diagonal(corr, -1)
    i, j = np.unravel_index(np.argmax(corr), corr.shape)
    return ref.columns[i], ref.columns[j], float(ref.corr().iloc[i, j])


def inject(
    clean: pd.DataFrame, seed: int, rate: float = RATE, severity: float = SEVERITY
) -> pd.DataFrame:
    n, cols = len(clean), list(clean.columns)
    k = max(round(rate * n), 15)
    if 6 * k > n:
        raise NotEligible("too few rows for six anomaly groups")
    rng = np.random.default_rng(seed)
    mean, std = clean.mean(), clean.std()
    pop = clean.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    pop["group_id"] = np.arange(n)
    pop["anomaly_type"] = "clean"
    hours = rng.permutation(n)
    pop["t"] = _BASE + pd.to_timedelta(hours, unit="h")
    n_clean = n - 5 * k
    blocks = {
        name: pop.iloc[n_clean + i * k : n_clean + (i + 1) * k].copy()
        for i, name in enumerate(
            ["missing_value", "univariate_outlier", "multivariate_outlier", "temporal_drift"]
            + ["invalid_format"]
        )
    }
    for pos in range(k):
        # missing: one or two cells of the continuous columns
        row = blocks["missing_value"]
        for col in rng.choice(cols, size=int(rng.integers(1, 3)), replace=False):
            row.iloc[pos, row.columns.get_loc(col)] = np.nan
        # univariate: one column far from the clean mean
        row = blocks["univariate_outlier"]
        col = rng.choice(cols)
        sign = rng.choice([-1.0, 1.0])
        row.iloc[pos, row.columns.get_loc(col)] = (
            mean[col] + sign * rng.uniform(6, 12) * severity * std[col]
        )
    a, b, corr = _pair(clean)
    hi_q, lo_q = min(1 - 0.03 / severity, 0.999), max(0.03 / severity, 0.001)
    hi, lo = (
        {c: clean[c].quantile(hi_q) for c in (a, b)},
        {c: clean[c].quantile(lo_q) for c in (a, b)},
    )
    block = blocks["multivariate_outlier"]
    for pos in range(k):
        up_first = (pos % 2 == 0) == (corr > 0)
        block.iloc[pos, block.columns.get_loc(a)] = hi[a] if up_first else lo[a]
        block.iloc[pos, block.columns.get_loc(b)] = lo[b] if up_first else hi[b]
    drift = blocks["temporal_drift"]
    shifted = list(rng.choice(cols, size=3, replace=False))
    for col in shifted:
        drift[col] = drift[col] + 1.5 * severity * std[col]
    drift["t"] = _BASE + pd.to_timedelta(rng.uniform(0.9 * n, n, size=k), unit="h")
    positive = [c for c in cols if clean[c].min() >= 0]
    invalid = blocks["invalid_format"]
    for pos in range(k):
        kind = rng.choice(["sign", "sentinel", "scale"] if positive else ["scale"])
        col = rng.choice(positive if kind != "scale" else cols)
        at = invalid.columns.get_loc(col)
        value = invalid.iloc[pos, at]
        invalid.iloc[pos, at] = (
            -abs(value) - 1e-9
            if kind == "sign"
            else _SENTINEL
            if kind == "sentinel"
            else value * _SCALE
        )
    parts = [pop.iloc[:n_clean]]
    for name, block in blocks.items():
        block["anomaly_type"] = name
        parts.append(block)
    source = pop.iloc[:n_clean].sample(n=k, random_state=seed).copy()
    source["anomaly_type"] = "duplicate"
    parts.append(source)
    out = pd.concat(parts)
    out["anomaly"] = out["anomaly_type"] != "clean"
    out = out.sample(frac=1.0, random_state=seed, ignore_index=True)
    return out[[*cols, "t", "group_id", "anomaly", "anomaly_type"]]
