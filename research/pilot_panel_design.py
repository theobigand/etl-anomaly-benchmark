"""Balanced pilot-panel allocation and planning-ratio coverage (#153, design only).

Reads only provenance metadata (category, domain, schema family, curator, linked cluster, floor,
exposure); no detector result, label outcome or held-out value is read and nothing is fitted.

The allocation is a constrained, seeded draw. The unit is the provenance cluster. Category quotas
are water-filled (equal shares, the remainder to the categories with most room) rather than
assigned to the category with the largest pool, which is what concentrates larger panels around
C1 and UCI. Inside a category the draw prefers clusters of a domain, schema family and curator
not yet in the panel, with a curator cap, and breaks the remaining ties with one seeded
permutation. The seed is a single input, never searched.

A cluster counts for its first category (alphabetical) in the quotas and for every category it
participates in in the profile.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import target_framework as tf
from scipy import stats

SMALLEST_EFFECT = 0.05


def sd_upper_coverage(n: int, ratio: float) -> float:
    """P(sigma <= ratio * sigma-hat) for n independent normal sources: one-sided coverage."""
    return float(stats.chi2.sf((n - 1) / ratio**2, n - 1))


def two_sided_level(n: int, ratio: float) -> float:
    """Level of the two-sided interval whose upper end is ``ratio`` (``sd_ratio_interval``)."""
    return 2.0 * sd_upper_coverage(n, ratio) - 1.0


def cluster_table(table: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group the per-group table by provenance cluster.

    A cluster is exposed if any member is, below the floor if any member is, and meets it only if
    every member does; an unknown member leaves it unknown.
    """
    out: dict[str, dict[str, Any]] = {}
    for group, row in sorted(table.items()):
        entry = out.setdefault(
            row["cluster"],
            {
                "groups": [],
                "categories": set(),
                "domains": set(),
                "schema_families": set(),
                "curators": set(),
                "floors": [],
                "exposed": False,
            },
        )
        entry["groups"].append(group)
        entry["categories"].update(row["categories"])
        entry["domains"].add(row["domain"])
        entry["schema_families"].add(row["schema_family"])
        entry["curators"].add(row["curator"])
        entry["floors"].append(row["floor"])
        entry["exposed"] = entry["exposed"] or bool(row["exposed"])
    for entry in out.values():
        floors = entry.pop("floors")
        entry["floor"] = (
            False if False in floors else True if all(f is True for f in floors) else None
        )
        for key in ("categories", "domains", "schema_families", "curators"):
            entry[key] = sorted(entry[key])
    return out


def eligible_clusters(clusters: dict[str, dict[str, Any]], require_floor: bool = True) -> set[str]:
    """Unexposed clusters; with ``require_floor`` only those whose floor is met."""
    return {
        c
        for c, e in clusters.items()
        if not e["exposed"] and (e["floor"] is True or not require_floor)
    }


def water_fill(size: int, capacity: dict[str, int]) -> dict[str, int]:
    """Equal quotas first, each next place to the category with most room left (ties by name)."""
    if size > sum(capacity.values()):
        raise ValueError(f"size {size} exceeds the capacity {sum(capacity.values())}")
    quota = {c: 0 for c in sorted(capacity)}
    for _ in range(size):
        open_ = [c for c in quota if quota[c] < capacity[c]]
        quota[min(open_, key=lambda c: (quota[c], quota[c] - capacity[c], c))] += 1
    return quota


