"""Every local file of the dataset pool must match the pinned manifest (pool_extension.md, P6).

``research/pool_check.py`` re-downloads the pool and compares it with the manifest on a hosted
runner. This check reads the files used by the studies on this machine, so that a changed or
missing file is caught before a result is computed from it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def local_path(entry_id: str, adbench: Path, pool: Path) -> Path | None:
    """The local file of a manifest entry, or ``None`` when it is not there."""
    kind, _, name = entry_id.partition(":")
    if kind == "uci":
        path = pool / f"{name}.csv"
        return path if path.is_file() else None
    matches = sorted(adbench.glob(f"*_{name}.npz")) if adbench.is_dir() else []
    return matches[0] if len(matches) == 1 else None


def check_pool(manifest: list[dict[str, Any]], adbench: Path, pool: Path) -> list[dict[str, str]]:
    report = []
    for entry in manifest:
        path = local_path(entry["id"], adbench, pool)
        if path is None:
            status = "missing"
        else:
            status = "ok" if sha256_file(path) == entry["sha256"] else "changed"
        report.append({"id": entry["id"], "status": status})
    return report


def summarize(report: list[dict[str, str]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in report:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"datasets": len(report), "counts": counts, "all_ok": counts.get("ok", 0) == len(report)}


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "verification/evidence/dataset_registry/pool_manifest.json",
    )
    parser.add_argument("--adbench", type=Path, default=root / "data" / "adbench")
    parser.add_argument("--pool", type=Path, default=root / "data" / "pool")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = check_pool(json.loads(args.manifest.read_text()), args.adbench, args.pool)
    result = {"summary": summarize(report), "report": report}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result["summary"]))
    return 0 if result["summary"]["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
