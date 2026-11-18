"""Train-only replay of the 100 labelled pool problems (T062/T063, pool-train-only-replay-v1).

Raw, uncleaned tables are split by identical-feature-row groups (stratified on a group label),
then prepared with ``pool_preprocessing.prepare_frozen`` so that no schema, vocabulary, row or
statistic decision reads evaluation rows. Exploratory: archived results are only compared, never
overwritten. See docs/thesis-remediation/POOL_TRAIN_ONLY_REPLAY_2026-11-18.md.
"""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import warnings  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from functools import partial as bind  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labelled_benchmark as lb  # noqa: E402
import uci_loader as ul  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES  # noqa: E402
from research.pool_train_only import evaluate_frozen  # noqa: E402

PROTOCOL = "pool-train-only-replay-v1"


def load_raw(job: dict[str, Any]) -> tuple[pd.DataFrame, np.ndarray]:
    """Raw features as strings and the binary label; no cleaning, no row removal."""
    if job["source"] == "adbench":
        data = np.load(job["path"])
        frame = pd.DataFrame(data["X"], columns=[f"c{i}" for i in range(data["X"].shape[1])])
        labels = np.asarray(data["y"]).astype(int)
    else:
        frame, labels, _ = ul.derive_labels(ul.read_table(Path(job["path"])), job["meta"])
        frame = frame.copy()
        frame.columns = [str(c) for c in frame.columns]
        labels = np.asarray(labels).astype(int)
    return frame.astype("string"), labels


def grouped_split(frame: pd.DataFrame, labels: np.ndarray, seed: int) -> dict[str, list[int]]:
    """70/15/15 split of groups of identical feature rows, stratified on 'any anomaly in group'."""
    keys = pd.util.hash_pandas_object(frame, index=False).to_numpy()
    codes, uniques = pd.factorize(keys)
    group_label = np.zeros(len(uniques), dtype=int)
    np.maximum.at(group_label, codes, labels)
    groups = np.arange(len(uniques))
    train, rest = train_test_split(groups, train_size=0.70, stratify=group_label, random_state=seed)
    val, test = train_test_split(
        rest, train_size=0.5, stratify=group_label[rest], random_state=seed
    )
    return {
        name: np.flatnonzero(np.isin(codes, ids)).tolist()
        for name, ids in (("train", train), ("validation", val), ("test", test))
    }


def run_job(job: dict[str, Any], methods: list[str]) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    try:
        frame, labels = load_raw(job)
        metrics: dict[str, list[dict[str, float]]] = {}
        errors: list[dict[str, Any]] = []
        skipped: list[str] = []
        fits: list[dict[str, Any]] = []
        for seed in config.BENCHMARK_SEEDS:
            parts = grouped_split(frame, labels, seed)
            result = evaluate_frozen(frame, labels, parts, seed=seed, methods=methods)
            for name, run in result["runs"].items():
                metrics.setdefault(name, []).append({"seed": seed, **run["metrics"]})
            errors += [{"seed": seed, **e} for e in result["errors"]]
            skipped = result["skipped"]
            fit = result["preprocessing"]
            fits.append(
                {
                    "seed": seed,
                    "rows": {k: len(v) for k, v in parts.items()},
                    "prevalence": result["prevalence"],
                    "numeric": len(fit["numeric_columns"]),
                    "categorical": len(fit["categorical_columns"]),
                    "dropped": {k: len(v) for k, v in fit["dropped"].items()},
                }
            )
    except Exception as error:  # recorded, never dropped silently
        return {"problem": job["problem"], "source": job["source"], "failed": repr(error)}
    return {
        "protocol": PROTOCOL,
        "problem": job["problem"],
        "source": job["source"],
        "rows": int(len(labels)),
        "prevalence": float(labels.mean()),
        "metrics": metrics,
        "errors": errors,
        "skipped": skipped,
        "preparation": fits,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent
    parser.add_argument(
        "--registry", type=Path, default=root / "verification/evidence/dataset_registry"
    )
    parser.add_argument("--adbench", type=Path, default=root / "data" / "adbench")
    parser.add_argument("--pool", type=Path, default=root / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--methods", choices=("classical", "deep"), default="classical")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    todo = [
        j
        for j in lb.jobs(args.registry, args.adbench, args.pool)
        if not args.only or j["problem"] in args.only
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    if args.resume:
        todo = [
            j for j in todo if not (args.output / f"{j['problem'].replace(':', '_')}.json").exists()
        ]
    failed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(
            bind(run_job, methods=list(DEEP_NAMES if args.methods == "deep" else lb.METHODS)), todo
        ):
            failed += "failed" in result
            stem = result["problem"].replace(":", "_")
            with atomic_path(args.output / f"{stem}.json") as partial:
                partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(f"{len(todo)} problems, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
