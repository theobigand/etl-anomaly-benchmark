"""Design-only simulations of the cluster-level analysis and the batch alert budget (#153).

Synthetic data only: no detector is run and no benchmark outcome is read. The simulations
answer how the candidate primary analysis (the mean of per-cluster paired differences, equal
cluster weights, one test per comparison at the Holm level) behaves when its assumptions fail:
few clusters, unequal cluster sizes, heterogeneous source variances, bounded skewed differences
and residual dependence between clusters of one curator. They do not replace the owner decision.

The batch part gives the exact moments of the probability that a new observation alerts after
the registered interpolated empirical quantile threshold. The sample maximum is the only
threshold whose exceedance probability is Beta(1, n).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats


def false_alert_moments(n: int, level: float) -> dict[str, float]:
    """Mean and sd of P(new score > T) for T the linear-interpolated ``level`` quantile of n
    exchangeable continuous scores.

    With the order statistics U(j), U(j+1) of n uniforms (j = floor(level (n - 1)) + 1) and
    h the interpolation weight, T = (1 - h) U(j) + h U(j+1) on the uniform scale and the
    exceedance probability is 1 - T. Mean, variance and covariance of uniform order statistics
    are exact, so no simulation is needed.
    """
    position = level * (n - 1)
    j = int(np.floor(position)) + 1
    h = position - np.floor(position)
    scale = (n + 1) ** 2 * (n + 2)

    def var(i: int) -> float:
        return i * (n + 1 - i) / scale

    if h == 0 or j == n:
        weights, indices = [1.0], [j]
    else:
        weights, indices = [1.0 - h, h], [j, j + 1]
    mean = 1.0 - sum(w * i for w, i in zip(weights, indices, strict=True)) / (n + 1)
    variance = sum(w * w * var(i) for w, i in zip(weights, indices, strict=True))
    if len(indices) == 2:
        variance += 2 * weights[0] * weights[1] * j * (n + 1 - (j + 1)) / scale
    return {"mean": float(mean), "sd": float(np.sqrt(variance))}


def observed_rate_sd(n: int, level: float, test_units: int) -> float:
    """Sd of the observed false-alert rate on ``test_units`` independent test units: the
    threshold uncertainty plus the binomial noise given the threshold."""
    m = false_alert_moments(n, level)
    binomial = (m["mean"] * (1 - m["mean"]) - m["sd"] ** 2) / test_units
    return float(np.sqrt(m["sd"] ** 2 + binomial))


def alert_rate(validation: np.ndarray, level: float, new: np.ndarray) -> float:
    """Share of ``new`` scores strictly above the interpolated quantile of each validation row."""
    threshold = np.quantile(validation, level, axis=1, method="linear")[:, None]
    return float(np.mean(new > threshold))


def standardised_shape(shape: str, rng: np.random.Generator, size: tuple[int, ...]) -> np.ndarray:
    """Zero-mean, unit-sd noise: normal, or a bounded right-skewed scaled Beta(0.5, 3)."""
    if shape == "normal":
        return rng.standard_normal(size)
    if shape == "bounded":
        a, b = 0.5, 3.0
        mean = a / (a + b)
        sd = np.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
        return (rng.beta(a, b, size) - mean) / sd
    raise ValueError(f"unknown shape {shape!r}")


def simulate(
    n: int,
    sigma: float,
    delta: float,
    shape: str = "normal",
    heterogeneity: float = 0.0,
    size_noise: float = 0.0,
    curator_size: int = 1,
    icc: float = 0.0,
    reps: int = 1000,
    boot: int = 499,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, dict[str, float]]:
    """Rejection rate (alpha, two-sided, null mean 0) and coverage of the 1 - alpha interval of
    the true difference ``delta`` for four procedures on per-cluster differences.

    ``heterogeneity``: sd of the log of each cluster's variance multiplier (mean one).
    ``size_noise``: share of the variance that is sampling noise of unequal cluster sizes.
    ``curator_size`` and ``icc``: consecutive clusters sharing a curator effect with that
    intraclass correlation; ``t``, ``boot`` and ``perm`` ignore it, ``boot_curator`` resamples
    curators. The data of every procedure is one common draw.
    """
    rng = np.random.default_rng(seed)
    scale = np.exp(rng.normal(0, heterogeneity, (reps, n)) - heterogeneity**2 / 2)
    sizes = np.exp(rng.normal(0, 1.0, (reps, n)))
    sizes /= sizes.mean(axis=1, keepdims=True)
    spread = sigma * np.sqrt(scale * ((1 - size_noise) + size_noise / sizes))
    idio = standardised_shape(shape, rng, (reps, n)) * spread
    n_curators = int(np.ceil(n / curator_size))
    shared = np.repeat(rng.standard_normal((reps, n_curators)), curator_size, axis=1)[:, :n]
    data = delta + np.sqrt(1 - icc) * idio + np.sqrt(icc) * sigma * shared
    mean = data.mean(axis=1)
    half = stats.t.ppf(1 - alpha / 2, n - 1) * data.std(axis=1, ddof=1) / np.sqrt(n)
    return {
        "t": {
            "reject": _t_reject(data, alpha),
            "coverage": float(np.mean(np.abs(mean - delta) <= half)),
        },
        "boot": _boot(data, delta, boot, alpha, rng, None),
        "boot_curator": _boot(
            data, delta, boot, alpha, rng, curator_size if curator_size > 1 else None
        ),
        "perm": {"reject": _signflip(data, boot, alpha, rng)},
    }


def _t_reject(data: np.ndarray, alpha: float) -> float:
    p = stats.ttest_1samp(data, 0.0, axis=1).pvalue
    return float(np.mean(p < alpha))


def _boot(
    data: np.ndarray,
    delta: float,
    boot: int,
    alpha: float,
    rng: np.random.Generator,
    curator_size: int | None,
) -> dict[str, float]:
    reps, n = data.shape
    low = np.empty(reps)
    high = np.empty(reps)
    for r in range(reps):
        if curator_size:
            blocks = np.arange(n) // curator_size
            ids = np.unique(blocks)
            picks = rng.integers(0, len(ids), (boot, len(ids)))
            sums = np.array([data[r][blocks == b].sum() for b in ids])
            counts = np.array([(blocks == b).sum() for b in ids])
            est = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
        else:
            est = data[r][rng.integers(0, n, (boot, n))].mean(axis=1)
        low[r], high[r] = np.quantile(est, [alpha / 2, 1 - alpha / 2])
    return {
        "reject": float(np.mean((low > 0) | (high < 0))),
        "coverage": float(np.mean((low <= delta) & (delta <= high))),
    }


def _signflip(data: np.ndarray, boot: int, alpha: float, rng: np.random.Generator) -> float:
    reps, n = data.shape
    rejected = 0
    for r in range(reps):
        observed = abs(data[r].mean())
        signs = rng.choice([-1.0, 1.0], (boot, n))
        flipped = np.abs((signs * data[r]).mean(axis=1))
        rejected += (1 + np.sum(flipped >= observed)) / (1 + boot) <= alpha
    return float(rejected / reps)


#: scenario grid of the evidence file; every number is a hypothetical design input
SCENARIOS: list[dict[str, Any]] = [
    {"name": "few clusters, normal", "n": 16},
    {"name": "few clusters, bounded skewed", "n": 16, "shape": "bounded"},
    {
        "name": "heterogeneous variances and unequal sizes",
        "n": 40,
        "heterogeneity": 1.0,
        "size_noise": 0.5,
    },
    {"name": "bounded skewed", "n": 80, "shape": "bounded"},
    {"name": "residual curator dependence icc 0.2", "n": 80, "curator_size": 4, "icc": 0.2},
    {"name": "residual curator dependence icc 0.5", "n": 80, "curator_size": 4, "icc": 0.5},
]
SIGMA, EFFECT = 0.10, 0.05


def evidence(reps: int = 2000, boot: int = 999, seed: int = 2026) -> dict[str, Any]:
    rows = []
    for index, scenario in enumerate(SCENARIOS):
        params = {k: v for k, v in scenario.items() if k != "name"}
        row: dict[str, Any] = {"scenario": scenario["name"], **params}
        for label, delta in (("null", 0.0), ("effect_0.05", EFFECT)):
            for alpha_label, alpha in (("0.05", 0.05), ("0.0167", 0.05 / 3)):
                row[f"{label}@{alpha_label}"] = simulate(
                    sigma=SIGMA,
                    delta=delta,
                    reps=reps,
                    boot=boot,
                    alpha=alpha,
                    seed=seed + index,
                    **params,
                )
        rows.append(row)
    return {
        "note": "design-only synthetic simulation; sigma, effects and dependence are hypothetical",
        "reps": reps,
        "boot": boot,
        "sigma": SIGMA,
        "scenarios": rows,
        "batch_alert_budget": [
            {
                "validation_batches": n,
                **false_alert_moments(n, 0.95),
                "beta_1_n_mean_if_max": 1 / (n + 1),
            }
            for n in (16, 20, 21, 30, 40, 60, 100)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=2000)
    parser.add_argument("--boot", type=int, default=999)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = evidence(args.reps, args.boot, args.seed)
    args.output.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
