"""Structural dry run of the unit-level protocols (#135, #137, #138, #139).

One adapter per registry protocol (P-TAB, P-TS, P-SEQ, P-REL, P-NEST) checks that a source's view
has the structure its experimental unit needs, and reports a source-specific reason otherwise.
The rule of an adapter depends on the protocol and on the structure of the data alone: no group,
view or dataset name appears in this module, so no source has a privileged path.

What a dry run does and does not do:

* it checks the digest of each file against the view manifest, reads at most ``PROBE`` rows of a
  table to learn column kinds, and reports counts, column names and kinds;
* it never returns a cell value, never reads a column whose name belongs to the ground-truth
  vocabulary, and never fits, scores or injects anything;
* its verdict is structural evidence. It does not make a group *executable* in the utilization
  ledger (no approved execution path with a detector runner exists for these protocols) and it
  never counts as a scientific execution. Units other than the registered temporal batch stay
  provisional until the protocol amendment (S03, #152 to #154) approves them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import batch_panel as bp
import compatibility_model as cm
import obs_redaction as orr
import pandas as pd
import relational_units as rel
import utilization_ledger as ul

PROBE = 5000
EVIDENCE = bp.EVIDENCE
OUTPUT = EVIDENCE / "structural_dry_run.json"
CODES = (
    "view_missing",
    "no_table",
    "digest_mismatch",
    "too_few_units",
    "no_time_axis",
    "no_value_column",
    "no_event_type",
    "no_event_order",
    "no_relationship",
    "no_nesting",
    "malformed_document",
    "unsupported_protocol",
    "adapter_error",
)
#: the unit-level protocols have no detector runner and the freeze forbids a scientific run
NUMERIC_AXIS = "numeric epoch or elapsed-time axes are not recognised by this adapter"
FREEZE_REASON = "the experiment freeze is active and no detector runner exists for this protocol"


@dataclass(frozen=True)
class Verdict:
    """The structural outcome of one participation; ``facts`` holds counts and names only."""

    group: str
    category: str
    protocol: str
    unit: str
    unit_status: str
    ok: bool
    code: str = ""
    reason: str = ""
    facts: dict[str, Any] = field(default_factory=dict)


class Failure(Exception):
    """A structural reason: a code from ``CODES`` and a sentence naming the source's fact."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code, self.reason = code, reason


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def check_files(paths: list[Path], entry: dict[str, Any], root: Path) -> None:
    """Every file must match the digest the view manifest recorded for its path in the view."""
    for path in paths:
        key = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name
        recorded = entry.get("files", {}).get(key, {}).get("sha256")
        if recorded and digest(path) != recorded:
            raise Failure("digest_mismatch", f"{key} differs from the manifest digest")


def allowed_columns(path: Path) -> list[str]:
    """Header names that are not ground-truth vocabulary; those are never read."""
    header = pd.read_csv(path, nrows=0).columns
    return [c for c in header if not orr.GROUND_TRUTH_NAME.search(str(c))]


