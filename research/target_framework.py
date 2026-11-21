"""Design-only calculations for the number of independent source groups (no detector is run).

Everything here uses hypothetical parameters supplied by the caller: the between-source standard
deviation of a paired performance difference (sigma), the smallest difference worth detecting
(delta) and a design effect or intra-cluster correlation for sources that share a domain, schema
or curator. The numbers are planning illustrations, not empirical estimates; the variance pilot
(T424) is what replaces the assumed sigma.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np
from scipy import stats


def normal_factor(alpha: float, power: float) -> float:
    """(z_{1-alpha/2} + z_power)^2: the 7.85 of the design decision for alpha 0.05, power 0.80."""
    return float((stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) ** 2)


def t_quantile(p: float, df: float) -> float:
    return float(stats.t.ppf(p, df))


def _check(sigma: float, delta: float) -> None:
    if sigma <= 0 or delta <= 0:
        raise ValueError("sigma and delta must be positive")


def z_sources(
    sigma: float, delta: float, alpha: float = 0.05, power: float = 0.80, comparisons: int = 1
) -> float:
    """Normal-approximation number of independent sources (not rounded) for a paired comparison."""
    _check(sigma, delta)
    return normal_factor(alpha / comparisons, power) * (sigma / delta) ** 2


def paired_power(n: int, sigma: float, delta: float, alpha: float = 0.05) -> float:
    """Power of a two-sided paired t test on ``n`` source-level differences (non-central t)."""
    if n < 2:
        return 0.0
    df = n - 1
    cutoff = stats.t.ppf(1 - alpha / 2, df)
    shift = delta / (sigma / math.sqrt(n))
    upper = stats.nct.sf(cutoff, df, shift)
    lower = stats.nct.cdf(-cutoff, df, shift)
    # for a large shift the tails are tiny and the routines can return nan: treat that as 0 or 1
    upper = 1.0 if not np.isfinite(upper) else upper
    return float(upper + (lower if np.isfinite(lower) else 0.0))


def minimum_detectable_delta(
    n: float, sigma: float, alpha: float = 0.05, power: float = 0.80
) -> float:
    """Smallest paired difference detected with the given power by ``n`` independent sources."""
    if n < 2:
        raise ValueError("at least 2 sources are needed")
    low, high = 0.0, 10.0 * sigma
    for _ in range(60):
        mid = (low + high) / 2
        if paired_power(math.floor(n), sigma, mid, alpha) >= power:
            high = mid
        else:
            low = mid
    return math.ceil(high * 10_000) / 10_000  # rounded up so the power is still reached


def design_effect(cluster_size: float, icc: float) -> float:
    """Variance inflation 1 + (m - 1) * icc for sources that come in clusters of size m."""
    return 1.0 + (cluster_size - 1.0) * icc


def paired_sources(
    sigma: float,
    delta: float,
    alpha: float = 0.05,
    power: float = 0.80,
    comparisons: int = 1,
    design_effect: float = 1.0,
) -> int:
    """Smallest number of independent sources reaching the power, times the design effect.

    The level is divided by ``comparisons`` (Bonferroni); the result is rounded up.
    """
    _check(sigma, delta)
    level = alpha / comparisons
    n = max(2, math.ceil(z_sources(sigma, delta, alpha, power, comparisons)) - 2)
    while paired_power(n, sigma, delta, level) < power:
        n += 1
    return math.ceil(n * design_effect)


def ci_sources(
    sigma: float, half_width: float, level: float = 0.95, design_effect: float = 1.0
) -> int:
    """Smallest number of independent sources whose mean difference has the given CI half-width."""
    _check(sigma, half_width)
    n = 2
    while t_quantile(1 - (1 - level) / 2, n - 1) * sigma / math.sqrt(n) > half_width:
        n += 1
    return math.ceil(n * design_effect)


def sensitivity_grid(
    sigmas: list[float], deltas: list[float], comparisons: list[int]
) -> list[dict[str, Any]]:
    """Requirement for every combination, in the order sigma, delta, comparisons."""
    rows = []
    for sigma in sigmas:
        for delta in deltas:
            for m in comparisons:
                rows.append(
                    {
                        "sigma": sigma,
                        "delta": delta,
                        "comparisons": m,
                        "z_sources": z_sources(sigma, delta, comparisons=m),
                        "t_sources": paired_sources(sigma, delta, comparisons=m),
                        "ci_sources_half_width_delta": ci_sources(sigma, delta),
                    }
                )
    return rows


def holm_adjust(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the order given (monotone, capped at 1)."""
    if any(not 0.0 <= p <= 1.0 for p in pvalues):
        raise ValueError("p-values must be between 0 and 1")
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[index]))
        adjusted[index] = round(running, 12)
    return adjusted


