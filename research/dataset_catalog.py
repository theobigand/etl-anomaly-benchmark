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
