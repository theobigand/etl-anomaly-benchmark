"""Readiness assessment of flat tabular (C1) and categorical or mixed (C2a) tables.

The thresholds are fixed here, before any detector runs, and are documented in
``verification/dataset_target_methodology.md``. A provenance group is represented, per stratum,
by its largest eligible table; a group with no eligible table is rejected for that stratum with
the reasons of its tables. Nothing here reads a detector result.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

MIN_ROWS = {"C1": 300, "C2a": 500}
MIN_USABLE = {"C1": 4, "C2a": 5}
MAX_MISSING = 0.30
MAX_DUPLICATES = 0.50
MAX_COLUMN_MISSING = 0.50
MAX_ROWS = 50_000


def licence_class(text: str | None) -> str:
    """open for CC BY and CC0 families, research_only for the NC variants, else unclear."""
    upper = (text or "").upper()
    if re.search(r"(^|[^A-Z])NC([^A-Z]|$)", upper):
        return "research_only"
    if "CC BY" in upper or "CC0" in upper or "CREATIVE COMMONS ATTRIBUTION" in upper:
        return "open"
    return "unclear"


def profile(frame: pd.DataFrame) -> dict[str, Any]:
    """Sizes, informative column counts, categorical levels, missing and duplicate shares."""
    rows = len(frame)
    constant = [c for c in frame.columns if frame[c].nunique(dropna=True) <= 1]
    usable = [c for c in frame.columns if c not in constant]
    numeric = [c for c in usable if pd.api.types.is_numeric_dtype(frame[c])]
    categorical = [c for c in usable if c not in numeric]
    levels = [frame[c].nunique(dropna=True) for c in categorical]
    cells = rows * len(frame.columns)
    return {
        "rows": rows,
        "columns": len(frame.columns),
        "constant": len(constant),
        "usable": len(usable),
        "numeric": len(numeric),
        "categorical": len(categorical),
        "max_levels": max(levels) if levels else 0,
        "levels_ge3": sum(1 for n in levels if n >= 3),
        "missing_share": round(float(frame.isna().sum().sum()) / cells, 4) if cells else 0.0,
        "duplicate_share": round(float(frame.duplicated().sum()) / rows, 4) if rows else 0.0,
    }


def reasons(
    p: dict[str, Any],
    stratum: str,
    demographics: list[str] | None = None,
    licence_class: str = "open",  # noqa: A002 - the name of the field it checks
) -> list[str]:
    """Why a table is not eligible for the stratum (empty when it is), in a fixed order."""
    out = []
    if licence_class not in ("open", "research_only"):
        out.append("licence not open or research_only")
    if demographics:
        out.append("personal attributes listed by the publisher (privacy review pending)")
    if p["rows"] < MIN_ROWS[stratum]:
        out.append(f"fewer than {MIN_ROWS[stratum]} rows")
    if stratum == "C1" and p["numeric"] < 3:
        out.append("fewer than 3 informative numeric columns")
    if p["usable"] < MIN_USABLE[stratum]:
        out.append(f"fewer than {MIN_USABLE[stratum]} informative columns")
    if stratum == "C2a":
        if p["categorical"] < 2:
            out.append("fewer than 2 categorical columns")
        elif p["levels_ge3"] < 1:
            out.append("no categorical column with at least 3 levels")
    if p["missing_share"] > MAX_MISSING:
        out.append("more than 30 percent of values missing")
    if p["duplicate_share"] > MAX_DUPLICATES:
        out.append("more than half of the rows are duplicates")
    return out


def prepare(frame: pd.DataFrame, max_rows: int = MAX_ROWS) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Drop constant columns and columns missing in more than half of the rows; keep every
    ``stride``-th row (from the first) when the table exceeds ``max_rows``."""
    constant = [c for c in frame.columns if frame[c].nunique(dropna=True) <= 1]
    mostly = [
        c
        for c in frame.columns
        if c not in constant and frame[c].isna().mean() > MAX_COLUMN_MISSING
    ]
    kept = frame.drop(columns=constant + mostly)
    stride = max(1, int(np.ceil(len(kept) / max_rows)))
    out = kept.iloc[::stride].reset_index(drop=True) if stride > 1 else kept
    return out, {
        "rows_in": len(frame),
        "rows_out": len(out),
        "stride": stride,
        "dropped_constant": constant,
        "dropped_missing": mostly,
    }