def balanced_panel(
    table: dict[str, dict[str, Any]],
    size: int,
    seed: int,
    require_floor: bool = True,
    curator_share: float = 0.25,
) -> dict[str, Any]:
    """Seeded balanced panel of ``size`` clusters; see the module docstring."""
    clusters = cluster_table(table)
    pool = sorted(eligible_clusters(clusters, require_floor))
    if not require_floor:
        pool = [c for c in pool if clusters[c]["floor"] is not True]
    home = {c: clusters[c]["categories"][0] for c in pool}
    capacity = {k: sum(1 for c in pool if home[c] == k) for k in sorted(set(home.values()))}
    quotas = water_fill(size, capacity)
    rank = {c: int(i) for i, c in enumerate(np.random.default_rng(seed).permutation(pool))}
    cap = max(2, math.ceil(size * curator_share))
    chosen: list[str] = []
    seen: dict[str, dict[str, int]] = {"domains": {}, "schema_families": {}, "curators": {}}

    def key(cluster: str) -> tuple[int, int, int, int, int]:
        entry = clusters[cluster]
        taken = {k: sum(seen[k].get(v, 0) for v in entry[k]) for k in seen}
        return (
            int(taken["curators"] >= cap),
            taken["domains"],
            taken["schema_families"],
            taken["curators"],
            rank[cluster],
        )

    for category in sorted(quotas, key=lambda c: (capacity[c], c)):
        for _ in range(quotas[category]):
            candidates = [c for c in pool if home[c] == category and c not in chosen]
            pick = min(candidates, key=key)
            chosen.append(pick)
            for k in seen:
                for v in clusters[pick][k]:
                    seen[k][v] = seen[k].get(v, 0) + 1
    return {
        "seed": seed,
        "size": size,
        "require_floor": require_floor,
        "quotas": quotas,
        "clusters": sorted(chosen),
        "groups": sorted(g for c in chosen for g in clusters[c]["groups"]),
    }


