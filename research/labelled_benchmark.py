"""Core detectors on the labelled problems of the pool (protocol labelled_pool.md)."""

from __future__ import annotations

import os

os.environ.setdefault("TQDM_DISABLE", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import warnings  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dataset_registry as dr  # noqa: E402
import normalise as nm  # noqa: E402
import uci_loader as ul  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.metrics import compute_metrics  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import DETECTOR_NAMES, clip_contamination, get_detector  # noqa: E402

METHODS = list(DETECTOR_NAMES)


def load_adbench(name: str, path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    data = np.load(path)
    x, y, report = nm.clean(pd.DataFrame(data["X"]), data["y"])
    report.update(source="adbench", name=name)
    return x, y, report


def load_uci(meta: dict[str, Any], path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    features, labels, info = ul.derive_labels(ul.read_table(path), meta)
    x, y, report = nm.clean(features, labels)
    report.update(info, source="uci", name=meta["name"], uci_id=meta["uci_id"])
    return x, y, report


def run_problem(
    x: np.ndarray,
    y: np.ndarray,
    seeds: tuple[int, ...] = config.BENCHMARK_SEEDS,
    methods: list[str] | None = None,
) -> dict[str, Any]:
    methods = methods or METHODS
    unknown = [m for m in methods if m not in METHODS]
    if unknown:
        raise ValueError(f"unknown detector names: {unknown}")
    metrics: dict[str, list[dict[str, float]]] = {}
    skipped: list[str] = []
    for seed in seeds:
        part = nm.split(x, y, seed)
        names = [f"f{i}" for i in range(x.shape[1])]
        train = pd.DataFrame(part["x_train"], columns=names)
        test = pd.DataFrame(part["x_test"], columns=names)
        contamination = clip_contamination(float(part["y_train"].mean()))
        skip = nm.skipped_detectors(len(train))
        skipped = [m for m in methods if m in skip]
        for method in methods:
            if method in skip:
                continue
            result = detect(test, get_detector(method, contamination), fit_df=train)
            row = compute_metrics(part["y_test"], result.flags.to_numpy(), result.scores.to_numpy())
            metrics.setdefault(method, []).append(row)
    return {"seeds": list(seeds), "metrics": metrics, "skipped": skipped}


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    try:
        if job["source"] == "adbench":
            x, y, report = load_adbench(job["name"], Path(job["path"]))
        else:
            x, y, report = load_uci(job["meta"], Path(job["path"]))
        result = run_problem(x, y)
    except Exception as error:  # recorded, never dropped silently
        return {"problem": job["problem"], "source": job["source"], "failed": repr(error)}
    return {
        "problem": job["problem"],
        "source": job["source"],
        "name": report["name"],
        "prevalence": float(y.mean()),
        "rows": int(len(y)),
        "features": int(x.shape[1]),
        "report": report,
        **result,
    }


def jobs(registry: Path, adbench: Path, pool: Path) -> list[dict[str, Any]]:
    files = {t["name"]: t["file"] for t in dr.ADBENCH_TABULAR}
    out = [
        {
            "problem": f"adbench:{name}",
            "source": "adbench",
            "name": name,
            "path": str(adbench / files[name]),
        }
        for name in sorted(json.loads((registry / "adbench_normalisation_report.json").read_text()))
    ]
    curated = {
        m["uci_id"]: m for m in json.loads((registry / "uci_curated.json").read_text())["kept"]
    }
    for row in json.loads((registry / "uci_pool.json").read_text())["rows"]:
        if "labelled" in row["roles"]:
            out.append(
                {
                    "problem": f"uci:{row['uci_id']}",
                    "source": "uci",
                    "meta": curated[row["uci_id"]],
                    "path": str(pool / f"{row['uci_id']}.csv"),
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent
    registry = root / "verification" / "evidence" / "dataset_registry"
    parser.add_argument("--registry", type=Path, default=registry)
    parser.add_argument("--adbench", type=Path, default=root / "data" / "adbench")
    parser.add_argument("--pool", type=Path, default=root / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", nargs="*", help="problem ids, for a quick check")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    todo = [
        j
        for j in jobs(args.registry, args.adbench, args.pool)
        if not args.only or j["problem"] in args.only
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    failed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(run_job, todo):
            failed += "failed" in result
            stem = result["problem"].replace(":", "_")
            with atomic_path(args.output / f"{stem}.json") as partial:
                partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
            print(result["problem"], result.get("failed", "ok"), flush=True)
    print(f"{len(todo)} problems, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
