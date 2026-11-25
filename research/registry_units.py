"""Registry-driven units of the batch study: representations, compatibility, loading and planning.

The batch protocol (verification/pipeline_batch_faults.md) registers one experimental unit, the
temporal batch of a timestamped numeric table. This module resolves registry groups to that unit
through ``batch_panel`` (one rule for every view, no privileged source), states which other
representations would need a design decision, and loads a group's table for the harness. Running a
detector on a group needs an authorization record naming the step and the groups; without one the
module only plans.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import batch_panel as bp
import numpy as np
import pandas as pd
import pipeline_batch as pb

ROOT = bp.ROOT
EVIDENCE = bp.EVIDENCE
TIME = pb.TIME
REGISTERED, PROPOSED = "registered", "proposed"
ALL = tuple(pb.MECHANISMS)
#: unit -> (status, mechanisms defined for it). A proposed unit has no approved definition yet, so
#: it is neither eligible nor run; its mechanisms are the ones whose meaning carries over.
UNITS: dict[str, tuple[str, tuple[str, ...]]] = {
    "temporal_batch": (REGISTERED, ALL),
    "event_window": (PROPOSED, ("partial_load", "duplicate_load", "stale_batch", "schema_drop")),
    "relational_load": (
        PROPOSED,
        ("partial_load", "duplicate_load", "stale_batch", "null_spike", "referential_integrity"),
    ),
    "document_batch": (
        PROPOSED,
        ("partial_load", "duplicate_load", "stale_batch", "null_spike", "schema_drop"),
    ),
}
#: protocol of the registry facts -> units that could apply to it, in order of preference
PROTOCOL_UNITS: dict[str, tuple[str, ...]] = {
    "P-TS": ("temporal_batch",),
    "P-TAB": ("temporal_batch",),
    "P-SEQ": ("temporal_batch", "event_window"),
    "P-REL": ("temporal_batch", "relational_load"),
    "P-NEST": ("document_batch",),
}
#: detectors read the profile of a temporal batch; no other unit has a profile yet
DETECTOR_UNITS = ("temporal_batch",)


def group_protocols(facts: dict[str, Any]) -> dict[str, str]:
    """Protocol identifier per provenance group (the first fact in identifier order)."""
    out: dict[str, str] = {}
    for _, fact in sorted(facts.items()):
        group = fact.get("independent_group")
        if group and group not in out:
            out[group] = fact["protocol_id"]
    return out


def compatibility(protocol: str, entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Per candidate unit of the protocol: whether it can be run and why not.

    ``unsupported`` is a missing definition or table (the group is not invalid for the unit in
    principle); the batch unit is ``runnable`` exactly when the audit found an eligible table.
    """
    rows = []
    for unit in PROTOCOL_UNITS[protocol]:
        status, mechanisms = UNITS[unit]
        runnable = unit == "temporal_batch" and bool(entry["eligible"])
        if runnable:
            reason = ""
        elif status == PROPOSED:
            reason = "unsupported: the unit has no approved definition"
        else:
            reason = "; ".join(entry["reasons"])
        rows.append(
            {
                "unit": unit,
                "status": status,
                "runnable": runnable,
                "mechanisms": list(mechanisms),
                "detectors": unit in DETECTOR_UNITS,
                "reason": reason,
            }
        )
    return rows


