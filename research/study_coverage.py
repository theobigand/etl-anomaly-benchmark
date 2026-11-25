"""Coverage of the two studies per provenance group (T430): which claim each population supports.

One row per independent provenance group joins existing evidence only: category membership and
facts (``readiness*.json``), local availability of the experimental view, the unit-level protocol
that applies to its structure (``anomaly_protocols.json``), batch eligibility
(``batch_eligibility.json``), proposed batch units (``registry_units.compatibility``), linked
clusters and exposure (``linked_sets.json``). Nothing here reads a detector result. Counts are of
groups or clusters, never of batches, seeds or injected variants.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import batch_statistics as bs
import registry_units as ru

EVIDENCE = bs.LINKS
VIEWS = ru.bp.VIEWS


def view_available(manifest: dict[str, Any], views: Path, name: str) -> bool:
    """Every file of the view recorded in the manifest exists locally."""
    files = manifest[name]["files"] if name in manifest else {}
    return bool(files) and all(
        (views / name / f).is_file() or (views / "flat" / f).is_file() for f in files
    )


def group_rows(
    evidence: Path, views: Path, links: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    facts = json.loads((evidence / "readiness_facts.json").read_text())["facts"]
    ready = json.loads((evidence / "readiness.json").read_text())["ready_groups"]
    audit = json.loads((evidence / "batch_eligibility.json").read_text())["groups"]
    protocols = json.loads((evidence / "anomaly_protocols.json").read_text())["protocols"]
    members = {g for groups in ready.values() for g in groups}
    cluster = bs.link_clusters(sorted(audit), [s["groups"] for s in links["linked_sets"]])
    rows: dict[str, dict[str, Any]] = {}
    for fact in facts.values():
        group = fact.get("independent_group")
        if not group or group not in members:  # a fact of a group that is not ready is not counted
            continue
        row = rows.setdefault(
            group,
            {
                "views": set(),
                "protocols": set(),
                "origin": set(),
                "natural_labels": False,
                "units_ok": False,
            },
        )
        row["protocols"].add(fact["protocol_id"])
        if fact.get("view"):
            row["views"].add(fact["view"])
        row["origin"].add(fact["anomaly_origin"])
        row["natural_labels"] |= bool(fact.get("natural_labels"))
        row["units_ok"] |= fact["units"] >= fact["min_units"]
    out = {}
    for group, row in sorted(rows.items()):
        entry = audit[group]
        local = bool(row["views"]) and all(view_available(manifest, views, v) for v in row["views"])
        protocol = sorted(row["protocols"])[0]
        compat = ru.compatibility(protocol, entry)
        out[group] = {
            "categories": sorted(c for c, gs in ready.items() if group in gs),
            "protocol": protocol,
            "views": sorted(row["views"]),
            "local_view_available": local,
            "labels": {"origin": sorted(row["origin"]), "natural_labels": row["natural_labels"]},
            "unit_level": {
                "mechanisms": protocols[protocol]["mechanisms"],
                "compatible": local and row["units_ok"],
                "reason": ""
                if local and row["units_ok"]
                else ("view not built locally" if not local else "fewer units than the minimum"),
            },
            "batch_approved": {"eligible": entry["eligible"], "reasons": entry["reasons"]},
            "batch_provisional": [
                {"unit": c["unit"], "reason": c["reason"]}
                for c in compat
                if c["status"] != "registered"
            ],
            "cluster": cluster[group],
            "exposed": group in links["exposed_groups"],
        }
    return out


def summarise(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cats = sorted({c for r in rows.values() for c in r["categories"]})
    per = {}
    for c in cats:
        mine = {g: r for g, r in rows.items() if c in r["categories"]}
        per[c] = {
            "groups": len(mine),
            "local_view": sum(r["local_view_available"] for r in mine.values()),
            "unit_level": sum(r["unit_level"]["compatible"] for r in mine.values()),
            "batch_approved": sum(r["batch_approved"]["eligible"] for r in mine.values()),
            "batch_approved_clusters": len(
                {r["cluster"] for r in mine.values() if r["batch_approved"]["eligible"]}
            ),
            "exposed": sum(r["exposed"] for r in mine.values()),
        }
    return {
        "groups": len(rows),
        "clusters": len({r["cluster"] for r in rows.values()}),
        "unit_level": sum(r["unit_level"]["compatible"] for r in rows.values()),
        "batch_approved": sum(r["batch_approved"]["eligible"] for r in rows.values()),
        "batch_approved_clusters": len(
            {r["cluster"] for r in rows.values() if r["batch_approved"]["eligible"]}
        ),
        "natural_labels": sum(r["labels"]["natural_labels"] for r in rows.values()),
        "protocols": dict(sorted(Counter(r["protocol"] for r in rows.values()).items())),
        "per_category": per,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--views", type=Path, default=VIEWS)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = json.loads((args.evidence / "experimental_views.json").read_text())
    links = bs.load_links(args.evidence / "linked_sets.json")
    rows = group_rows(args.evidence, args.views, links, manifest)
    text = json.dumps({"summary": summarise(rows), "groups": rows}, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
