"""Statistics of the batch study that need no detector result: dependence, partition and variance.

The unit of inference is the provenance group, and linked groups (shared upstream records or
related populations) form one cluster that stays on one side of any split. The estimators here
take per-group numbers, so they can be tested on synthetic data and run unchanged on a pilot. The
sample-size arithmetic and the Holm correction are those of ``target_framework``.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import target_framework as tf

LINKS = Path(__file__).resolve().parent.parent / "verification/evidence/dataset_registry_v2"


def link_clusters(groups: list[str], linked_sets: list[list[str]]) -> dict[str, str]:
    """Cluster id per group: a linked set shares the id of its first group in sorted order.

    Sets that share a group merge into one cluster. A group in no set is its own cluster.
    """
    parent = {g: g for g in groups}

    def find(g: str) -> str:
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    for members in linked_sets:
        present = [g for g in members if g in parent]
        for g in present[1:]:
            a, b = find(present[0]), find(g)
            if a != b:
                parent[max(a, b)] = min(a, b)
    return {g: find(g) for g in groups}


def clusters_of(assignment: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for group, cluster in sorted(assignment.items()):
        out.setdefault(cluster, []).append(group)
    return out


def draw_clustered_pilot(
    members: dict[str, list[str]],
    linked_sets: list[list[str]],
    exposed: list[str],
    total: int,
    minimum: int,
    seed: int,
    domains: dict[str, str] | None = None,
    reuse_exposed: bool = False,
) -> dict[str, Any]:
    """Seeded pilot of ``total`` clusters; exposed groups and their linked partners never confirm.

    A cluster is drawn as one unit, so linked groups never straddle the pilot and the holdout. The
    exposed clusters are reported apart; with ``reuse_exposed`` they fill the first pilot places
    (they cannot be confirmatory evidence, so the pilot spends no fresh cluster on them) and the
    draw supplies the rest (the per-category minimum counts fresh clusters only). Only group
    identifiers, categories and the seed are read.
    """
    every = sorted({g for groups in members.values() for g in groups})
    cluster = link_clusters(every, linked_sets)
    exposed_clusters = {cluster[g] for g in exposed if g in cluster}
    collapsed = {
        c: sorted({cluster[g] for g in groups if cluster[g] not in exposed_clusters})
        for c, groups in members.items()
    }
    by_cluster = clusters_of(cluster)
    labels = {c: domains.get(c, "") for c in by_cluster} if domains else None
    seeded = len(exposed_clusters) if reuse_exposed else 0
    if total < seeded:
        raise ValueError("the pilot is smaller than the exposed clusters it must hold")
    plan = tf.plan_pilot(collapsed, total - seeded, minimum, seed, labels)
    pilot = sorted(set(plan["pilot"]) | (exposed_clusters if reuse_exposed else set()))

    def expand(ids: Any) -> list[str]:
        return sorted(g for c in ids for g in by_cluster[c])

    return {
        "seed": seed,
        "pilot": expand(pilot),
        "holdout": expand(plan["holdout"]),
        "exposed": expand(exposed_clusters),
        "clusters": {"pilot": len(pilot), "holdout": len(plan["holdout"])},
    }


def factor_structure(
    groups: list[str], attributes: dict[str, dict[str, Any]], factors: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    """Levels of each random-effect factor over the groups: what a model could estimate.

    ``singletons`` are levels with one group (their effect is confounded with the group's own).
    """
    out: dict[str, dict[str, Any]] = {}
    for factor in factors:
        counts = Counter(str(attributes.get(g, {}).get(factor, "unknown")) for g in groups)
        out[factor] = {
            "levels": len(counts),
            "singletons": sum(1 for n in counts.values() if n == 1),
            "largest": max(counts.values()) if counts else 0,
            "largest_level": min(k for k, n in counts.items() if n == max(counts.values()))
            if counts
            else None,
        }
    return out


def effective_clusters(sizes: list[int], icc: float) -> float:
    """Groups discounted for dependence inside clusters (``target_framework.effective_groups``)."""
    return tf.effective_groups(sizes, icc)


def cluster_bootstrap(
    values: np.ndarray,
    clusters: list[str],
    seed: int,
    resamples: int = 2000,
    level: float = 0.95,
) -> dict[str, float]:
    """Mean of per-group values with a percentile interval from resampling whole clusters.

    Each resample draws as many clusters as there are, with replacement, and pools their groups,
    so a linked set always enters together. ``values`` has one entry per group.
    """
    values = np.fromiter(values, dtype=float)
    if len(values) != len(clusters) or not len(values):
        raise ValueError("one value and one cluster per group, at least one group")
    if not 0.0 < level < 1.0:
        raise ValueError("level must be between 0 and 1")
    names = sorted(set(clusters))
    rows = [np.flatnonzero(np.array(clusters) == c) for c in names]
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    for i in range(resamples):
        pick = rng.integers(len(names), size=len(names))
        means[i] = values[np.concatenate([rows[j] for j in pick])].mean()
    tail = (1.0 - level) / 2.0 * 100.0
    low, high = np.percentile(means, [tail, 100.0 - tail])
    return {
        "mean": float(values.mean()),
        "low": float(low),
        "high": float(high),
        "clusters": len(names),
    }


def icc_oneway(y: np.ndarray) -> float:
    """ICC(1) of a balanced table (groups x observations), truncated at zero.

    The share of the variance that lies between groups: (MSB - MSW) / (MSB + (k - 1) MSW).
    """
    y = np.asarray(y)
    n, k = y.shape
    if n < 2 or k < 2:
        raise ValueError("need at least two groups and two observations per group")
    msb = k * y.mean(axis=1).var(ddof=1)
    msw = ((y - y.mean(axis=1, keepdims=True)) ** 2).sum() / (n * (k - 1))
    return max(0.0, float((msb - msw) / (msb + (k - 1) * msw)))


def variance_components(y: np.ndarray) -> dict[str, float]:
    """Source, detector, source-by-detector and residual variance of a balanced crossed design.

    ``y`` has shape (sources, detectors, replicates) with at least two replicates (seeds,
    mechanisms or severities). Expected-mean-square estimators of the two-way random-effects model;
    a negative estimate is reported as zero and listed in ``truncated``. This is the method of
    moments, not REML, and it needs a complete design.
    """
    y = np.asarray(y)
    s, d, r = y.shape
    if s < 2 or d < 2 or r < 2:
        raise ValueError("need at least two sources, two detectors and two replicates")
    cell = y.mean(axis=2)
    source, detector, grand = cell.mean(axis=1), cell.mean(axis=0), y.mean()
    ms_s = d * r * ((source - grand) ** 2).sum() / (s - 1)
    ms_d = s * r * ((detector - grand) ** 2).sum() / (d - 1)
    inter = cell - source[:, None] - detector[None, :] + grand
    ms_sd = r * (inter**2).sum() / ((s - 1) * (d - 1))
    ms_e = ((y - cell[:, :, None]) ** 2).sum() / (s * d * (r - 1))
    raw = {
        "source": (ms_s - ms_sd) / (d * r),
        "detector": (ms_d - ms_sd) / (s * r),
        "source_by_detector": (ms_sd - ms_e) / r,
        "residual": ms_e,
    }
    out = {k: max(0.0, float(v)) for k, v in raw.items()}
    out["truncated"] = sorted(k for k, v in raw.items() if v < 0)  # type: ignore[assignment]
    return out


def paired_difference_sd(y: np.ndarray, first: int, second: int) -> float:
    """SD over sources of the detector difference of the replicate means: the sigma of the
    paired-source sample-size tables (``target_framework.paired_sources``)."""
    y = np.asarray(y)
    if y.shape[0] < 2:
        raise ValueError("need at least two sources")
    return float((y[:, first].mean(axis=1) - y[:, second].mean(axis=1)).std(ddof=1))


def load_links(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or LINKS / "linked_sets.json").read_text())


FACTORS = ("domain", "schema_family", "curator")


def eligible_members(evidence: Path, audit: Path) -> dict[str, list[str]]:
    """Ready groups per category that the batch audit found eligible."""
    ready = json.loads((evidence / "readiness.json").read_text())["ready_groups"]
    groups = json.loads(audit.read_text())["groups"]
    return {
        c: sorted(g for g in gs if groups.get(g, {}).get("eligible")) for c, gs in ready.items()
    }


def structure(evidence: Path, audit: Path, links: dict[str, Any]) -> dict[str, Any]:
    """Dependence structure of the eligible population: no outcome is read."""
    members = eligible_members(evidence, audit)
    groups = sorted({g for gs in members.values() for g in gs})
    attributes = json.loads((evidence / "source_attributes.json").read_text())
    cluster = link_clusters(groups, [s["groups"] for s in links["linked_sets"]])
    exposed = sorted(set(links["exposed_groups"]) & set(groups))
    return {
        "eligible_groups": len(groups),
        "per_category": {c: len(gs) for c, gs in sorted(members.items())},
        "clusters": len(set(cluster.values())),
        "exposed": exposed,
        "available_after_exposure": len(groups) - len(exposed),
        "factors": factor_structure(groups, attributes, FACTORS),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("structure", "pilot-plan"))
    parser.add_argument("--evidence", type=Path, default=LINKS)
    parser.add_argument("--audit", type=Path, default=LINKS / "batch_eligibility.json")
    parser.add_argument("--links", type=Path, default=LINKS / "linked_sets.json")
    parser.add_argument("--total", type=int)
    parser.add_argument("--minimum", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--reuse-exposed", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    links = load_links(args.links)
    if args.command == "structure":
        report: dict[str, Any] = structure(args.evidence, args.audit, links)
    else:
        if args.total is None or args.seed is None:
            raise SystemExit("pilot-plan needs --total and --seed (both are owner decisions)")
        report = draw_clustered_pilot(
            eligible_members(args.evidence, args.audit),
            [s["groups"] for s in links["linked_sets"]],
            sorted(links["exposed_groups"]),
            args.total,
            args.minimum,
            args.seed,
            reuse_exposed=args.reuse_exposed,
        )
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