def holm_rejections(pvalues: list[float], alpha: float = 0.05) -> list[bool]:
    """Hypotheses of a prespecified family that Holm's procedure rejects at familywise ``alpha``."""
    return [p <= alpha for p in holm_adjust(pvalues)]


def log_ratio_delta(relative_reduction: float) -> float:
    """Difference on the log scale for a relative reduction r: ln(1 / (1 - r))."""
    if not 0.0 < relative_reduction < 1.0:
        raise ValueError("a relative reduction must be between 0 and 1")
    return -math.log(1.0 - relative_reduction)


def sd_ratio_interval(n: int, level: float = 0.95) -> tuple[float, float]:
    """Confidence interval of sigma-hat / sigma from n sources (chi-square, normal differences)."""
    tail = (1.0 - level) / 2.0
    low = math.sqrt((n - 1) / stats.chi2.ppf(1.0 - tail, n - 1))
    high = math.sqrt((n - 1) / stats.chi2.ppf(tail, n - 1))
    return low, high


def pilot_sources_for_sd(max_upper_ratio: float, level: float = 0.95) -> int:
    """Fewest pilot sources whose SD interval ends at most ``max_upper_ratio`` times sigma-hat."""
    if max_upper_ratio <= 1.0:
        raise ValueError("the upper ratio must be above 1")
    n = 3
    while sd_ratio_interval(n, level)[1] > max_upper_ratio:
        n += 1
    return n


def effective_sd_interval(
    n: int, design_effect: float = 1.0, level: float = 0.95
) -> tuple[float, float]:
    """SD interval with n sources reduced to n / design_effect effective sources (at least two).

    A rough planning device: it assumes the effective number behaves like independent normal
    sources, which clustering and heterogeneity only approximately justify.
    """
    if design_effect < 1.0:
        raise ValueError("the design effect must be at least 1")
    return sd_ratio_interval(max(2, math.floor(n / design_effect)), level)


def pilot_allocation(
    ready: dict[str, int], minimum: int, max_share: float, total_cap: int
) -> dict[str, int]:
    """Pilot groups per category: ``max_share`` of the ready groups, at least ``minimum`` (never
    more than are ready), trimmed from the largest quota while the total exceeds ``total_cap``."""
    quota = {c: min(n, max(minimum, math.floor(n * max_share))) for c, n in sorted(ready.items())}
    while sum(quota.values()) > total_cap:
        largest = max(quota, key=lambda c: (quota[c], c))
        if quota[largest] <= min(minimum, ready[largest]):
            break
        quota[largest] -= 1
    return quota


def draw_pilot(members: dict[str, list[str]], quota: dict[str, int], seed: int) -> dict[str, Any]:
    """Seeded draw of pilot groups meeting each category quota; a group in several categories is
    drawn once and counts for all of them. The rest is the confirmatory holdout. No detector
    result is read: only provenance-group identifiers and the seed."""
    rng = np.random.default_rng(seed)
    chosen: set[str] = set()
    for category in sorted(quota):
        pool = sorted(members.get(category, []))
        have = [g for g in pool if g in chosen]
        rest = [g for g in pool if g not in chosen]
        order = list(rng.permutation(len(rest)))
        for index in order[: max(0, min(quota[category], len(pool)) - len(have))]:
            chosen.add(rest[int(index)])
    every = {g for groups in members.values() for g in groups}
    return {"seed": seed, "pilot": sorted(chosen), "holdout": sorted(every - chosen)}


#: provisional smallest effects of interest (owner decision E); illustrative, not validated
EFFECT_SCENARIOS: list[dict[str, Any]] = [
    {"metric": "recall at matched alert budget", "delta": 0.05},
    {"metric": "AUPRC", "delta": 0.05},
    {"metric": "AUROC", "delta": 0.02},
    {"metric": "false-positive burden", "relative_reduction": 0.20},
    {"metric": "cost", "relative_reduction": 0.20},
]


