"""Paired inference over independent units: Holm correction, effect sizes, ranks (issues 78, 83).

The unit is the source group, never the problem or the seed. Values are one number per unit and
detector (``NaN`` where the detector did not run). Nothing here reads a file.
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
from scipy.stats import friedmanchisquare, kendalltau, rankdata, wilcoxon

DRAWS = 10_000
SEED = 2026
LEVEL = 0.95


def holm(p_values: list[float] | np.ndarray) -> np.ndarray:
    """Holm step-down adjusted p-values, in the order given, monotone and capped at 1."""
    p = np.asarray(p_values) * 1.0
    order = np.argsort(p)
    adjusted = np.empty(len(p))
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(p) - rank) * p[index])
        adjusted[index] = min(running, 1.0)
    return adjusted


def group_means(values: dict[str, float], groups: dict[str, str]) -> dict[str, float]:
    """Mean of the values of each group; NaN values are ignored, a group with none is dropped."""
    pooled: dict[str, list[float]] = {}
    for item, value in values.items():
        if not np.isnan(value):
            pooled.setdefault(groups[item], []).append(value)
    return {group: float(np.mean(v)) for group, v in sorted(pooled.items())}


def paired_effect(
    a: np.ndarray, b: np.ndarray, draws: int = DRAWS, seed: int = SEED
) -> dict[str, Any]:
    """Wilcoxon test and effect sizes of ``a - b`` over units where both are present."""
    keep = ~(np.isnan(a) | np.isnan(b))
    d = (a - b)[keep]
    n = int(keep.sum())
    out: dict[str, Any] = {"units": n}
    if n == 0:
        return {**out, "median_difference": float("nan"), "p": 1.0}
    nonzero = d[d != 0]
    p = 1.0 if len(nonzero) == 0 else float(wilcoxon(nonzero).pvalue)
    rng = np.random.default_rng(seed)
    medians = np.median(d[rng.integers(0, n, (draws, n))], axis=1)
    tail = (1 - LEVEL) / 2
    low, high = np.quantile(medians, [tail, 1 - tail])
    wins, losses = int((d > 0).sum()), int((d < 0).sum())
    return {
        **out,
        "median_difference": float(np.median(d)),
        "ci_low": float(low),
        "ci_high": float(high),
        "p": p,
        "probability_of_superiority": float((wins + 0.5 * (n - wins - losses)) / n),
        "rank_biserial": float((wins - losses) / n),
    }


def pairwise(table: dict[str, np.ndarray], draws: int = DRAWS) -> list[dict[str, Any]]:
    """Every ordered-once pair of detectors with Holm-adjusted p over all pairs."""
    rows = []
    for first, second in itertools.combinations(sorted(table), 2):
        rows.append({"a": first, "b": second, **paired_effect(table[first], table[second], draws)})
    adjusted = holm([r["p"] for r in rows])
    for i, row in enumerate(rows):
        row["p_holm"] = float(adjusted[i])
    return rows


def complete_matrix(
    table: dict[str, np.ndarray], coverage: float = 0.9
) -> tuple[list[str], np.ndarray]:
    """Detectors present on at least ``coverage`` of the units, over the units where all are."""

    names = sorted(m for m, v in table.items() if (~np.isnan(v)).mean() >= coverage)
    matrix = np.column_stack([table[m] for m in names])
    return names, matrix[~np.isnan(matrix).any(axis=1)]


def mean_ranks(matrix: np.ndarray) -> np.ndarray:
    """Mean rank of each column (1 is best, ties averaged) over the rows."""
    return np.mean([rankdata(-row) for row in matrix], axis=0)


def rank_intervals(matrix: np.ndarray, draws: int = DRAWS, seed: int = SEED) -> np.ndarray:
    """Percentile interval of the mean rank of each column, resampling rows (units)."""
    rng = np.random.default_rng(seed)
    ranks = np.array([rankdata(-row) for row in matrix])
    means = ranks[rng.integers(0, len(ranks), (draws, len(ranks)))].mean(axis=1)
    tail = (1 - LEVEL) / 2
    return np.quantile(means, [tail, 1 - tail], axis=0).T


def friedman(matrix: np.ndarray) -> dict[str, float]:
    result = friedmanchisquare(*matrix.T)
    return {
        "statistic": float(result.statistic),
        "p": float(result.pvalue),
        "units": int(len(matrix)),
        "detectors": int(matrix.shape[1]),
    }


def kendall(a: np.ndarray, b: np.ndarray) -> float:
    """Kendall tau-b between two rank vectors."""
    return float(kendalltau(a, b).statistic)