def clean_table(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """The replayed table of the harness: continuous columns plus the parsed time, time-ordered.

    The cleaning is that of ``pipeline_batch.load_table`` (time-ordered, complete rows, no repeated
    rows) applied to a table whose time column is found by content.
    """
    report = bp.assess_table(frame)
    if not report["eligible"]:
        raise ValueError(report["reasons"][0])  # one reason: the first rule that failed
    name = str(report["time_column"])
    stamps = bp.parse_time(frame[name])
    keep = stamps.notna()
    features = frame.drop(columns=[name])[keep]
    features = features.drop(columns=bp.trend_columns(features, stamps[keep]))
    columns = bp.continuous_columns(features)
    table = features[columns].astype("float64").assign(**{TIME: stamps[keep].dt.tz_localize(None)})
    order = np.lexsort((np.arange(len(table)), table[TIME].to_numpy()))  # time, then file order
    table = table.iloc[order].dropna().drop_duplicates(subset=columns)
    return table.reset_index(drop=True), {"time_column": name, "columns": columns}


def load_group(
    group: str, entry: dict[str, Any], views: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """The table of an eligible group, from the table the audit chose."""
    if not entry["eligible"]:
        raise ValueError(f"{group} is not eligible: {'; '.join(entry['reasons'])}")
    paths = bp.view_tables(views, entry["view"]) or []
    path = next(p for p in paths if p.name == entry["table"]["file"])
    table, info = clean_table(pd.read_csv(path))
    return table, {"group": group, "view": entry["view"], "file": path.name, **info}


def cells(detectors: int, seeds: int = len(pb.SEEDS)) -> int:
    """Detector evaluations of one group: arms x seeds x mechanisms x severities x detectors."""
    return 2 * seeds * len(pb.MECHANISMS) * len(pb.LEVELS) * detectors


def plan_group(entry: dict[str, Any], compact: bool = False) -> dict[str, Any]:
    """Batches, split and evaluation count of one eligible group, from the audit alone."""
    batches = entry["table"]["batches"]
    ref, val, test = pb.split_batches(batches)
    detectors = len(pb.DETECTORS) - len(pb.LEARNED if compact else pb.COMPACT)
    return {
        "batch_rows": entry["table"]["batch_rows"],
        "batches": {"reference": len(ref), "validation": len(val), "test": len(test)},
        "evaluations": cells(detectors),
    }


def check_authorization(path: Path | None, step: str, groups: list[str]) -> None:
    """Refuse a detector run without a record that names the step and every group."""
    if path is None:
        raise PermissionError("a detector run needs --authorization naming the step and groups")
    record = json.loads(path.read_text())
    if record.get("step") != step:
        raise PermissionError(f"the authorization is for step {record.get('step')!r}, not {step!r}")
    missing = sorted(set(groups) - set(record.get("groups", [])))
    if missing:
        raise PermissionError(f"groups not covered by the authorization: {missing}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("compatibility", "plan", "run"))
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--views", type=Path, default=bp.VIEWS)
    parser.add_argument("--audit", type=Path, default=EVIDENCE / "batch_eligibility.json")
    parser.add_argument("--groups", nargs="*", default=[])
    parser.add_argument("--step", default="")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compact", action="store_true")
    return parser


def run_groups(args: argparse.Namespace, audit: dict[str, Any], chosen: list[str]) -> None:
    """Run both arms on each chosen group and write one atomic result file per group."""
    from etl_benchmark.atomic import atomic_path

    check_authorization(args.authorization, args.step, chosen)
    if args.output is None:
        raise SystemExit("--output is required to run")
    args.output.mkdir(parents=True, exist_ok=True)
    learned = pb.COMPACT if args.compact else pb.LEARNED
    for group in chosen:
        table, info = load_group(group, audit[group], args.views)
        arms = {
            "clean_reference": pb.run_source(table, learned=learned),
            "contaminated_reference": pb.run_source(table, contaminated=True, learned=learned),
        }
        with atomic_path(args.output / f"{group}.json") as partial:
            partial.write_text(
                json.dumps({"id": group, **info, "arms": arms}, sort_keys=True) + "\n"
            )
        print(group, flush=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    facts = json.loads((args.evidence / "readiness_facts.json").read_text())["facts"]
    audit = json.loads(args.audit.read_text())["groups"]
    chosen = args.groups or sorted(g for g, e in audit.items() if e["eligible"])
    unknown = sorted(set(chosen) - set(audit))
    if unknown:
        raise SystemExit(f"unknown groups: {unknown}")
    if args.command == "run":
        run_groups(args, audit, chosen)
        return 0
    if args.command == "compatibility":
        protocols = group_protocols(facts)
        report: Any = {g: compatibility(protocols[g], audit[g]) for g in sorted(audit)}
    else:
        rows = {g: plan_group(audit[g], args.compact) for g in chosen if audit[g]["eligible"]}
        evaluations = sum(r["evaluations"] for r in rows.values())
        report = {"groups": rows, "totals": {"groups": len(rows), "evaluations": evaluations}}
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