def representatives(tables: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any] | None]:
    """Per (group, stratum): its largest eligible table (ties: smaller id), or None."""
    out: dict[tuple[str, str], dict[str, Any] | None] = {}
    for t in sorted(tables, key=lambda t: (t["group"], t["stratum"], -t["rows"], t["id"])):
        key = (t["group"], t["stratum"])
        out.setdefault(key, None)
        if not t["reasons"] and out[key] is None:
            out[key] = t
    return out


def assess(
    rows: list[dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    licences: dict[str, str],
    load: Any,
) -> list[dict[str, Any]]:
    """One record per audited source: group, stratum, profile and the reasons it is not eligible.

    ``rows`` are catalogue rows; twins (rows of one source) are listed with the first table.
    ``load(source)`` returns the table.
    """
    from provenance_audit import group_sources, stratum_of_row

    owned = [r for r in rows if stratum_of_row(r)]
    sources: dict[str, dict[str, Any]] = {}
    for row in owned:
        entry = sources.setdefault(
            row["source"], {"id": row["id"], "stratum": stratum_of_row(row), "twins": []}
        )
        if row["id"] != entry["id"]:
            entry["twins"].append(row["id"])
    groups = group_sources({s: metadata.get(s, {}) for s in sources})
    tables = []
    for source, info in sources.items():
        p = profile(load(source))
        cls = licence_class(licences.get(source))
        meta = metadata.get(source, {})
        tables.append(
            {
                "id": info["id"],
                "source": source,
                "group": groups[source],
                "stratum": info["stratum"],
                "twins": info["twins"],
                "rows": p["rows"],
                "profile": p,
                "licence": licences.get(source),
                "licence_class": cls,
                "area": meta.get("area"),
                "name": meta.get("name"),
                "reasons": reasons(p, info["stratum"], meta.get("demographics"), cls),
            }
        )
    return tables


def register(
    tables: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Readiness entries (one per group and stratum), facts of the represented groups, view list."""
    chosen = representatives(tables)
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in tables:
        by_group.setdefault((t["group"], t["stratum"]), []).append(t)
    entries, facts, views = [], {}, []
    for (group, stratum), rep in sorted(chosen.items()):
        key = f"flat:{group}:{stratum}"
        members = by_group[(group, stratum)]
        why = (
            f"representative table {rep['id']} ({rep['name']}): {rep['rows']} rows, "
            f"{rep['profile']['usable']} informative columns, licence {rep['licence']}"
            if rep
            else "no eligible table: "
            + "; ".join(f"{m['id']}: {', '.join(m['reasons'])}" for m in members)
        )
        entries.append(
            {
                "id": key,
                "family": group,
                "publisher": group,
                "stratum": stratum,
                "licence_class": (rep or members[0])["licence_class"],
                "eligible": rep is not None,
                "system": group,
                "upstream_status": "verified",
                "protocols": "P-TAB",
                "reason": why,
                "stages": {
                    "collection_implemented": True,
                    "data_acquired": True,
                    "discovered": True,
                    "licence_verified": "licence stated on the repository page of the table",
                    "ready_for_experiments": False,
                    "structural_validation": rep is not None,
                },
            }
        )
        if rep:
            view = "flat_" + re.sub(r"[^A-Za-z0-9]+", "_", f"{group}_{stratum}")
            facts[key] = {
                "anomaly_origin": "controlled_injection",
                "baseline_properties": [
                    f"{rep['rows']} rows and {rep['profile']['usable']} informative columns in the representative table",  # noqa: E501
                    f"{rep['profile']['missing_share']} share of missing values",
                    f"{len(members)} audited table(s) in this group and stratum",
                ],
                "first_party": False,
                "independent_group": group,
                "min_units": MIN_ROWS[stratum],
                "partitions": "hash of the row index 70/15/15",
                "privacy": "handled",
                "protocol_id": "P-TAB",
                "units": rep["rows"],
                "view": view,
            }
            views.append(
                {"key": view, "source": rep["source"], "table": rep["id"], "stratum": stratum}
            )
    return entries, facts, views


def main(argv: list[str] | None = None) -> int:
    import argparse
    import hashlib
    import json
    from pathlib import Path

    here = Path(__file__).resolve().parent
    import dataset_catalog as dc
    import uci_loader

    base = here.parent / "verification/evidence/dataset_registry_v2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=base)
    args = parser.parse_args(argv)
    root = here.parent
    metadata = {
        f"uci:{k}": v
        for k, v in json.loads((args.dir / "uci_metadata_cache.json").read_text()).items()
    }
    pool = json.loads((root / "verification/evidence/dataset_registry/uci_pool.json").read_text())
    wave2 = json.loads((args.dir / "uci_wave2_selection.json").read_text())
    licences = {f"uci:{r['uci_id']}": r["licence"] for r in pool["rows"]}
    licences.update({f"uci:{r['uci_id']}": r["licence"] for r in wave2["chosen"]})
    shas = {f"uci:{r['uci_id']}": r["sha256"] for r in pool["rows"]}
    wave_manifest = json.loads((args.dir / "uci_wave2_manifest.json").read_text())
    shas.update({f"uci:{t['uci_id']}": t["sha256"] for t in wave_manifest["tables"]})

    def path_of(source: str) -> Path:
        number = source.split(":", 1)[1]
        for folder in ("data/pool", "data/uci_wave2"):
            candidate = root / folder / f"{number}.csv"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(source)

    rows = [r for r in dc.stratum_rows() if str(r["source"]).startswith("uci:")]
    available = [r for r in rows if _has_file(path_of, r["source"])]
    changed = [
        r["source"]
        for r in available
        if hashlib.sha256(path_of(r["source"]).read_bytes()).hexdigest() != shas.get(r["source"])
    ]
    tables = assess(
        [r for r in available if r["source"] not in changed],
        metadata,
        licences,
        lambda source: uci_loader.read_table(path_of(source)),
    )
    entries, facts, views = register(tables)
    out = {
        "tables": tables,
        "views": views,
        "without_file": sorted({r["source"] for r in rows} - {r["source"] for r in available}),
        "checksum_mismatch": sorted(set(changed)),
    }
    (args.dir / "flat_selection.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    acquired = json.loads((args.dir / "acquired_sources.json").read_text())
    acquired["entries"] = [
        e for e in acquired["entries"] if not e["id"].startswith("flat:")
    ] + entries
    (args.dir / "acquired_sources.json").write_text(
        json.dumps(acquired, indent=1, sort_keys=True) + "\n"
    )
    declared = json.loads((args.dir / "readiness_facts.json").read_text())
    declared["facts"] = {k: v for k, v in declared["facts"].items() if not k.startswith("flat:")}
    declared["facts"].update(facts)
    (args.dir / "readiness_facts.json").write_text(
        json.dumps(declared, indent=1, sort_keys=True) + "\n"
    )
    print(
        f"{len(tables)} tables, {len(entries)} group entries, {len(facts)} represented, {len(views)} views"  # noqa: E501
    )
    return 0


def _has_file(path_of: Any, source: str) -> bool:
    try:
        path_of(source)
    except FileNotFoundError:
        return False
    return True


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "src")]
    raise SystemExit(main())
