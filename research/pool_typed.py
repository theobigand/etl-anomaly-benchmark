"""Typed injection and severity sweep on every eligible table of the pool (pool_extension.md).

The carriers are the 116 UCI tables and the 36 ADBench datasets (the normal class only for a
labelled set). The eligibility rule of ``injection.py`` is unchanged; each table that fails it is
recorded with the reason. The reference run repeats ``typed_run.py`` on the ADBench carriers
(the UCI ones are already archived); the severity sweep covers every eligible table.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from functools import partial as bind
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import dataset_registry as dr  # noqa: E402
import injection as inj  # noqa: E402
import typed_run as tr  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

SEEDS = tr.SEEDS
SWEEP_SEEDS = (42, 1, 2)
SEVERITIES = (0.5, 1.0, 2.0, 4.0)
MAGNITUDE_TYPES = ("univariate_outlier", "multivariate_outlier", "temporal_drift")


def jobs(registry: Path, data: Path, adbench: Path) -> list[dict[str, Any]]:
    """Every dataset of the pool as a carrier job."""
    meta = {m["uci_id"]: m for m in json.loads((registry / "uci_curated.json").read_text())["kept"]}
    out = []
    for row in json.loads((registry / "uci_pool.json").read_text())["rows"]:
        out.append(
            {
                "id": f"uci:{row['uci_id']}",
                "source": "uci",
                "name": meta[row["uci_id"]]["name"],
                "meta": meta[row["uci_id"]],
                "path": str(data / f"{row['uci_id']}.csv"),
            }
        )
    files = {t["name"]: t["file"] for t in dr.ADBENCH_TABULAR}
    report = json.loads((registry / "adbench_normalisation_report.json").read_text())
    for name in sorted(report):
        out.append(
            {
                "id": f"adbench:{name}",
                "source": "adbench",
                "name": name,
                "path": str(adbench / files[name]),
            }
        )
    return out


def load_carrier(job: dict[str, Any], seed: int = 0) -> tuple[pd.DataFrame, dict[str, Any]]:
    if job["source"] == "uci":
        return tr.load_carrier(job["meta"], Path(job["path"]), seed)
    data = np.load(job["path"])
    features = pd.DataFrame(data["X"]).add_prefix("f")[np.asarray(data["y"]).astype(int) == 0]
    carrier, report = inj.prepare(features.reset_index(drop=True), seed=seed)
    report.update(source_rows=int(len(features)), normal_class_only=True)
    return carrier, report


def eligibility(job: dict[str, Any]) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    row = {"id": job["id"], "name": job["name"], "source": job["source"]}
    try:
        carrier, report = load_carrier(job)
    except inj.NotEligible as reason:
        return {**row, "eligible": False, "reason": str(reason)}
    except Exception as error:  # recorded, not hidden
        return {**row, "eligible": False, "reason": f"load failed: {error!r}"}
    return {**row, "eligible": True, "rows": int(len(carrier)), "report": report}


def run_reference(job: dict[str, Any], names: list[str] | None = None) -> dict[str, Any]:
    """The five-seed typed run of ``typed_run.run_one`` on one carrier."""
    warnings.filterwarnings("ignore")
    import typed_benchmark as tb

    carrier, report = load_carrier(job)
    cols = list(carrier.columns)
    recalls, precisions, fprs = [], [], []
    for seed in SEEDS:
        result = tb.evaluate(inj.inject(carrier, seed=seed), cols, seed, names)
        recalls.append(result["recall"])
        precisions.append(result["precision"])
        fprs.append(result["fpr"])
    mean = pd.concat(recalls, keys=range(len(recalls))).groupby(level=1, sort=False).mean()
    precision = (
        pd.concat(precisions, keys=range(len(precisions))).groupby(level=1, sort=False).mean()
    )
    return {
        "id": job["id"],
        "name": job["name"],
        "carrier": report,
        "seeds": list(SEEDS),
        "recall_mean": json.loads(mean.to_json(orient="split")),
        "precision_mean": json.loads(precision.to_json(orient="split")),
        "fpr_mean": json.loads(pd.concat(fprs, axis=1).mean(axis=1).to_json()),
    }


def run_severity(
    job: dict[str, Any],
    names: list[str] | None = None,
    severities: tuple[float, ...] = SEVERITIES,
    seeds: tuple[int, ...] = SWEEP_SEEDS,
) -> dict[str, Any]:
    """Mean recall by method and type at each severity multiplier."""
    warnings.filterwarnings("ignore")
    import typed_benchmark as tb

    carrier, report = load_carrier(job)
    cols = list(carrier.columns)
    by_severity: dict[str, Any] = {}
    for severity in severities:
        frames = [
            tb.evaluate(inj.inject(carrier, seed=seed, severity=severity), cols, seed, names)[
                "recall"
            ]
            for seed in seeds
        ]
        mean = pd.concat(frames, keys=range(len(frames))).groupby(level=1, sort=False).mean()
        by_severity[str(severity)] = json.loads(mean[list(MAGNITUDE_TYPES)].to_json(orient="split"))
    return {
        "id": job["id"],
        "name": job["name"],
        "carrier": report,
        "seeds": list(seeds),
        "severities": list(severities),
        "recall_by_severity": by_severity,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("eligibility", "reference", "severity"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--methods", choices=("classical", "deep"), default="classical")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--only", nargs="*", help="dataset ids, for a quick check")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    registry = ROOT / "verification" / "evidence" / "dataset_registry"
    todo = [
        j
        for j in jobs(registry, ROOT / "data" / "pool", ROOT / "data" / "adbench")
        if not args.only or j["id"] in args.only
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "eligibility":
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            rows = list(pool.map(eligibility, todo))
        with atomic_path(args.output / "eligibility.json") as partial:
            partial.write_text(json.dumps(rows, indent=1) + "\n")
        print(sum(r["eligible"] for r in rows), "eligible of", len(rows))
        return 0
    eligible = {
        r["id"]
        for r in json.loads((args.output.parent / "eligibility.json").read_text())
        if r["eligible"]
    }
    todo = [j for j in todo if j["id"] in eligible]
    if args.command == "reference":
        todo = [j for j in todo if j["source"] == "adbench"]  # the UCI ones are archived already
    names = list(DEEP_NAMES) if args.methods == "deep" else None
    stem = lambda job: job["id"].replace(":", "_")  # noqa: E731
    if args.resume:
        todo = [j for j in todo if not (args.output / f"{stem(j)}.json").exists()]
    work = run_reference if args.command == "reference" else run_severity
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for job, result in zip(todo, pool.map(bind(work, names=names), todo), strict=True):
            with atomic_path(args.output / f"{stem(job)}.json") as partial:
                partial.write_text(json.dumps(result, sort_keys=True) + "\n")
            print(job["id"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