def panel_profile(table: dict[str, dict[str, Any]], groups: list[str]) -> dict[str, Any]:
    """Composition of a panel and what is left for the confirmatory holdout."""
    clusters = cluster_table(table)
    panel = {table[g]["cluster"] for g in groups}
    rows = [clusters[c] for c in sorted(panel)]

    def count(key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in rows:
            for value in row[key]:
                out[value] = out.get(value, 0) + 1
        return dict(sorted(out.items()))

    holdout = {c for c, e in clusters.items() if c not in panel and not e["exposed"]}
    met = {c for c in holdout if clusters[c]["floor"] is True}
    by_category = {
        k: sum(1 for c in met if k in clusters[c]["categories"])
        for k in sorted({k for e in clusters.values() for k in e["categories"]})
    }
    curators, families = count("curators"), count("schema_families")
    return {
        "clusters": len(panel),
        "category_clusters": count("categories"),
        "domains": len(count("domains")),
        "schema_families": len(families),
        "max_per_schema_family": max(families.values()),
        "curators": len(curators),
        "max_per_curator": max(curators.values()),
        "uci_clusters": curators.get("uci", 0),
        "floor_met": sum(1 for r in rows if r["floor"] is True),
        "exposed": sum(1 for r in rows if r["exposed"]),
        "holdout_clusters": len(holdout),
        "holdout_floor_met": len(met),
        "holdout_floor_met_by_category": by_category,
    }


def historical_overlap(
    table: dict[str, dict[str, Any]], pool_rows: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Registry UCI groups that were also rows of the historical pool benchmark.

    ``labelled``: detectors ran on the native labels of the row and outcomes were reported;
    ``carrier``: the row only carried injected faults. Both are study-specific exposure under the
    old protocols, not exposure under the unit-level protocols; whether they matter is a rule the
    owner decides, and the registry's ``exposed_groups`` does not record them.
    """
    out: dict[str, list[str]] = {"labelled": [], "carrier": []}
    for row in pool_rows:
        group = f"uci:{row['uci_id']}"
        if group in table:
            out["labelled" if "labelled" in row["roles"] else "carrier"].append(group)
    return {k: sorted(set(v)) for k, v in out.items()}


def with_exposure(table: dict[str, dict[str, Any]], groups: list[str]) -> dict[str, dict[str, Any]]:
    """Copy of the table in which the given groups count as exposed (a scenario, not a rule)."""
    return {g: {**row, "exposed": row["exposed"] or g in set(groups)} for g, row in table.items()}


def required_sources(sigma_hat: float, ratio: float, comparisons: int, design_effect: float) -> int:
    """Confirmatory clusters for the smallest effect: sigma = sigma-hat x ratio, Holm level
    alpha / comparisons (Bonferroni planning bound), times the confirmatory design effect.
    The ratio carries the dependence of the pilot; the design effect that of the confirmatory
    clusters: the two are different and are applied once each."""
    return tf.paired_sources(
        sigma_hat * ratio, SMALLEST_EFFECT, comparisons=comparisons, design_effect=design_effect
    )


SIGMA_HATS = (0.07, 0.10, 0.12)
RATIOS = (1.4, 1.55, 1.7)
FAMILIES = (1, 3, 11)  # primary candidates 1 and 3; 11 is a sensitivity scenario
DESIGN_EFFECTS = (1.0, 1.3)
SEEDS = range(1, 101)
EVIDENCE = Path(__file__).resolve().parent.parent / "verification/evidence/dataset_registry_v2"


def _summary(values: list[int]) -> dict[str, float]:
    return {"min": min(values), "median": float(np.median(values)), "max": max(values)}


def build(
    panel_file: dict[str, Any],
    seed: int,
    sizes: tuple[int, ...] = (16, 24, 32),
    pool_rows: list[dict[str, Any]] | None = None,
) -> dict:
    """Current proposals against balanced panels, capacity and seed-stability of the procedure."""
    table = panel_file["table"]
    out: dict[str, Any] = {
        "note": "design-only: provenance metadata only, no detector was run; a proposal, not an "
        "approval; the seed is the recorded plan seed, not searched",
        "seed": seed,
        "coverage": [
            {
                "effective_n": n,
                "ratio": r,
                "one_sided": round(sd_upper_coverage(n, r), 4),
                "two_sided_level": round(two_sided_level(n, r), 4),
            }
            for r in RATIOS
            for n in (16, 12, 8)
        ],
        "panels": {},
    }
    for n in sizes:
        balanced = balanced_panel(table, n, seed)
        profile = panel_profile(table, balanced["groups"])
        current = panel_profile(table, panel_file["plans"][str(n)]["pilot"])
        stable = [panel_profile(table, balanced_panel(table, n, s)["groups"]) for s in SEEDS]
        out["panels"][str(n)] = {
            "current": current,
            "balanced": {
                "quotas": balanced["quotas"],
                "cluster_ids": balanced["clusters"],
                **profile,
            },
            "seed_stability": {
                key: _summary([p[key] for p in stable])
                for key in ("max_per_curator", "max_per_schema_family", "domains", "uci_clusters")
            },
            "pilot_upper_ratio_95": round(tf.effective_sd_interval(n)[1], 3),
            "required_sources": [
                {
                    "sigma_hat": sh,
                    "ratio": r,
                    "comparisons": k,
                    "design_effect": de,
                    "sources": required_sources(sh, r, k, de),
                    "fits_holdout_floor_met": required_sources(sh, r, k, de)
                    <= profile["holdout_floor_met"],
                }
                for sh in SIGMA_HATS
                for r in RATIOS
                for k in FAMILIES
                for de in DESIGN_EFFECTS
            ],
        }
    if pool_rows is not None:
        overlap = historical_overlap(table, pool_rows)
        strict = with_exposure(table, overlap["labelled"])
        out["historical_exposure"] = {
            "labelled_pool_groups": overlap["labelled"],
            "carrier_only_groups": overlap["carrier"],
            "in_current_panels": {
                str(n): sorted(set(overlap["labelled"]) & set(panel_file["plans"][str(n)]["pilot"]))
                for n in sizes
            },
            "scenario_labelled_groups_also_exposed": {
                str(n): panel_profile(strict, balanced_panel(strict, n, seed)["groups"])
                for n in sizes
            },
        }
    clusters = cluster_table(table)
    below = {
        clusters[c]["categories"][0]
        for c in eligible_clusters(clusters, require_floor=False)
        if clusters[c]["floor"] is not True
    }
    technical = balanced_panel(table, len(below), seed, require_floor=False)
    out["technical_validation_panel"] = {
        "purpose": "protocol plumbing only, below the floor, disjoint from the statistical panels",
        "clusters": technical["clusters"],
        "quotas": technical["quotas"],
    }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--seed", type=int, default=20261121)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    panel_file = json.loads((args.evidence / "unit_pilot_panel.json").read_text())
    pool = args.evidence.parent / "dataset_registry/uci_pool.json"
    rows = json.loads(pool.read_text())["rows"] if pool.exists() else None
    text = json.dumps(build(panel_file, args.seed, pool_rows=rows), indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
