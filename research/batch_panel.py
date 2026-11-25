"""Which registry groups the batch unit of ``pipeline-batch-v1`` is defined for.

The batch protocol (verification/pipeline_batch_faults.md) replays a real timestamped table in time
order as successive loads and profiles its continuous columns. This audit applies that unit
definition, with the eligibility constants of the plumbing pilot, to the experimental views of the
registry. It reads tables and provenance only: no detector, fault or label is involved, and nothing
here selects a panel.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import pipeline_batch as pb

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "verification/evidence/dataset_registry_v2"
VIEWS = ROOT / "data/experimental"
TIME_HINTS = ("time", "date", "stamp")
MIN_PARSED = 0.99
# The eligibility constants of the plumbing pilot (chrono_injected.MIN_ROWS, MIN_COLUMNS, TREND and
# injection.MIN_DISTINCT). They are restated so that the audit does not import the detector stack;
# a test asserts that they stay equal to the originals.
MIN_ROWS, MIN_COLUMNS, TREND, MIN_DISTINCT = 1500, 4, 0.99, 10


def trend_columns(frame: pd.DataFrame, stamps: pd.Series) -> list[str]:
    """Numeric columns that are an index or counter of the time order (Spearman above TREND)."""
    rank = stamps.rank(method="first")
    return [
        c
        for c in frame.columns
        if pd.api.types.is_numeric_dtype(frame[c]) and abs(frame[c].corr(rank, "spearman")) > TREND
    ]


def continuous_columns(frame: pd.DataFrame) -> list[str]:
    """Numeric columns with at least MIN_DISTINCT distinct values (this also excludes booleans)."""
    return [
        c
        for c in frame.columns
        if pd.api.types.is_numeric_dtype(frame[c]) and frame[c].nunique() >= MIN_DISTINCT
    ]


def parse_time(column: pd.Series) -> pd.Series:
    """Instants of a column in UTC; text that cannot be read becomes missing."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(column, errors="coerce", utc=True)


def time_column(frame: pd.DataFrame) -> str | None:
    """First non-numeric column named like a time that parses (99 percent) to varying instants."""
    for name in frame.columns:
        column = frame[name]
        if any(hint in str(name).lower() for hint in TIME_HINTS) and not (
            pd.api.types.is_numeric_dtype(column)
        ):
            parsed = parse_time(column)
            if parsed.notna().mean() >= MIN_PARSED and parsed.nunique() > 1:
                return str(name)
    return None


