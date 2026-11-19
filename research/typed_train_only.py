"""Train-only replay of the typed-injection study (T062/T063, protocol ``typed-train-only-v1``).

In the archived study the magnitudes of the injected faults use the mean, the standard deviation,
the most correlated pair and the quantiles of the whole carrier, so rows of the evaluation
partitions influence the faults the detectors are scored on. Here the injection is first laid out
(group identities, types, partitions), then the statistics are recomputed from the unmodified
rows of the training partition only and the faults are injected again with those statistics.
Group identities, types and partitions are independent of the statistics, so the partitions are
identical to the archived ones; this is asserted. The carrier definition (continuous columns,
complete rows, de-duplication, row cap) is the pre-registered population and is unchanged.
Exploratory; archived results are compared, never overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from functools import partial as bind
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import injection as inj  # noqa: E402
import pool_typed as pt  # noqa: E402
import typed_run as tr  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

PROTOCOL = "typed-train-only-v1"


def train_reference(carrier: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Unmodified carrier rows of the training partition of the injection of ``seed``."""
    import typed_benchmark as tb

    layout = inj.inject(carrier, seed=seed)
    train, _val, _test = tb.split(layout, seed)
    cols = list(carrier.columns)
    return train.loc[train["anomaly_type"] == "clean", cols].reset_index(drop=True)


def inject_train_only(carrier: pd.DataFrame, seed: int) -> pd.DataFrame:
    """The injection of ``seed`` with statistics read from training rows only."""
    import typed_benchmark as tb

    reference = train_reference(carrier, seed)
    frame = inj.inject(carrier, seed=seed, reference=reference)
    layout = inj.inject(carrier, seed=seed)
    keys = ["group_id", "anomaly_type"]
    if not frame[keys].equals(layout[keys]):
        raise AssertionError("the reference changed the group or type layout")
    before = [set(p["group_id"]) for p in tb.split(layout, seed)]
    after = [set(p["group_id"]) for p in tb.split(frame, seed)]
    if before != after:
        raise AssertionError("the reference changed the partitions")
    return frame


def run_one(job: tuple[dict[str, Any], str, str], names: list[str] | None = None) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    import typed_benchmark as tb

    meta, path, digest = job
    carrier, report = tr.load_carrier(meta, Path(path), seed=0)
    cols = list(carrier.columns)
    recalls, precisions, fprs = [], [], []
    for seed in tr.SEEDS:
        result = tb.evaluate(inject_train_only(carrier, seed), cols, seed, names)
        recalls.append(result["recall"])
        precisions.append(result["precision"])
        fprs.append(result["fpr"])
    mean = pd.concat(recalls, keys=range(len(recalls))).groupby(level=1, sort=False).mean()
    precision = pd.concat(precisions, keys=range(len(precisions))).groupby(level=1, sort=False).mean()
    return {
        "protocol": PROTOCOL,
        "uci_id": meta["uci_id"],
        "name": meta["name"],
        "sha256": digest,
        "carrier": report,
        "seeds": list(tr.SEEDS),
        "recall_mean": json.loads(mean.to_json(orient="split")),
        "precision_mean": json.loads(precision.to_json(orient="split")),
        "fpr_mean": json.loads(pd.concat(fprs, axis=1).mean(axis=1).to_json()),
    }


def run_adbench(job: dict[str, Any], names: list[str] | None = None) -> dict[str, Any]:
    """The replay of one ADBench carrier (the carrier of ``pool_typed``, same five seeds)."""
    warnings.filterwarnings("ignore")
    import typed_benchmark as tb

    carrier, report = pt.load_carrier(job)
    cols = list(carrier.columns)
    results = [tb.evaluate(inject_train_only(carrier, seed), cols, seed, names) for seed in tr.SEEDS]

    def mean(key: str) -> dict:
        stack = pd.concat([r[key] for r in results], keys=range(len(results)))
        return json.loads(stack.groupby(level=1, sort=False).mean().to_json(orient="split"))

    return {
        "protocol": PROTOCOL,
        "id": job["id"],
        "name": job["name"],
        "carrier": report,
        "seeds": list(tr.SEEDS),
        "recall_mean": mean("recall"),
        "precision_mean": mean("precision"),
        "fpr_mean": json.loads(pd.concat([r["fpr"] for r in results], axis=1).mean(axis=1).to_json()),
    }


