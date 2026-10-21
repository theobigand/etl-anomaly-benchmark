"""Download the curated UCI sets, record their digests and the roles each can serve."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dataset_registry as dr  # noqa: E402
import normalise as nm  # noqa: E402
import uci_loader as ul  # noqa: E402


def pool_row(meta: dict[str, Any], path: Path, digest: str) -> dict[str, Any]:
    frame = ul.read_table(path)
    row: dict[str, Any] = {
        "uci_id": meta["uci_id"],
        "name": meta.get("name"),
        "licence": meta.get("licence"),
        "url": meta.get("data_url"),
        "sha256": digest,
        "roles": [],
    }
    try:
        features, _ = ul.split_columns(frame, meta)
        _, _, report = nm.clean(features, [0] * len(features))
        row["carrier"] = report
        row["roles"].append("carrier")
    except nm.NormaliseError as error:
        row["carrier_refused"] = str(error)
    try:
        features, labels, info = ul.derive_labels(frame, meta)
        x, y, report = nm.clean(features, labels)
        nm.split(x, y, 0)
        row.update(label={**info, **report}, roles=[*row["roles"], "labelled"])
        row["skipped_detectors"] = nm.skipped_detectors(int(0.7 * len(y)))
    except (ul.NoLabels, nm.NormaliseError) as error:
        row["label_refused"] = str(error)
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curated", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=dr.ROOT / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    rows, failed = [], []
    for meta in json.loads(args.curated.read_text())["kept"]:
        try:
            path, digest = dr.fetch_unpinned(
                meta["data_url"], args.destination / f"{meta['uci_id']}.csv"
            )
            rows.append(pool_row(meta, path, digest))
        except (OSError, ValueError, dr.RegistryError) as error:
            failed.append({"uci_id": meta["uci_id"], "error": str(error)})
        time.sleep(0.3)
    out = {"rows": rows, "failed": failed}
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"{len(rows)} recorded, {len(failed)} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
