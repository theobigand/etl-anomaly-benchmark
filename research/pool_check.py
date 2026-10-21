"""Pinned manifest of the pooled datasets and the check that every download still matches it.

Nothing is stored: each file is downloaded into memory, hashed and dropped, so the check can run
on a hosted runner without redistributing any raw data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dataset_registry as dr  # noqa: E402


def build_manifest(inventory: list[dict[str, Any]], uci_rows: list[dict[str, Any]]):
    manifest = [
        {
            "id": f"adbench:{r['name']}",
            "url": r["source_url"],
            "sha256": r["sha256"],
            "licence": r["underlying_terms"],
        }
        for r in inventory
        if r["decision"] == "INCLUDE"
    ]
    manifest += [
        {
            "id": f"uci:{r['uci_id']}",
            "url": r["url"],
            "sha256": r["sha256"],
            "licence": r["licence"],
        }
        for r in uci_rows
    ]
    return manifest


def _download(url: str, opener, sleep, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            return dr._download(url, opener, dr.MAX_BYTES)
        except OSError:
            if attempt == attempts - 1:
                raise
            sleep(2.0 * 2**attempt)
    raise AssertionError("unreachable")


def verify(manifest, opener=dr.open_url, sleep=time.sleep) -> list[dict[str, str]]:
    report = []
    for entry in manifest:
        try:
            data = _download(entry["url"], opener, sleep)
        except dr.RegistryError:
            status = "refused"
        except OSError:
            status = "unreachable"
        else:
            status = "ok" if hashlib.sha256(data).hexdigest() == entry["sha256"] else "changed"
        report.append({"id": entry["id"], "status": status})
        sleep(0.3)
    return report


def main(argv: list[str] | None = None, opener=dr.open_url, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", nargs=2, metavar=("INVENTORY", "UCI_POOL"))
    parser.add_argument("--verify", type=Path, metavar="MANIFEST")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    if args.build:
        inventory = json.loads(Path(args.build[0]).read_text())
        uci = json.loads(Path(args.build[1]).read_text())["rows"]
        result: Any = build_manifest(inventory, uci)
        code = 0
    else:
        result = verify(json.loads(args.verify.read_text()), opener, sleep)
        code = 0 if all(r["status"] == "ok" for r in result) else 1
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(f"{len(result)} entries")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