def _matrix(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(**result["recall_mean"])


def compare(archive: dict[Any, dict[str, Any]], replay: dict[Any, dict[str, Any]]) -> dict[str, Any]:
    """Paired difference replay minus archive of the mean recall, per method and anomaly type.

    The unit is the carrier; only carriers present in both are used. The interval is a percentile
    bootstrap over carriers (2,000 draws, seed 0).
    """
    ids = sorted(set(archive) & set(replay))
    if not ids:
        raise ValueError("no carrier in common")
    diffs = np.stack(
        [_matrix(replay[i]).sort_index().to_numpy() - _matrix(archive[i]).sort_index().to_numpy()
         for i in ids]
    )
    ref = _matrix(archive[ids[0]]).sort_index()
    rng = np.random.default_rng(0)
    draws = rng.integers(0, len(ids), size=(2000, len(ids)))
    boot = np.nanmedian(diffs[draws], axis=1)
    low, high = np.nanpercentile(boot, [2.5, 97.5], axis=0)
    cells = []
    for r, method in enumerate(ref.index):
        for c, kind in enumerate(ref.columns):
            column = diffs[:, r, c]
            cells.append(
                {
                    "method": method,
                    "type": kind,
                    "median_difference": float(np.nanmedian(column)),
                    "mean_difference": float(np.nanmean(column)),
                    "ci_low": float(low[r, c]),
                    "ci_high": float(high[r, c]),
                    "share_over_0.1": float(np.mean(np.abs(column[~np.isnan(column)]) > 0.1)),
                }
            )
    return {"carriers": len(ids), "bootstrap": {"draws": 2000, "seed": 0}, "cells": cells}


def load_runs(directory: Path) -> dict[Any, dict[str, Any]]:
    """Runs keyed by UCI id, or by the identifier of an ADBench carrier."""
    out = {}
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text())
        out[int(data["uci_id"]) if data.get("uci_id") is not None else data["id"]] = data
    return out


def write_json(path: Path, payload: Any) -> None:
    """Write ``payload`` atomically as sorted, one-space-indented JSON with a final newline."""
    from etl_benchmark.atomic import atomic_path

    with atomic_path(path) as partial:
        partial.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")


def _stem(identifier: str) -> str:
    return identifier.replace(":", "_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent
    registry = root / "verification" / "evidence" / "dataset_registry"
    parser.add_argument("--curated", type=Path, default=registry / "uci_curated.json")
    parser.add_argument("--pool", type=Path, default=registry / "uci_pool.json")
    parser.add_argument("--data", type=Path, default=root / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only-ids", nargs="*", help="ADBench identifiers, for a quick check")
    parser.add_argument("--only", type=int, nargs="*", help="UCI ids, for a quick check")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--methods", choices=("classical", "deep"), default="classical")
    parser.add_argument("--compare", type=Path, help="archived runs directory to pair with")
    parser.add_argument("--adbench", action="store_true", help="replay the ADBench carriers")
    parser.add_argument("--adbench-dir", type=Path, default=root / "data" / "adbench")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.compare:
        report = compare(load_runs(args.compare), load_runs(args.output))
        report["protocol"] = PROTOCOL
        write_json(args.output.parent / f"comparison_{args.methods}.json", report)
        print(f"{report['carriers']} carriers compared")
        return 0
    if args.adbench:
        names = list(DEEP_NAMES) if args.methods == "deep" else None
        todo = [
            j
            for j in pt.jobs(args.curated.parent, args.data, args.adbench_dir)
            if j["source"] == "adbench" and (not args.only_ids or j["id"] in args.only_ids)
        ]
        todo = [j for j in todo if pt.eligibility(j)["eligible"]]
        if args.resume:
            todo = [j for j in todo if not (args.output / f"{_stem(j['id'])}.json").exists()]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for result in pool.map(bind(run_adbench, names=names), todo):
                write_json(args.output / f"{_stem(result['id'])}.json", result)
                print(result["name"])
        print(f"{len(todo)} datasets")
        return 0
    todo = [
        j
        for j in tr.jobs(args.curated, args.pool, args.data)
        if not args.only or j[0]["uci_id"] in args.only
    ]
    if args.resume:
        todo = [j for j in todo if not (args.output / f"{j[0]['uci_id']}.json").exists()]
    names = list(DEEP_NAMES) if args.methods == "deep" else None
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(bind(run_one, names=names), todo):
            write_json(args.output / f"{result['uci_id']}.json", result)
            print(result["name"])
    print(f"{len(todo)} datasets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
