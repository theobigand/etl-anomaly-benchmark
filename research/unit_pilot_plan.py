"""Unit-level variance pilot: panel proposal over the 235-group corpus (#152, design only).

The panel is a seeded draw over metadata and provenance: ready groups per category, linked sets,
previous exposure and domain labels. No detector result, label outcome or held-out value is read,
and nothing here runs a detector. The draw is the one of the batch pilot
(``batch_statistics.draw_clustered_pilot``): a linked cluster is drawn as one unit, so linked
groups never straddle the pilot and the confirmatory holdout, and exposed clusters never confirm.

The pilot size, the minimum per category, the seed and the exposure rule are owner decisions; the
module takes them as arguments and records them with the plan. A plan is a proposal until the
owner records an authorization for the step and the groups (``registry_units.check_authorization``).

The confirmatory floor (``variance_pilot_design.md`` 12.4) needs at least 1,000 eligible test
units. Test units are estimated as 15 percent of the units of a group whose recorded partition is
the 70/15/15 hash split; for any other partition the floor is reported as unknown, never as met.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import batch_statistics as bs
import target_framework as tf

EVIDENCE = bs.LINKS
OUTPUT = EVIDENCE / "unit_pilot_panel.json"
SPLIT = "70/15/15"
TEST_SHARE = 0.15
FLOOR_TEST_UNITS = 1000
#: hypothetical planning figures of the design (section 11.7): sigma, smallest effect, family sizes
SIGMA, DELTA, FAMILIES = 0.10, 0.05, (1, 3, 5, 11)


def group_table(evidence: Path) -> dict[str, dict[str, Any]]:
    """Per group: categories, units, floor, domain, schema family, curator and linked cluster."""
    facts = json.loads((evidence / "readiness_facts.json").read_text())["facts"]
    registry = json.loads((evidence / "readiness.json").read_text())
    attributes = json.loads((evidence / "source_attributes.json").read_text())
    links = bs.load_links(evidence / "linked_sets.json")
    stratum = {d["id"]: d["stratum"] for d in registry["datasets"]}
    ready = {(g, c) for c, groups in registry["ready_groups"].items() for g in groups}
    groups = sorted({g for g, _ in ready})
    cluster = bs.link_clusters(groups, [s["groups"] for s in links["linked_sets"]])
    table: dict[str, dict[str, Any]] = {
        g: {"categories": [], "units": 0, "split": set(), "floor": None} for g in groups
    }
    for fact_id, fact in facts.items():
        group, category = fact.get("independent_group"), stratum.get(fact_id)
        if (group, category) not in ready:
            continue
        row = table[group]
        row["categories"].append(category)
        row["units"] = max(row["units"], fact["units"])
        row["split"].add(SPLIT in str(fact.get("partitions", "")))
    for group, row in table.items():
        attribute = attributes[group]
        row["categories"] = sorted(set(row["categories"]))
        row["floor"] = (
            int(row["units"] * TEST_SHARE) >= FLOOR_TEST_UNITS if row["split"] == {True} else None
        )
        row["split"] = sorted(row["split"])
        row.update(
            domain=attribute["domain"],
            schema_family=attribute["schema_family"],
            curator=attribute["curator"],
            cluster=cluster[group],
            exposed=group in links["exposed_groups"],
        )
    return table


def plan(
    evidence: Path, total: int, minimum: int, seed: int, reuse_exposed: bool = False
) -> dict[str, Any]:
    """One seeded panel proposal and the adequacy of its confirmatory holdout."""
    registry = json.loads((evidence / "readiness.json").read_text())
    links = bs.load_links(evidence / "linked_sets.json")
    table = group_table(evidence)
    domains = {g: row["domain"] for g, row in table.items()}
    draw = bs.draw_clustered_pilot(
        {c: sorted(g) for c, g in registry["ready_groups"].items()},
        [s["groups"] for s in links["linked_sets"]],
        sorted(links["exposed_groups"]),
        total,
        minimum,
        seed,
        domains,
        reuse_exposed,
    )
    pilot, holdout = set(draw["pilot"]), set(draw["holdout"])
    exposed = set(draw["exposed"])
    per_category = {
        c: {
            "ready": len(g),
            "pilot": len(pilot & set(g)),
            "holdout": len(holdout & set(g)),
            "holdout_floor_met": sum(table[x]["floor"] is True for x in holdout & set(g)),
            "holdout_floor_unknown": sum(table[x]["floor"] is None for x in holdout & set(g)),
            "exposed_not_confirming": len(exposed & set(g)),
        }
        for c, g in sorted(registry["ready_groups"].items())
    }
    holdout_clusters = {table[g]["cluster"] for g in holdout}
    return {
        "seed": seed,
        "total": total,
        "minimum": minimum,
        "reuse_exposed": reuse_exposed,
        "pilot": sorted(pilot),
        "holdout": sorted(holdout),
        "exposed": sorted(exposed),
        "clusters": draw["clusters"],
        "per_category": per_category,
        "holdout_clusters": len(holdout_clusters),
        "holdout_clusters_floor_met": len(
            {table[g]["cluster"] for g in holdout if table[g]["floor"] is True}
        ),
        "required_sources": {
            str(k): tf.paired_sources(SIGMA, DELTA, comparisons=k) for k in FAMILIES
        },
    }


def build(evidence: Path, sizes: list[int], minimum: int, seed: int) -> dict[str, Any]:
    return {
        "status": "proposal: size, minimum, seed and exposure rule are owner decisions",
        "table": group_table(evidence),
        "plans": {str(n): plan(evidence, n, minimum, seed) for n in sizes},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--sizes", type=int, nargs="+", required=True)
    parser.add_argument("--minimum", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = json.dumps(build(args.evidence, args.sizes, args.minimum, args.seed), indent=1) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
