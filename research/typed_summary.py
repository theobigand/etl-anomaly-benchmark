"""Pooled summary of the per-dataset typed heatmaps and the pre-registered hypothesis checks.

The thresholds are those of verification/typed_injection.md, written before any result.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

STRUCTURAL = ("missing_value", "duplicate", "invalid_format")
ML = ("isolation_forest", "lof", "ocsvm")


def pooled(data: dict[str, pd.DataFrame], resamples: int = 2000, seed: int = 0):
    """Median over datasets with a bootstrap interval resampling the datasets."""
    stack = np.stack([m.to_numpy(dtype=float) for m in data.values()])
    rng = np.random.default_rng(seed)
    boot = np.stack(
        [
            np.nanmedian(stack[rng.integers(0, len(stack), len(stack))], axis=0)
            for _ in range(resamples)
        ]
    )
    first = next(iter(data.values()))

    def frame(a: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(a, index=first.index, columns=first.columns)

    return {
        "median": frame(np.nanmedian(stack, axis=0)),
        "low": frame(np.nanpercentile(boot, 2.5, axis=0)),
        "high": frame(np.nanpercentile(boot, 97.5, axis=0)),
    }


def _mean_rank_correlation(vectors: list[np.ndarray]) -> float:
    values = []
    for a, b in combinations(vectors, 2):
        if np.ptp(a) == 0 or np.ptp(b) == 0:
            continue
        values.append(float(spearmanr(a, b).statistic))
    return float(np.mean(values)) if values else float("nan")


def stability(data: dict[str, pd.DataFrame]) -> dict[str, Any]:
    matrices = list(data.values())
    overall = _mean_rank_correlation([m.to_numpy(dtype=float).ravel() for m in matrices])
    per_type = {
        kind: _mean_rank_correlation([m[kind].to_numpy(dtype=float) for m in matrices])
        for kind in matrices[0].columns
    }
    return {"overall": overall, "per_type": per_type}


def _cell(data: dict[str, pd.DataFrame], method: str, kind: str) -> np.ndarray:
    return np.array([m.loc[method, kind] for m in data.values()], dtype=float)


def hypotheses(data: dict[str, pd.DataFrame], n_columns: dict[str, int]) -> dict[str, Any]:
    med = lambda method, kind: float(np.nanmedian(_cell(data, method, kind)))  # noqa: E731
    out: dict[str, Any] = {}
    ge_min = float(np.nanmin(_cell(data, "great_expectations", "missing_value")))
    others_dup = {
        m: float(np.nanmax(_cell(data, m, "duplicate")))
        for m in next(iter(data.values())).index
        if m != "transform_dedup"
    }
    uni = {m: med(m, "univariate_outlier") for m in ("zscore", "iqr", *ML)}
    out["H1"] = {
        "holds": ge_min >= 0.9 and max(others_dup.values()) < 0.9 and min(uni.values()) > 0.7,
        "ge_missing_min": ge_min,
        "other_duplicate_max": max(others_dup.values()),
        "univariate_median": uni,
    }
    multi = {
        m: med(m, "multivariate_outlier") for m in ("isolation_forest", "ocsvm", "zscore", "iqr")
    }
    gap = min(multi["isolation_forest"], multi["ocsvm"]) - max(multi["zscore"], multi["iqr"])
    out["H2"] = {
        "holds": gap >= 0.4 and max(multi["zscore"], multi["iqr"]) < 0.2,
        "median": multi,
        "gap": gap,
    }
    methods = next(iter(data.values())).index
    drift = {m: med(m, "temporal_drift") for m in methods}
    out["H3"] = {"holds": max(drift.values()) < 0.5, "median": drift}
    s = stability(data)
    hard = max(s["per_type"]["multivariate_outlier"], s["per_type"]["temporal_drift"])
    easy = min(s["per_type"][k] for k in STRUCTURAL)
    out["H4"] = {"holds": bool(s["overall"] >= 0.7 and hard < easy), "stability": s}
    names = [n for n in data if n in n_columns]
    rho = spearmanr(
        [n_columns[n] for n in names],
        [data[n].loc["isolation_forest", "univariate_outlier"] for n in names],
    ).statistic
    out["H5"] = {"holds": bool(rho < 0), "rho": float(rho)}
    return out