def probe(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """A bounded prefix of the table without the withheld columns, and the withheld names."""
    keep = allowed_columns(path)
    header = list(pd.read_csv(path, nrows=0).columns)
    return pd.read_csv(path, nrows=PROBE, usecols=keep), [c for c in header if c not in keep]


def rows_of(entry: dict[str, Any], path: Path) -> int:
    return int(entry.get("files", {}).get(path.name, {}).get("rows", 0))


def csv_tables(paths: list[Path]) -> list[Path]:
    tables = [p for p in paths if p.suffix == ".csv"]
    if not tables:
        raise Failure("no_table", "the view holds no CSV table")
    return tables


def adapt_tab(
    paths: list[Path], entry: dict[str, Any], fact: dict[str, Any], views: Path
) -> dict[str, Any]:
    """P-TAB, unit ``row``: a table with enough rows and at least one value column."""
    best: dict[str, Any] = {}
    for path in csv_tables(paths):
        frame, withheld = probe(path)
        columns = list(frame.columns)
        values = bp.continuous_columns(frame) if len(frame) else []
        categorical = [c for c in columns if c not in values]
        rows = rows_of(entry, path)
        if rows >= fact["min_units"] and (values or categorical):
            return {
                "table": path.name,
                "rows": rows,
                "columns": len(columns),
                "continuous_columns": len(values),
                "withheld_columns": withheld,
            }
        best = best or {"rows": rows}
    if best.get("rows", 0) < fact["min_units"]:
        raise Failure("too_few_units", f"{best.get('rows', 0)} rows, {fact['min_units']} needed")
    raise Failure("no_value_column", "no table has a usable column")


def adapt_ts(
    paths: list[Path], entry: dict[str, Any], fact: dict[str, Any], views: Path
) -> dict[str, Any]:
    """P-TS, unit ``time_window``: a time axis and at least one numeric column."""
    reasons: list[Failure] = []
    for path in csv_tables(paths):
        frame, withheld = probe(path)
        axis = bp.time_column(frame)
        if axis is None:
            reasons.append(
                Failure(
                    "no_time_axis",
                    f"{path.name} has no parseable instant column; {NUMERIC_AXIS}",
                )
            )
            continue
        values = bp.continuous_columns(frame.drop(columns=[axis]))
        rows = rows_of(entry, path)
        if not values:
            reasons.append(Failure("no_value_column", f"{path.name} has no numeric column"))
        elif rows < fact["min_units"]:
            reasons.append(Failure("too_few_units", f"{rows} rows, {fact['min_units']} needed"))
        else:
            ordered = bool(bp.parse_time(frame[axis]).is_monotonic_increasing)
            return {
                "table": path.name,
                "rows": rows,
                "time_column": axis,
                "time_ordered_in_probe": ordered,
                "numeric_columns": len(values),
                "withheld_columns": withheld,
            }
    raise reasons[0]


def adapt_seq(
    paths: list[Path], entry: dict[str, Any], fact: dict[str, Any], views: Path
) -> dict[str, Any]:
    """P-SEQ, unit ``event_sequence``: an event order and an event type with a bounded alphabet."""
    reasons: list[Failure] = []
    for path in csv_tables(paths):
        frame, withheld = probe(path)
        axis = bp.time_column(frame)
        ordinal = [
            c
            for c in frame.columns
            if pd.api.types.is_integer_dtype(frame[c]) and frame[c].is_monotonic_increasing
        ]
        kinds = [
            c
            for c in frame.columns
            if c != axis and c not in ordinal and not pd.api.types.is_float_dtype(frame[c])
        ]
        kinds = [c for c in kinds if 2 <= frame[c].nunique() <= max(50, len(frame) // 2)]
        rows = rows_of(entry, path)
        if axis is None and not ordinal:
            reasons.append(
                Failure(
                    "no_event_order",
                    f"{path.name} has no instant or increasing integer column; {NUMERIC_AXIS}",
                )
            )
        elif not kinds:
            reasons.append(Failure("no_event_type", f"{path.name} has no event-type column"))
        elif rows < fact["min_units"]:
            reasons.append(Failure("too_few_units", f"{rows} rows, {fact['min_units']} needed"))
        else:
            return {
                "table": path.name,
                "events": rows,
                "order_column": axis or ordinal[0],
                "event_type_candidates": len(kinds),
                "withheld_columns": withheld,
            }
    raise reasons[0]


def adapt_rel(
    paths: list[Path], entry: dict[str, Any], fact: dict[str, Any], views: Path
) -> dict[str, Any]:
    """P-REL, unit ``relationship``: declared foreign keys whose columns exist in the tables."""
    keys = rel.declared_keys({fact["view"]: entry}).get(fact["view"], [])
    tables = {p.stem: set(allowed_columns(p)) for p in csv_tables(paths)}
    usable = [
        (fk, count)
        for fk, count in keys
        if fk.child in tables
        and fk.parent in tables
        and set(fk.columns) <= tables[fk.child]
        and set(fk.parent_columns) <= tables[fk.parent]
    ]
    if not usable:
        reason = (
            "no declared foreign key has its tables and columns in the view"
            if keys
            else "the view manifest declares no foreign key"
        )
        raise Failure("no_relationship", reason)
    return {"tables": len(tables), "relationships": len(usable)}


def paths_of(node: Any, prefix: str = "") -> set[str]:
    """Distinct structural paths of a document; array positions collapse to ``[]``."""
    out: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{prefix}.{key}" if prefix else str(key)
            out.add(here)
            out |= paths_of(value, here)
    elif isinstance(node, list):
        out.add(prefix + "[]")
        for item in node:
            out |= paths_of(item, prefix + "[]")
    return out


def adapt_nest(
    paths: list[Path], entry: dict[str, Any], fact: dict[str, Any], views: Path
) -> dict[str, Any]:
    """P-NEST, unit ``nested_path``: JSON-lines documents that keep nested objects or arrays."""
    documents = [p for p in paths if p.suffix == ".jsonl"]
    if not documents:
        raise Failure("no_table", "the view holds no JSON-lines document file")
    seen: set[str] = set()
    parsed = bad = 0
    with documents[0].open() as handle:
        for line in handle:
            if parsed + bad >= PROBE:
                break
            try:
                seen |= paths_of(json.loads(line))
                parsed += 1
            except ValueError:
                bad += 1
    if not parsed:
        raise Failure("malformed_document", f"none of {bad} probed lines is a JSON document")
    nested = sorted(p for p in seen if "." in p or "[]" in p)
    if not nested:
        raise Failure("no_nesting", "every probed document is flat")
    return {
        "file": documents[0].name,
        "documents_probed": parsed,
        "malformed_probed": bad,
        "paths": len(seen),
        "nested_paths": len(nested),
    }


ADAPTERS: dict[str, Callable[..., dict[str, Any]]] = {
    "P-TAB": adapt_tab,
    "P-TS": adapt_ts,
    "P-SEQ": adapt_seq,
    "P-REL": adapt_rel,
    "P-NEST": adapt_nest,
}


def select_paths(
    protocol: str, fact_id: str, view: str, root: Path, shared: bool, flat: bool
) -> list[Path]:
    """The files that carry the fact: the whole relational structure, the documents, or its tables.

    A relational fact owns every table of the view (a ``view:subset`` fact only the folder named
    ``subset``), a nested fact its JSON-lines files, and a tabular fact the tables the batch audit
    attributes to it; when none is attributed, a derived fact falls back to the tables of the view.
    """
    if flat:
        return [root / f"{view}.csv"]
    everything = sorted(p for p in root.rglob("*") if p.is_file())
    if protocol == "P-REL":
        subset = fact_id.partition(":")[2]
        scoped = [p for p in everything if subset and p.parent.name == subset]
        return [p for p in (scoped or everything) if p.suffix == ".csv"]
    if protocol == "P-NEST":
        return [p for p in everything if p.suffix == ".jsonl"]
    tables = [p for p in everything if p.parent == root and p.suffix == ".csv"]
    return bp.attributed(fact_id, view, tables, shared) or tables


def availability(protocol: str, unit: str) -> dict[str, Any]:
    """Whether a scientific run exists for the unit; the answer is no while the freeze holds."""
    _kind, status, _basis = cm.UNITS[unit]
    return {
        "protocol": protocol,
        "unit": unit,
        "unit_status": status,
        "scientific_execution": False,
        "reason": FREEZE_REASON,
    }


def dry_run(
    group: str,
    category: str,
    protocol: str,
    unit: str,
    fact_id: str,
    fact: dict[str, Any],
    views: Path,
    manifest: dict[str, Any],
    shared: bool,
) -> Verdict:
    """One participation; any structural or adapter failure becomes a verdict, never a raise."""
    status = cm.UNITS[unit][1]
    base = {"group": group, "category": category, "protocol": protocol, "unit": unit}
    base["unit_status"] = status
    try:
        adapter = ADAPTERS.get(protocol)
        if adapter is None:
            raise Failure("unsupported_protocol", f"no adapter for {protocol}")
        view = fact["view"]
        if not (views / view).is_dir() and not (views / "flat" / f"{view}.csv").is_file():
            raise Failure("view_missing", f"view {view} is not built locally")
        flat = not (views / view).is_dir()
        root = views / "flat" if flat else views / view
        paths = select_paths(protocol, fact_id, view, root, shared, flat)
        check_files(paths, manifest.get(view, {}), root)
        facts = adapter(paths, manifest.get(view, {}), fact, views)
        return Verdict(ok=True, facts=facts, **base)  # type: ignore[arg-type]
    except Failure as failure:
        return Verdict(ok=False, code=failure.code, reason=failure.reason, **base)  # type: ignore[arg-type]
    except Exception as error:  # an adapter bug or unreadable file is reported, not hidden
        reason = f"{type(error).__name__}: {error}"[:300]
        return Verdict(ok=False, code="adapter_error", reason=reason, **base)  # type: ignore[arg-type]


def run(evidence: Path, views: Path) -> dict[str, Any]:
    """Every registry participation, dispatched by its protocol and its detection unit."""
    facts = json.loads((evidence / "readiness_facts.json").read_text())["facts"]
    registry = json.loads((evidence / "readiness.json").read_text())
    stratum = {d["id"]: d["stratum"] for d in registry["datasets"]}
    manifest = json.loads((evidence / "experimental_views.json").read_text())
    protocols = json.loads((evidence / "anomaly_protocols.json").read_text())["protocols"]
    participations = ul.registry_participations(evidence)
    per_view = Counter(fact["view"] for fact in facts.values())
    out: dict[str, list[dict[str, Any]]] = {}
    for group, by_category in sorted(participations.items()):
        for category, protocol in sorted(by_category.items()):
            members = [
                (fid, f)
                for fid, f in sorted(facts.items())
                if f.get("independent_group") == group and stratum.get(fid) == category
            ]
            unit = protocols[protocol]["detection_unit"]
            verdicts = [
                dry_run(
                    group,
                    category,
                    protocol,
                    unit,
                    fid,
                    f,
                    views,
                    manifest,
                    per_view[f["view"]] > 1,
                )
                for fid, f in members
            ]
            chosen = next((v for v in verdicts if v.ok), verdicts[0])
            out.setdefault(group, []).append(asdict(chosen))
    return {
        "access": access_record(),
        "groups": out,
        "summary": summarise(out),
        "availability": availabilities(protocols),
    }


def access_record() -> dict[str, Any]:
    """What a run touches, so that the access can be judged against the exposure rules."""
    return {
        "operations": [
            "sha256 of each view file, compared with the view manifest",
            f"header and at most {PROBE} leading rows of each CSV table, to learn column kinds",
            f"at most {PROBE} leading lines of the first JSON-lines file, parsed for paths",
        ],
        "returned": "counts, column names, column kinds and reasons; never a cell value",
        "withheld": "columns whose name belongs to the ground-truth vocabulary are never read",
        "not_done": "no detector fit or inference, no score, no metric, no injection, no selection",
        "ledger_effect": "none: a structural verdict does not make a group executable or exposed",
    }


def availabilities(protocols: dict[str, Any]) -> dict[str, Any]:
    return {p: availability(p, spec["detection_unit"]) for p, spec in sorted(protocols.items())}


def summarise(groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Counts by category and by reason; participations are not groups."""
    by_category: dict[str, dict[str, int]] = {}
    reasons: dict[str, int] = {}
    for rows in groups.values():
        for row in rows:
            cell = by_category.setdefault(row["category"], {"participations": 0, "passed": 0})
            cell["participations"] += 1
            cell["passed"] += row["ok"]
            if not row["ok"]:
                reasons[row["code"]] = reasons.get(row["code"], 0) + 1
    return {"by_category": by_category, "failure_codes": reasons}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--views", type=Path, default=bp.VIEWS)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = json.dumps(run(args.evidence, args.views), indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