def _report(reasons: list[str], name: str | None, columns: int, rows: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "eligible": not reasons,
        "reasons": reasons,
        "time_column": name,
        "columns": columns,
        "rows": rows,
    }
    if not reasons:
        k = pb.batch_size(rows)
        report |= {"batch_rows": k, "batches": rows // k}
    return report


def assess_table(frame: pd.DataFrame) -> dict[str, Any]:
    """Eligibility of one table under the batch unit, cleaned as ``pipeline_batch.load_table``."""
    name = time_column(frame)
    if name is None:
        return _report(["no parseable time column"], None, 0, 0)
    stamps = parse_time(frame[name])
    keep = stamps.notna()
    features = frame.drop(columns=[name])[keep]
    features = features.drop(columns=trend_columns(features, stamps[keep]))
    columns = continuous_columns(features)
    if len(columns) < MIN_COLUMNS:
        return _report([f"only {len(columns)} continuous columns"], name, len(columns), 0)
    rows = len(features[columns].dropna().drop_duplicates())
    reasons = [f"only {rows} rows after cleaning"] if rows < MIN_ROWS else []
    return _report(reasons, name, len(columns), rows)


def view_tables(views: Path, name: str) -> list[Path] | None:
    """CSV tables of a view: its directory, or the single file of a flat view; None if absent."""
    if (views / name).is_dir():
        return sorted((views / name).glob("*.csv"))
    flat = views / "flat" / f"{name}.csv"
    return [flat] if flat.is_file() else None


def attributed(fact_id: str, view: str, paths: list[Path], shared: bool) -> list[Path]:
    """Tables of the view that belong to one fact: all of them unless several facts share it.

    In a shared view a table belongs to the fact whose identifier equals its file stem or ends
    with it after an underscore (``uci:560`` and ``uci_560.csv``, ``ukspend_mhra`` and
    ``mhra.csv``); the base fact, named like the view, keeps every table.
    """
    if not shared or fact_id == view:
        return paths
    key = fact_id.lower().replace(":", "_")
    return [p for p in paths if key == p.stem.lower() or key.endswith("_" + p.stem.lower())]


def audit_view(views: Path, name: str, fact_id: str, shared: bool) -> dict[str, Any]:
    """Tables of a view that belong to the fact; eligible through its first eligible table."""
    found = view_tables(views, name)
    if found is None:
        return {
            "eligible": False,
            "reasons": [f"view {name} is not built locally"],
            "table": None,
            "tables": [],
        }
    paths = attributed(fact_id, name, found, shared)
    tables = [{"file": p.name, **assess_table(pd.read_csv(p))} for p in paths]
    chosen = next((t for t in tables if t["eligible"]), None)
    if chosen:
        return {"eligible": True, "reasons": [], "table": chosen, "tables": tables}
    reasons = (
        sorted({r for t in tables for r in t["reasons"]})
        if tables
        else ["no CSV table: the batch unit is not defined for this layout"]
    )
    return {"eligible": False, "reasons": reasons, "table": None, "tables": tables}


def audit_groups(facts: dict[str, Any], views: Path) -> dict[str, Any]:
    """Per provenance group, the audit of the tables of its facts; eligible through any fact."""
    per_view: dict[str, int] = {}
    for fact in facts.values():
        if fact.get("view"):
            per_view[fact["view"]] = per_view.get(fact["view"], 0) + 1
    by_group: dict[str, list[tuple[str, str]]] = {}
    for fact_id, fact in sorted(facts.items()):
        if fact.get("independent_group"):
            pairs = by_group.setdefault(fact["independent_group"], [])
            if fact.get("view"):
                pairs.append((fact_id, fact["view"]))
    out: dict[str, Any] = {}
    for group, pairs in sorted(by_group.items()):
        if not pairs:
            out[group] = {"eligible": False, "views": [], "reasons": ["no experimental view"]}
            continue
        audits = [(view, audit_view(views, view, f, per_view[view] > 1)) for f, view in pairs]
        first = next(((v, a) for v, a in audits if a["eligible"]), None)
        out[group] = {
            "eligible": first is not None,
            "view": first[0] if first else None,
            "views": sorted({view for _, view in pairs}),
            "reasons": [] if first else sorted({r for _, a in audits for r in a["reasons"]}),
            "table": first[1]["table"] if first else None,
        }
    return out


def summarise(audit: dict[str, Any], members: dict[str, list[str]]) -> dict[str, Any]:
    """Eligible groups overall and per category of the readiness contract."""
    ready = {g for groups in members.values() for g in groups} & set(audit)
    return {
        "groups": {"audited": len(ready), "eligible": sum(audit[g]["eligible"] for g in ready)},
        "per_category": {
            c: {
                "ready": len(set(g)),
                "eligible": sum(bool(audit.get(x, {}).get("eligible")) for x in set(g)),
            }
            for c, g in sorted(members.items())
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--views", type=Path, default=VIEWS)
    parser.add_argument("--output", type=Path, default=EVIDENCE / "batch_eligibility.json")
    args = parser.parse_args(argv)
    facts = json.loads((args.evidence / "readiness_facts.json").read_text())["facts"]
    members = json.loads((args.evidence / "readiness.json").read_text())["ready_groups"]
    audit = audit_groups(facts, args.views)
    report = {
        "protocol": pb.PROTOCOL,
        "rule": {
            "min_rows": MIN_ROWS,
            "min_continuous_columns": MIN_COLUMNS,
            "time_hints": list(TIME_HINTS),
            "min_parsed_share": MIN_PARSED,
        },
        "summary": summarise(audit, members),
        "groups": audit,
    }
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
