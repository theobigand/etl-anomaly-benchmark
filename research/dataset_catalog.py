"""One logical catalog over the pool manifest, the legacy benchmark files and the time series.

The 152 pool entries stay in the archived ``pool_manifest.json`` (never rewritten); everything
else, the four historical CSV files and the naturally labelled series, is described in
``data/catalog.json`` and ``verification/evidence/natural_temporal/manifest.json``. This module
presents them through one interface: identity, role, local path, independent source and checksum.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import dataset_registry as dr  # noqa: E402

CATALOG = ROOT / "data" / "catalog.json"
POOL_MANIFEST = ROOT / "verification" / "evidence" / "dataset_registry" / "pool_manifest.json"
TEMPORAL_MANIFEST = ROOT / "verification" / "evidence" / "natural_temporal" / "manifest.json"
TEMPORAL_DIR = ROOT / "data" / "temporal"
# ADBench file stem -> UCI source id, so that twins share one independent source.
_TWIN = {name: uci_id for name, (uci_id, _title) in dr.UCI_SOURCES.items()}
#: roles whose entries add no independent real-world source
NOT_INDEPENDENT = ("synthetic", "duplicate_representation")


def source_key(dataset_id: str) -> str:
    """Independent underlying source: ADBench tables derived from a UCI set share its key."""
    kind, _, name = dataset_id.partition(":")
    if kind == "adbench" and name in _TWIN:
        return f"uci:{_TWIN[name]}"
    return dataset_id


def load(catalog: Path = CATALOG) -> dict[str, Any]:
    return json.loads(catalog.read_text())


def legacy_entries(catalog: Path = CATALOG) -> list[dict[str, Any]]:
    return load(catalog)["entries"]


def pool_ids(manifest: Path = POOL_MANIFEST) -> set[str]:
    return {e["id"] for e in json.loads(manifest.read_text())}


def resolve(entry: dict[str, Any], root: Path = ROOT) -> Path:
    """Local file of a catalog entry."""
    return root / entry["path"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_files(root: Path = ROOT, catalog: Path = CATALOG) -> dict[str, str]:
    """Status of each legacy file: ``ok``, ``missing`` or ``checksum differs``."""
    out = {}
    for entry in legacy_entries(catalog):
        path = resolve(entry, root)
        if not path.exists():
            out[entry["id"]] = "missing"
        else:
            out[entry["id"]] = "ok" if sha256(path) == entry["sha256"] else "checksum differs"
    return out


def problems(catalog: Path = CATALOG, manifest: Path = POOL_MANIFEST) -> list[str]:
    """Inconsistencies of the catalog: unknown targets, wrong source identity, bad roles."""
    data = load(catalog)
    pool = pool_ids(manifest)
    found = []
    seen: set[str] = set()
    for e in data["entries"]:
        if e["id"] in seen or e["id"] in pool:
            found.append(f"{e['id']}: identity is not unique")
        seen.add(e["id"])
        if e["role"] not in data["roles"]:
            found.append(f"{e['id']}: unknown role {e['role']}")
        if e["role"] == "duplicate_representation":
            target = e.get("same_as")
            if target not in pool:
                found.append(f"{e['id']}: same_as {target} is not in the pool")
            elif source_key(target) != e["source_identity"]:
                found.append(f"{e['id']}: source identity differs from that of {target}")
        elif e.get("same_as"):
            found.append(f"{e['id']}: only a duplicate representation may name same_as")
    return found


def independent_source_count(pool_sources: set[str], catalog: Path = CATALOG) -> dict[str, int]:
    """Sources added by the catalog entries: duplicates and synthetic data add none."""
    added = {
        e["source_identity"]
        for e in legacy_entries(catalog)
        if e["role"] not in NOT_INDEPENDENT and e["source_identity"] not in pool_sources
    }
    return {"pool": len(pool_sources), "added_by_supplementary": len(added)}


# Structural strata of the design decision (docs/thesis-remediation/DESIGN_DECISION_2026-11-21.md):
# (minimum, recommended, ambitious) independent source families per stratum.
STRATA = {
    "C1": "flat tabular",
    "C2": "transactional and categorical",
    "C3": "time series",
    "C4": "logs and event sequences",
    "C5": "relational",
    "C6": "nested",
}
TARGETS = {
    "C1": (15, 36, 50),
    "C2": (15, 30, 45),
    "C3": (15, 40, 55),
    "C4": (15, 28, 40),
    "C5": (15, 36, 55),
    "C6": (15, 30, 45),
}
WAVE2_MANIFEST = ROOT / "verification/evidence/dataset_registry_v2/uci_wave2_manifest.json"
WAVE2_TIME = ROOT / "verification/evidence/dataset_registry_v2/uci_wave2_time.json"
COVERAGE = ROOT / "verification/evidence/coverage/coverage_matrix.json"
NATURAL_RESULTS = ROOT / "verification/evidence/natural_temporal/results"
GAP_DIR = ROOT / "verification/evidence/dataset_registry_v2"


def stratum_of(row: dict[str, Any]) -> str:
    """Operational stratum of a source: an explicit one, else time, then categorical, else flat.

    A real time variable that a protocol has used (or a verified one) makes a source C3. Tables with
    categorical or mixed columns, or tagged transactional, are C2. Everything else is C1. Logs,
    relational and nested sources are never inferred: they need an explicit ``stratum``.
    """
    if row.get("stratum"):
        return row["stratum"]
    if row.get("time_verified"):
        return "C3"
    tagged = set(row.get("tags") or [])
    if row.get("schema_kind") in ("categorical", "mixed") or tagged & {
        "transactional",
        "categorical_only",
    }:
        return "C2"
    return "C1"


def stratum_rows(
    coverage: Path = COVERAGE,
    wave2: Path = WAVE2_MANIFEST,
    natural: Path = NATURAL_RESULTS,
    wave2_time: Path = WAVE2_TIME,
) -> list[dict[str, Any]]:
    """One row per table or series, with its independent source and the facts the strata need."""
    rows: list[dict[str, Any]] = []
    if coverage.exists():
        for d in json.loads(coverage.read_text())["datasets"]:
            if d["decision"] == "retired":
                continue
            p = d["protocols"]
            verified = (
                p["chronological"]["status"] == "executed"
                or p["chronological_injected_classical"]["status"] == "executed"
            )
            rows.append(
                {
                    "id": d["id"],
                    "source": d["independent_source"],
                    "schema_kind": d["schema_kind"],
                    "time_verified": verified,
                    "origin": "first_pool",
                }
            )
    if wave2.exists():
        checked = json.loads(wave2_time.read_text()) if wave2_time.exists() else {}
        for t in json.loads(wave2.read_text())["tables"]:
            rows.append(
                {
                    "id": f"uci:{t['uci_id']}",
                    "source": f"uci:{t['uci_id']}",
                    "tags": t["tags"],
                    "time_verified": bool(checked.get(f"uci:{t['uci_id']}", {}).get("verified")),
                    "time_candidate": bool(t["time_candidates"]),
                    "origin": "wave2",
                }
            )
    if natural.exists():
        for path in sorted(natural.glob("*.json")):
            r = json.loads(path.read_text())
            if "chronological" in r:
                rows.append(
                    {
                        "id": r["id"],
                        "source": f"natural:{r['group']}",
                        "time_verified": True,
                        "origin": "natural_temporal",
                    }
                )
    return rows


#: licence-classified manifests (path, stratum): one entry per independent system or database
LICENCE_MANIFESTS = [(GAP_DIR / "loghub_manifest.json", "C4")]


def licence_rows(manifests: list[tuple[Path, str]]) -> list[dict[str, Any]]:
    """Rows of manifests that carry a licence class (open or research_only) and an explicit stratum."""
    rows: list[dict[str, Any]] = []
    for path, stratum in manifests:
        if not path.exists():
            continue
        manifest = json.loads(path.read_text())
        for t in manifest["tables"]:
            rows.append(
                {
                    "id": t["id"],
                    "source": t["id"],
                    "stratum": stratum,
                    "licence_class": manifest["licence_class"],
                    "origin": "licence_manifest",
                }
            )
    return rows


def gap_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Independent source families per stratum against the targets (once per stratum)."""
    seen: dict[str, set[str]] = {k: set() for k in STRATA}
    candidates: set[str] = set()
    for r in rows:
        seen[stratum_of(r)].add(r["source"])
        if r.get("time_candidate") and not r.get("time_verified"):
            candidates.add(r["source"])
    table = {}
    for k, label in STRATA.items():
        low, rec, amb = TARGETS[k]
        n = len(seen[k])
        table[k] = {
            "stratum": label,
            "sources": n,
            "minimum": low,
            "recommended": rec,
            "ambitious": amb,
            "missing_to_minimum": max(0, low - n),
            "missing_to_recommended": max(0, rec - n),
        }
    classes: dict[str, set[str]] = {}
    for r in rows:
        classes.setdefault(r.get("licence_class", "open"), set()).add(r["source"])
    return {
        "licence_classes": {k: len(v) for k, v in sorted(classes.items())},
        "strata": table,
        "time_candidates_not_yet_verified": sorted(candidates),
        "total_sources": len(set().union(*seen.values())),
    }


def render_gap(report: dict[str, Any]) -> str:
    lines = [
        "# Independent source families per stratum against the targets",
        "",
        "| Stratum | Sources now | Minimum | Recommended | Ambitious | Missing to recommended |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for k, v in report["strata"].items():
        lines.append(
            f"| {k} {v['stratum']} | {v['sources']} | {v['minimum']} | {v['recommended']} "
            f"| {v['ambitious']} | {v['missing_to_recommended']} |"
        )
    lines += [
        "",
        "Licence classes (sources): "
        + ", ".join(f"{k} {v}" for k, v in report["licence_classes"].items())
        + ".",
        "",
        f"Distinct source families: {report['total_sources']}. Wave-2 tables with a time-column "
        f"candidate that is not yet verified as a single chronological series: "
        f"{len(report['time_candidates_not_yet_verified'])}.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gap",))
    parser.add_argument("--out", type=Path, default=GAP_DIR)
    args = parser.parse_args(argv)
    report = gap_report([*stratum_rows(), *licence_rows(LICENCE_MANIFESTS)])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "stratum_gap.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    (args.out / "stratum_gap.md").write_text(render_gap(report))
    print(render_gap(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
