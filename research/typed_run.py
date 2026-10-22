"""Run the typed-injection benchmark over the eligible carriers of the pool (issue #65)."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from functools import partial as bind
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import injection as inj  # noqa: E402
import uci_loader as ul  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

SEEDS = (42, 1, 2, 3, 4)


def load_carrier(meta: dict[str, Any], path: Path, seed: int):
    frame = ul.read_table(path)
    try:
        features, labels, _ = ul.derive_labels(frame, meta)
        features = features[labels == 0]
        normal_only = True
    except ul.NoLabels:
        features, _ = ul.split_columns(frame, meta)
        normal_only = False
    carrier, report = inj.prepare(features, seed=0)
    report.update(source_rows=len(features), normal_class_only=normal_only)
    return carrier, report


def run_one(job: tuple[dict[str, Any], str, str], names: list[str] | None = None) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    import typed_benchmark as tb

    meta, path, digest = job
    carrier, report = load_carrier(meta, Path(path), seed=0)
    cols = list(carrier.columns)
    recalls, precisions, fprs = [], [], []
    for seed in SEEDS:
        df = inj.inject(carrier, seed=seed)
        result = tb.evaluate(df, cols, seed, names)
        recalls.append(result["recall"])
        precisions.append(result["precision"])
        fprs.append(result["fpr"])
    import pandas as pd

    stack = pd.concat(recalls, keys=range(len(recalls)))
    mean = stack.groupby(level=1, sort=False).mean()
    precision = (
        pd.concat(precisions, keys=range(len(precisions))).groupby(level=1, sort=False).mean()
    )
    fpr = pd.concat(fprs, axis=1).mean(axis=1)
    return {
        "uci_id": meta["uci_id"],
        "name": meta["name"],
        "sha256": digest,
        "carrier": report,
        "seeds": list(SEEDS),
        "recall_mean": json.loads(mean.to_json(orient="split")),
        "precision_mean": json.loads(precision.to_json(orient="split")),
        "fpr_mean": json.loads(fpr.to_json()),
        "recall_seeds": [json.loads(r.to_json(orient="split")) for r in recalls],
    }


def jobs(curated: Path, pool: Path, data: Path) -> list[tuple]:
    meta = {m["uci_id"]: m for m in json.loads(curated.read_text())["kept"]}
    out = []
    for row in json.loads(pool.read_text())["rows"]:
        if "carrier" not in row["roles"]:
            continue
        path = data / f"{row['uci_id']}.csv"
        try:
            load_carrier(meta[row["uci_id"]], path, seed=0)
        except inj.NotEligible:
            continue
        out.append((meta[row["uci_id"]], str(path), row["sha256"]))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent
    registry = root / "verification" / "evidence" / "dataset_registry"
    parser.add_argument("--curated", type=Path, default=registry / "uci_curated.json")
    parser.add_argument("--pool", type=Path, default=registry / "uci_pool.json")
    parser.add_argument("--data", type=Path, default=root / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", type=int, nargs="*", help="UCI ids, for a quick check")
    parser.add_argument(
        "--resume", action="store_true", help="skip the datasets whose result is already written"
    )
    parser.add_argument(
        "--methods",
        choices=("classical", "deep"),
        default="classical",
        help="the registry sweep with drift, or the neural detectors",
    )
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    todo = [
        j
        for j in jobs(args.curated, args.pool, args.data)
        if not args.only or j[0]["uci_id"] in args.only
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    if args.resume:
        todo = [j for j in todo if not (args.output / f"{j[0]['uci_id']}.json").exists()]
    names = list(DEEP_NAMES) if args.methods == "deep" else None
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(bind(run_one, names=names), todo):
            with atomic_path(args.output / f"{result['uci_id']}.json") as partial:
                partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
            print(result["name"], flush=True)
    print(f"{len(todo)} datasets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
