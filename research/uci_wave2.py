"""Second acquisition wave of UCI tables for the strata the first pool does not cover.

Protocol: verification/dataset_wave2.md. The first pool excluded time series, sequential and
transactional tables because its labelled and typed protocols could not use them; the batch-level
pipeline study can. Selection keeps the licence rule of the first pool (an open licence stated on
the UCI page itself) and skips every table already in the first pool. Files are fetched into
``data/uci_wave2`` (not redistributed) and pinned by checksum in a manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import dataset_registry as dr  # noqa: E402
import time_scan as ts  # noqa: E402
import uci_loader as ul  # noqa: E402
import uci_pool as up  # noqa: E402

ACCEPTED = up.ACCEPTED
MIN_ROWS, MAX_ROWS, MIN_FEATURES, MAX_FEATURES = 300, 3_000_000, 3, 300
EXCLUDED_MODALITIES = {"Image", "Text"}
WAVE_DIR = ROOT / "data" / "uci_wave2"
FIRST_POOL = ROOT / "verification/evidence/dataset_registry/uci_pool.json"
SELECTION = ROOT / "verification/evidence/dataset_registry_v2/uci_wave2_selection.json"
MANIFEST = ROOT / "verification/evidence/dataset_registry_v2/uci_wave2_manifest.json"


def tags(meta: dict[str, Any]) -> list[str]:
    """Which uncovered stratum a table can serve (it may serve several)."""
    found = []
    chars = set(meta.get("characteristics") or [])
    if "Time-Series" in chars:
        found.append("time_series")
    if "Sequential" in chars:
        found.append("sequential")
    if meta.get("area") == "Business" and (meta.get("num_instances") or 0) >= 500:
        found.append("transactional")
    types = set(meta.get("feature_types") or [])
    if "Categorical" in types and "Real" not in types and "Integer" not in types:
        found.append("categorical_only")
    return found


def rejection(meta: dict[str, Any], taken: set[int]) -> str | None:
    reasons = []
    rows, features = meta.get("num_instances"), meta.get("num_features")
    if meta["uci_id"] in taken:
        reasons.append("already in the first pool")
    if rows is None or not MIN_ROWS <= rows <= MAX_ROWS:
        reasons.append(f"rows ({rows})")
    if features is None or not MIN_FEATURES <= features <= MAX_FEATURES:
        reasons.append(f"features ({features})")
    if EXCLUDED_MODALITIES & set(meta.get("characteristics") or []):
        reasons.append("modality")
    if not meta.get("data_url"):
        reasons.append("download")
    if not tags(meta):
        reasons.append("serves no uncovered stratum")
    return "; ".join(reasons) or None


def first_pool_ids(path: Path = FIRST_POOL) -> set[int]:
    return {r["uci_id"] for r in json.loads(path.read_text())["rows"]}


def select(survey: list[dict[str, Any]], licences: dict[int, str], taken: set[int]):
    chosen, rejected = [], []
    for meta in survey:
        reason = rejection(meta, taken)
        if reason is None and licences.get(meta["uci_id"]) not in ACCEPTED:
            reason = "licence not open or not stated on the page"
        (rejected.append((meta, reason)) if reason else chosen.append(meta))
    return chosen, rejected


def pin(meta: dict[str, Any], destination: Path, fetcher=dr.fetch_unpinned) -> dict[str, Any]:
    """Download one table, hash it and record what the study needs to decide its use."""
    path = destination / f"{meta['uci_id']}.csv"
    path, digest = fetcher(meta["data_url"], path)
    frame = ul.read_table(path)
    candidates = [c["column"] for c in ts.candidate_columns(frame)]
    return {
        "uci_id": meta["uci_id"],
        "name": meta["name"],
        "licence": meta["licence"],
        "url": meta["data_url"],
        "page": meta["repository_url"],
        "sha256": digest,
        "rows": int(len(frame)),
        "columns": int(frame.shape[1]),
        "tags": tags(meta),
        "area": meta.get("area"),
        "time_candidates": candidates,
    }


def main(argv: list[str] | None = None) -> int:
    from etl_benchmark.atomic import atomic_path

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pick = commands.add_parser("select")
    pick.add_argument("--survey", type=Path, required=True)
    get = commands.add_parser("fetch")
    get.add_argument("--destination", type=Path, default=WAVE_DIR)
    args = parser.parse_args(argv)
    if args.command == "select":
        survey = json.loads(args.survey.read_text())["datasets"]
        taken = first_pool_ids()
        candidates = [m for m in survey if rejection(m, taken) is None]
        licences = {}
        for meta in candidates:
            page = dr._text(meta["repository_url"])
            licences[meta["uci_id"]] = dr.uci_licence(page)["licence"]
            time.sleep(0.3)
        chosen, rejected = select(survey, licences, taken)
        out = {
            "checked": time.strftime("%Y-%m-%d"),
            "chosen": [{**m, "licence": licences[m["uci_id"]], "tags": tags(m)} for m in chosen],
            "rejected_after_metadata": len(survey) - len(candidates),
            "rejected_by_licence": [
                {"uci_id": m["uci_id"], "name": m["name"], "reason": r}
                for m, r in rejected
                if "licence" in r
            ],
        }
        SELECTION.parent.mkdir(parents=True, exist_ok=True)
        with atomic_path(SELECTION) as partial:
            partial.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(f"chosen {len(chosen)}, licence-rejected {len(out['rejected_by_licence'])}")
        return 0
    chosen = json.loads(SELECTION.read_text())["chosen"]
    args.destination.mkdir(parents=True, exist_ok=True)
    rows, failed = [], []
    for meta in chosen:
        try:
            rows.append(pin(meta, args.destination))
        except (OSError, ValueError, pd.errors.ParserError) as error:
            failed.append({"uci_id": meta["uci_id"], "name": meta["name"], "reason": repr(error)})
    with atomic_path(MANIFEST) as partial:
        partial.write_text(
            json.dumps({"tables": rows, "failed": failed}, indent=1, sort_keys=True) + "\n"
        )
    print(f"fetched {len(rows)}, failed {len(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