def effect_requirements(sigmas: list[float]) -> list[dict[str, Any]]:
    """Independent sources per scenario and hypothetical SD (log-ratio scale for relative ones)."""
    rows = []
    for scenario in EFFECT_SCENARIOS:
        relative = "relative_reduction" in scenario
        delta = log_ratio_delta(scenario["relative_reduction"]) if relative else scenario["delta"]
        for sigma in sigmas:
            rows.append(
                {
                    "metric": scenario["metric"],
                    "scale": "log ratio" if relative else "absolute",
                    "sigma": sigma,
                    "delta": delta,
                    "sources_k1": paired_sources(sigma, delta),
                    "sources_holm_k3": paired_sources(sigma, delta, comparisons=3),
                    "sources_holm_k6": paired_sources(sigma, delta, comparisons=6),
                }
            )
    return rows


def effective_groups(cluster_sizes: list[int], icc: float) -> float:
    """Sum over clusters of m / (1 + (m - 1) * icc): groups discounted for shared structure."""
    return float(sum(m / (1 + (m - 1) * icc) for m in cluster_sizes))


def simulate_rejection(
    domains: int,
    per_domain: int,
    sigma_domain: float,
    sigma_source: float,
    delta: float,
    reps: int,
    seed: int,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Rejection rates of a source-level and of a domain-level paired test on simulated data.

    Each source difference is delta + a domain effect + a source effect. The source-level test
    treats all sources as independent; the domain-level test averages within domains first.
    """
    rng = np.random.default_rng(seed)
    naive = cluster = 0
    for _ in range(reps):
        domain_effect = rng.normal(0, sigma_domain, size=(domains, 1))
        diffs = delta + domain_effect + rng.normal(0, sigma_source, size=(domains, per_domain))
        naive += stats.ttest_1samp(diffs.ravel(), 0.0).pvalue < alpha
        cluster += stats.ttest_1samp(diffs.mean(axis=1), 0.0).pvalue < alpha
    return round(naive / reps, 4), round(cluster / reps, 4)


#: provisional acquisition quotas (owner decision B): planning figures, not statistical requirements
TARGETS = {"C1": 36, "C2a": 30, "C2b": 30, "C3": 40, "C4": 28, "C5": 36, "C6": 30}
#: provisional generalisation guardrails (owner decision D): distinct domains, distinct structural families  # noqa: E501
MINIMA = {
    "C1": (5, 3),
    "C2a": (5, 3),
    "C2b": (5, 4),
    "C3": (5, 3),
    "C4": (5, 3),
    "C5": (5, 4),
    "C6": (5, 4),
}


#: labels that name no domain or family and are never counted as one
UNCLASSIFIED = {"Other", "unknown", "other"}


def diversity_report(
    attributes: dict[str, dict[str, Any]],
    ready: dict[str, list[str]],
    targets: dict[str, int] = TARGETS,
    minima: dict[str, tuple[int, int]] = MINIMA,
) -> dict[str, dict[str, Any]]:
    """Per category: groups against the quota, distinct domains and structural families, and the
    exploratory (3 domains, 2 families) and generalisation (minima) coverage status.

    The structural family of a group in a category is ``attributes[group]["structure"][category]``;
    a group without one for that category is an error, not a family of its own.
    """
    out: dict[str, dict[str, Any]] = {}
    for category, groups in sorted(ready.items()):
        families = Counter(
            attributes[g]["structure"][category]
            for g in groups
            if attributes[g]["structure"][category] not in UNCLASSIFIED
        )
        domains = {attributes[g]["domain"] for g in groups} - UNCLASSIFIED
        need_domains, need_families = minima[category]
        quota = len(groups) >= targets[category]
        missing = []
        if not quota:
            missing.append(f"groups: {len(groups)} of {targets[category]}")
        if len(domains) < need_domains:
            missing.append(f"domains: {len(domains)} of {need_domains}")
        if len(families) < need_families:
            missing.append(f"families: {len(families)} of {need_families}")
        biggest = families.most_common(1)[0] if families else ("", 0)
        out[category] = {
            "groups": len(groups),
            "target": targets[category],
            "gap": max(0, targets[category] - len(groups)),
            "domains": len(domains),
            "families": len(families),
            "largest_family": biggest[0],
            "largest_family_share": round(biggest[1] / len(groups), 4) if groups else 0.0,
            "unclassified_groups": sum(
                1
                for g in groups
                if attributes[g]["structure"][category] in UNCLASSIFIED
                or attributes[g]["domain"] in UNCLASSIFIED
            ),
            "exploratory": len(domains) >= 3 and len(families) >= 2,
            "quota": quota,
            "diversity": len(domains) >= need_domains and len(families) >= need_families,
            "missing": missing,
        }
    return out


def coverage_summary(
    attributes: dict[str, dict[str, str]], ready: dict[str, list[str]], icc: float
) -> dict[str, dict[str, Any]]:
    """Distinct domains, producers, curators and schema families per category, plus the groups
    discounted by the assumed intra-schema-family correlation."""
    out: dict[str, dict[str, Any]] = {}
    union: list[str] = sorted({g for groups in ready.values() for g in groups})
    for name, groups in [*sorted(ready.items()), ("ALL", union)]:
        rows = [attributes[g] for g in groups]
        families = Counter(r["schema_family"] for r in rows)
        out[name] = {
            "groups": len(groups),
            "domains": len({r["domain"] for r in rows}),
            "producers": len({r["producer"] for r in rows}),
            "curators": len({r["curator"] for r in rows}),
            "schema_families": len(families),
            "largest_schema_family_share": round(max(families.values()) / len(groups), 4)
            if groups
            else 0.0,
            "effective_groups": round(effective_groups(list(families.values()), icc), 4),
        }
    return out


SIGMAS = [0.05, 0.10, 0.15, 0.20]
DELTAS = [0.02, 0.03, 0.05, 0.10]
COMPARISONS = [1, 3, 6]
ICCS = [0.0, 0.2, 0.5]


def report(
    attributes: dict[str, Any], readiness: dict[str, Any], reps: int = 2000
) -> dict[str, Any]:
    """The illustrative requirement tables and the coverage of the current ready groups."""
    ready = readiness["ready_groups"]
    return {
        "note": "design-only: every sigma, delta and icc below is hypothetical; no detector was run",  # noqa: E501
        "sensitivity": sensitivity_grid(SIGMAS, DELTAS, COMPARISONS),
        "design_effect_sources": [
            {
                "sigma": 0.10,
                "delta": 0.05,
                "cluster_size": m,
                "icc": icc,
                "design_effect": design_effect(m, icc),
                "sources": paired_sources(0.10, 0.05, design_effect=design_effect(m, icc)),
            }
            for m in (2, 4, 8)
            for icc in ICCS
        ],
        "simulation": [
            {
                "domains": d,
                "per_domain": k,
                "sigma_domain": sd,
                "null_rejection_source_level": naive,
                "null_rejection_domain_level": cluster,
            }
            for d, k, sd in ((6, 5, 0.08), (10, 3, 0.08), (10, 3, 0.02))
            for naive, cluster in [simulate_rejection(d, k, sd, 0.05, 0.0, reps=reps, seed=11)]
        ],
        "effect_requirements": effect_requirements([0.02, 0.05, 0.10]),
        "pilot_sd_precision": [
            {"max_upper_ratio": r, "level": lv, "pilot_sources": pilot_sources_for_sd(r, lv)}
            for r in (1.25, 1.40, 1.60)
            for lv in (0.80, 0.95)
        ],
        "minimum_detectable_delta": [
            {"sources": n, "sigma": sigma, "delta": minimum_detectable_delta(n, sigma)}
            for n in (10, 18, 25, 34, 49, 73)
            for sigma in (0.05, 0.10, 0.15)
        ],
        "diversity": diversity_report(attributes, ready),
        "coverage": {str(icc): coverage_summary(attributes, ready, icc) for icc in (0.2, 0.5)},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent
    base = here / "verification/evidence/dataset_registry_v2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=base)
    parser.add_argument("--reps", type=int, default=2000, help="simulation repetitions")
    args = parser.parse_args(argv)
    attributes = json.loads((args.dir / "source_attributes.json").read_text())
    readiness = json.loads((args.dir / "readiness.json").read_text())
    out = report(attributes, readiness, reps=args.reps)
    (args.dir / "target_framework.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n"
    )
    print(
        f"{len(out['sensitivity'])} sensitivity rows, coverage of {out['coverage']['0.2']['ALL']['groups']} groups"  # noqa: E501
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
