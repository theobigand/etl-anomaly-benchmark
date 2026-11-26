"""Utilization ledger (#133): the seven-stage status of every provenance group.

Stages, in order: acquired, structurally compatible, executable, executed, successfully evaluated,
included in the scientific analysis, and excluded with a documented justification. Each group holds
one explicit status per stage, and every status carries a reason when it is negative.

Evidence levels are kept apart so that a metadata check is never read as a result:

* ``metadata_only``: the registry facts say the group could fit a protocol;
* ``adapter_dry_run``: the real adapter of a registered execution path loaded the group, built its
  units and planned the evaluation, without fitting or scoring any detector;
* ``synthetic_end_to_end``: a path ran a detector on a synthetic fixture (a property of the path,
  proven by a named test, never of a group);
* ``scientific_execution``: a registry-driven scientific run produced a result for the group.

"Executable" means an approved execution path accepted the group in an adapter dry-run. Executed,
evaluated and included come only from an explicit executions record (none exists while the
experiment freeze is active), so ingestion, loading and metadata validation never count as
utilization. Nothing here fits a detector, injects a fault or reads a held-out outcome.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import batch_statistics as bs
import pandas as pd
import pipeline_batch as pb
import registry_units as ru
import study_coverage as sc

STAGES = (
    "acquired",
    "structurally_compatible",
    "executable",
    "executed",
    "evaluated",
    "included",
    "excluded",
)
LEVELS = ("metadata_only", "adapter_dry_run", "synthetic_end_to_end", "scientific_execution")
EVIDENCE = sc.EVIDENCE
OUTPUT = EVIDENCE / "utilization_ledger.json"
BATCH = "temporal_batch"
BATCH_METRICS = ("recall", "false_alert_rate", "roc_auc", "ap")
#: matching counts of the protocols (fault_protocols.match_exact / match_windows)
UNIT_METRICS = ("tp", "fp", "fn")
#: execution paths and the evidence each has on its own (not on any real group)
PATHS: dict[str, dict[str, Any]] = {
    BATCH: {
        "status": ru.REGISTERED,
        "adapter": "registry_units.load_group + pipeline_batch.make_batches + plan_group",
        "synthetic_end_to_end": (
            "research/tests/test_pipeline_batch.py::"
            "test_a_source_run_finds_gross_faults_misses_silent_ones_and_the_random_floor_is_near_chance"
        ),
    },
    "unit_level": {
        "status": "no_runner",
        "adapter": "none: only injector mechanics (fault_protocols) exist, with no registry-driven "
        "loader, partition or detector runner",
        "synthetic_end_to_end": None,
    },
}
#: the concrete implementation work that would make a group executable on some path
WORK_UNIT_LEVEL = "registry-driven unit-level runner for {protocol} (loader, partitions, detectors)"
WORK_BATCH_UNIT = "approve and implement the {unit} unit (no approved definition)"
WORK_BATCH_TABLE = "provide a timestamped numeric table for the batch unit (see the limitations)"


def dry_run_batch(entry: dict[str, Any], group: str, views: Path) -> dict[str, Any]:
    """Run the real batch adapter on one group up to the plan; no detector, no fault.

    Success needs the adapter to load the audited table, rebuild the audited number of batches and
    obtain non-empty reference, validation and test partitions.
    """
    try:
        table, info = ru.load_group(group, entry, views)
        batches = pb.make_batches(table)
        if len(batches) != entry["table"]["batches"]:
            raise ValueError(f"{len(batches)} batches rebuilt, {entry['table']['batches']} audited")
        plan = ru.plan_group(entry)
        if not all(plan["batches"].values()):
            raise ValueError("an empty reference, validation or test partition")
    except (ValueError, KeyError, OSError, StopIteration, pd.errors.ParserError) as error:
        return {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
    return {
        "status": "ok",
        "reason": "",
        "file": info["file"],
        "rows": len(table),
        "columns": len(info["columns"]),
        "plan": plan,
    }


def stage(status: bool, reason: str) -> dict[str, Any]:
    return {"status": "yes" if status else "no", "reason": "" if status else reason}


def stages_of(
    row: dict[str, Any],
    dry_run: dict[str, Any] | None,
    execution: dict[str, bool] | None,
    exclusion: str | None,
) -> dict[str, dict[str, Any]]:
    """The seven stages of one group; a later stage never holds without the earlier one it needs."""
    execution = execution or {}
    executed = bool(execution.get("executed"))
    evaluated = bool(execution.get("evaluated"))
    included = bool(execution.get("included"))
    compatible = row["unit_level"]["compatible"]
    ok = dry_run is not None and dry_run["status"] == "ok"
    if executed and not ok:
        raise ValueError("a group cannot be executed without a successful dry run")
    if evaluated and not executed:
        raise ValueError("a group cannot be evaluated without an execution")
    if included and not evaluated:
        raise ValueError("a group cannot be included without a successful evaluation")
    if exclusion and included:
        raise ValueError("a group cannot be both included and excluded")
    if dry_run is None:
        why_not = row["batch_approved"]["reasons"]
        executable_reason = "no registered path accepts the group: " + (
            "; ".join(why_not) if why_not else "not attempted"
        )
    else:
        executable_reason = f"the batch adapter dry run failed: {dry_run['reason']}"
    return {
        "acquired": stage(True, ""),
        "structurally_compatible": stage(compatible, row["unit_level"]["reason"]),
        "executable": stage(ok, executable_reason),
        "executed": stage(executed, "no registry-driven scientific run is recorded"),
        "evaluated": stage(evaluated, "not executed" if not executed else "evaluation failed"),
        "included": stage(
            included, "not evaluated" if not evaluated else "left out of the analysis"
        ),
        "excluded": {"status": "yes" if exclusion else "no", "reason": exclusion or ""},
    }


def evidence_level(stages: dict[str, dict[str, Any]], ok: bool) -> str:
    """Highest level reached by the group itself (synthetic evidence belongs to paths)."""
    if stages["executed"]["status"] == "yes":
        return "scientific_execution"
    if ok:
        return "adapter_dry_run"
    return "metadata_only" if stages["structurally_compatible"]["status"] == "yes" else "none"


def registry_participations(evidence: Path) -> dict[str, dict[str, str]]:
    """Protocol of each (group, category) participation: {group: {category: protocol}}.

    A group in several categories can fall under a different protocol in each (a sequence log
    in C4 and a table in C2b), so the protocol belongs to the participation, not to the group.
    """
    facts = json.loads((evidence / "readiness_facts.json").read_text())["facts"]
    registry = json.loads((evidence / "readiness.json").read_text())
    stratum = {d["id"]: d["stratum"] for d in registry["datasets"]}
    ready = {(g, c) for c, groups in registry["ready_groups"].items() for g in groups}
    found: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for fact_id, fact in facts.items():
        group, category = fact.get("independent_group"), stratum.get(fact_id)
        if (group, category) in ready:
            found[group][category].add(fact["protocol_id"])
    missing = sorted(f"{g}/{c}" for g, c in ready if not found[g][c])
    if missing:
        raise ValueError(f"participations without a protocol fact: {missing}")
    conflict = sorted(f"{g}/{c}" for g in found for c, ps in found[g].items() if len(ps) > 1)
    if conflict:
        raise ValueError(f"participations with several protocols: {conflict}")
    return {g: {c: next(iter(ps)) for c, ps in cats.items()} for g, cats in found.items()}


def provisional_units(protocols: list[str], entry: dict[str, Any]) -> list[dict[str, str]]:
    """Candidate units that are not registered, over every protocol of the group, once each."""
    seen: dict[str, str] = {}
    for protocol in protocols:
        for item in ru.compatibility(protocol, entry):
            if item["status"] != ru.REGISTERED:
                seen.setdefault(item["unit"], item["reason"])
    return [{"unit": unit, "reason": reason} for unit, reason in sorted(seen.items())]


def work_items(
    row: dict[str, Any], protocols: list[str], provisional: list[dict[str, str]], ok: bool
) -> list[str]:
    """Implementation work that remains before the group can contribute to an evaluation."""
    items = []
    if not row["unit_level"]["compatible"]:
        items.append("repair the structural compatibility: " + row["unit_level"]["reason"])
    if not ok:
        items += [WORK_UNIT_LEVEL.format(protocol=p) for p in protocols]
        if not row["batch_approved"]["eligible"]:
            items.append(WORK_BATCH_TABLE)
        items += [WORK_BATCH_UNIT.format(unit=u["unit"]) for u in provisional]
    return items


def group_entry(
    group: str,
    row: dict[str, Any],
    audit: dict[str, Any],
    protocols: dict[str, Any],
    by_category: dict[str, str],
    views: Path,
    execution: dict[str, bool] | None,
    exclusion: str | None,
    attempt: bool,
) -> dict[str, Any]:
    entry = audit[group]
    dry_run = dry_run_batch(entry, group, views) if attempt and entry["eligible"] else None
    ok = dry_run is not None and dry_run["status"] == "ok"
    stages = stages_of(row, dry_run, execution, exclusion)
    used = sorted(set(by_category.values()))
    provisional = provisional_units(used, entry)
    paths = [
        {
            "path": BATCH,
            "status": PATHS[BATCH]["status"],
            "dry_run": dry_run["status"] if dry_run else "not_applicable",
        },
        {"path": "unit_level", "status": PATHS["unit_level"]["status"], "dry_run": "not_available"},
    ]
    limitations = list(row["batch_approved"]["reasons"])
    limitations += [f"unit-level protocol {p} has no registry-driven runner" for p in used]
    limitations += [f"{u['unit']}: {u['reason']}" for u in provisional]
    return {
        "categories": row["categories"],
        "cluster": row["cluster"],
        "views": row["views"],
        "local_view_available": row["local_view_available"],
        "protocols": used,
        "participations": [
            {
                "category": category,
                "protocol": protocol,
                "detection_unit": protocols[protocol]["detection_unit"],
            }
            for category, protocol in sorted(by_category.items())
        ],
        "fault_operators": {
            "unit_level": {p: protocols[p]["mechanisms"] for p in used},
            BATCH: list(pb.MECHANISMS) if entry["eligible"] else [],
        },
        "detectors": {BATCH: list(pb.DETECTORS) if ok else [], "unit_level": []},
        "metrics": {
            BATCH: list(BATCH_METRICS) if ok else [],
            "unit_level": list(UNIT_METRICS),
        },
        "natural_labels": row["labels"]["natural_labels"],
        "label_origin": row["labels"]["origin"],
        "previous_exposure": bool(row["exposed"]),
        "paths": paths,
        "dry_run": dry_run,
        "evidence_level": evidence_level(stages, ok),
        "stages": stages,
        "limitations": limitations,
        "remaining_work": work_items(row, used, provisional, ok),
    }


def summarise(groups: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Counts of groups and clusters per stage, by category, protocol and evidence level."""

    def counts(members: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return {
            "groups": len(members),
            "clusters": len({g["cluster"] for g in members.values()}),
            "stages": {
                s: sum(g["stages"][s]["status"] == "yes" for g in members.values()) for s in STAGES
            },
            "stage_clusters": {
                s: len(
                    {g["cluster"] for g in members.values() if g["stages"][s]["status"] == "yes"}
                )
                for s in STAGES
            },
            "previous_exposure": sum(g["previous_exposure"] for g in members.values()),
            "natural_labels": sum(g["natural_labels"] for g in members.values()),
        }

    by_category: dict[str, dict[str, Any]] = defaultdict(dict)
    by_protocol: dict[str, dict[str, Any]] = defaultdict(dict)
    for category in sorted({c for g in groups.values() for c in g["categories"]}):
        by_category[category] = {
            g_id: g for g_id, g in groups.items() if category in g["categories"]
        }
    for protocol in sorted({p for g in groups.values() for p in g["protocols"]}):
        by_protocol[protocol] = {
            g_id: g for g_id, g in groups.items() if protocol in g["protocols"]
        }
    work: Counter[str] = Counter(w for g in groups.values() for w in g["remaining_work"])
    return {
        "total": counts(groups),
        "participations": sum(len(g["categories"]) for g in groups.values()),
        "by_category": {c: counts(m) for c, m in by_category.items()},
        "by_protocol": {p: counts(m) for p, m in by_protocol.items()},
        "evidence_levels": dict(
            sorted(Counter(g["evidence_level"] for g in groups.values()).items())
        ),
        "remaining_work": dict(sorted(work.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def build(
    evidence: Path,
    views: Path,
    executions: dict[str, dict[str, bool]] | None = None,
    exclusions: dict[str, str] | None = None,
    attempt: bool = True,
) -> dict[str, Any]:
    manifest = json.loads((evidence / "experimental_views.json").read_text())
    links = bs.load_links(evidence / "linked_sets.json")
    rows = sc.group_rows(evidence, views, links, manifest)
    audit = json.loads((evidence / "batch_eligibility.json").read_text())["groups"]
    protocols = json.loads((evidence / "anomaly_protocols.json").read_text())["protocols"]
    participations = registry_participations(evidence)
    executions, exclusions = executions or {}, exclusions or {}
    unknown = sorted((set(executions) | set(exclusions)) - set(rows))
    if unknown:
        raise ValueError(f"records name groups outside the registry: {unknown}")
    groups = {
        g: group_entry(
            g,
            r,
            audit,
            protocols,
            participations[g],
            views,
            executions.get(g),
            exclusions.get(g),
            attempt,
        )
        for g, r in rows.items()
    }
    return {
        "levels": list(LEVELS),
        "stages": list(STAGES),
        "paths": PATHS,
        "summary": summarise(groups),
        "groups": groups,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--views", type=Path, default=sc.VIEWS)
    parser.add_argument("--executions", type=Path)
    parser.add_argument("--exclusions", type=Path)
    parser.add_argument("--no-dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def load(path: Path | None) -> Any:
        return json.loads(path.read_text()) if path else None

    ledger = build(
        args.evidence,
        args.views,
        load(args.executions),
        load(args.exclusions),
        attempt=not args.no_dry_run,
    )
    text = json.dumps(ledger, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
