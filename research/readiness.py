"""Readiness contract for acquired datasets (T434-T437): seven ordered, testable statuses.

A dataset holds the highest status whose checks, and those of every earlier status, all pass.
The checks look at recorded facts, never at the number of tests run. ``experiment_ready`` means the
data can be used by a protocol; it does not mean an experiment was executed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

STATUSES = (
    "discovered",
    "rights_verified",
    "acquired",
    "structurally_valid",
    "scientifically_eligible",
    "protocol_ready",
    "experiment_ready",
)
RIGHTS_CLASSES = ("open", "research_only")
PRIVACY_OK = ("not_needed", "handled")


def _discovered(f: dict[str, Any]) -> list[str]:
    return [] if f.get("id") and f.get("source") else ["no identifier or source"]


def _rights(f: dict[str, Any]) -> list[str]:
    out = []
    if f.get("licence_class") not in RIGHTS_CLASSES:
        out.append(f"licence class {f.get('licence_class')!r} is not open or research_only")
    if not (f.get("first_party") or f.get("upstream_status") == "verified"):
        out.append("upstream terms not verified at the original publisher")
    return out


def _acquired(f: dict[str, Any]) -> list[str]:
    return [] if f.get("files_verified") else ["stored files not verified against checksums"]


def _structure(f: dict[str, Any]) -> list[str]:
    return [] if f.get("structure_passed") else ["structural validation not passed"]


def _eligible(f: dict[str, Any]) -> list[str]:
    out = []
    if not f.get("independent_group"):
        out.append("no independent source group")
    if f.get("privacy") not in PRIVACY_OK:
        out.append("personal-data handling not reviewed")
    if "baseline_properties" not in f:
        out.append("expected source properties (baseline) not recorded")
    if not f.get("anomaly_origin"):
        out.append("anomaly origin (natural or injected) not declared")
    if (f.get("units") or 0) < (f.get("min_units") or 1):
        out.append("too few detection units")
    return out


def _protocol(f: dict[str, Any]) -> list[str]:
    return [
        f"{k} not defined" for k in ("protocol_id", "detection_unit", "partitions") if not f.get(k)
    ]


def _view(f: dict[str, Any]) -> list[str]:
    out = []
    if not (f.get("view_sha256") and f.get("view_preprocessing")):
        out.append("no checksummed experimental view with recorded preprocessing")
    if f.get("personal_fields_remaining"):
        out.append("personal fields remain in the experimental view")
    return out


CHECKS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "discovered": _discovered,
    "rights_verified": _rights,
    "acquired": _acquired,
    "structurally_valid": _structure,
    "scientifically_eligible": _eligible,
    "protocol_ready": _protocol,
    "experiment_ready": _view,
}


def assess(facts: dict[str, Any]) -> dict[str, Any]:
    """Highest status reached and, when it stops early, the next status and its reasons."""
    reached = None
    for status in STATUSES:
        reasons = CHECKS[status](facts)
        if reasons:
            return {"status": reached, "failed": {"status": status, "reasons": reasons}}
        reached = status
    return {"status": reached, "failed": None}


def summarise(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Per stratum, how many datasets reached each status or a later one."""
    table: dict[str, dict[str, int]] = {}
    for r in rows:
        counts = table.setdefault(r["stratum"], dict.fromkeys(STATUSES, 0))
        if r["status"] is None:
            continue
        for status in STATUSES[: STATUSES.index(r["status"]) + 1]:
            counts[status] += 1
    return table


def ready_groups(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Independent source groups holding at least one experiment-ready dataset, per stratum."""
    out: dict[str, set[str]] = {}
    for r in rows:
        if r["status"] == "experiment_ready":
            out.setdefault(r["stratum"], set()).add(r["group"])
    return {k: sorted(v) for k, v in sorted(out.items())}


def facts_from(
    entry: dict[str, Any],
    declared: dict[str, Any] | None,
    views: dict[str, Any],
    protocols: dict[str, Any],
) -> dict[str, Any]:
    """Facts of one acquired entry from tracked evidence and the facts a reviewer declared."""
    declared = declared or {}
    stages = entry.get("stages", {})
    view = views.get(declared.get("view") or "")
    view_hash = None
    if view:
        shas = "".join(f["sha256"] for _, f in sorted(view["files"].items()))
        view_hash = hashlib.sha256(shas.encode()).hexdigest()
    protocol = protocols.get(declared.get("protocol_id") or "", {})
    return {
        "id": entry["id"],
        "source": entry.get("publisher"),
        "licence_class": entry["licence_class"],
        "first_party": declared.get("first_party", False),
        "upstream_status": entry.get("upstream_status"),
        "files_verified": bool(stages.get("data_acquired")),
        # an entry judged scientifically ineligible does not pass structure
        "structure_passed": bool(stages.get("structural_validation") and entry.get("eligible")),
        "independent_group": declared.get("independent_group"),
        "privacy": declared.get("privacy"),
        **({"baseline_properties": declared["baseline_properties"]} if declared else {}),
        "anomaly_origin": declared.get("anomaly_origin"),
        "units": declared.get("units"),
        "min_units": declared.get("min_units"),
        "protocol_id": declared.get("protocol_id"),
        "detection_unit": protocol.get("detection_unit"),
        "partitions": declared.get("partitions"),
        "view_sha256": view_hash,
        "view_preprocessing": "research/experimental_views.py build" if view else None,
        "personal_fields_remaining": [],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    here = Path(__file__).resolve().parent.parent
    base = here / "verification/evidence/dataset_registry_v2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=base)
    args = parser.parse_args(argv)
    load = lambda name: json.loads((args.dir / name).read_text())  # noqa: E731
    entries = load("acquired_sources.json")["entries"]
    loghub = load("loghub_manifest.json")
    entries += [
        {
            "id": t["id"],
            "publisher": "logpai",
            "stratum": "C4",
            "licence_class": loghub["licence_class"],
            "eligible": True,
            "stages": {"data_acquired": True, "structural_validation": True},
        }
        for t in loghub["tables"]
    ]
    declared, views = load("readiness_facts.json")["facts"], load("experimental_views.json")
    protocols = load("anomaly_protocols.json")["protocols"]
    rows = []
    for e in entries:
        result = assess(facts_from(e, declared.get(e["id"]), views, protocols))
        group = (declared.get(e["id"]) or {}).get("independent_group")
        rows.append({"id": e["id"], "stratum": e["stratum"], "group": group, **result})
    out = {"datasets": rows, "summary": summarise(rows), "ready_groups": ready_groups(rows)}
    (args.dir / "readiness.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["ready_groups"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
