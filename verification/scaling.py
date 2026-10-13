"""Bounded detector cost study; never used as a FAST timing threshold."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tracemalloc
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from etl_benchmark.pipeline import detect
from etl_benchmark.quality.ml import (
    IsolationForestDetector,
    LOFDetector,
    OneClassSVMDetector,
)

METHODS = {
    "isolation_forest": IsolationForestDetector,
    "lof": LOFDetector,
    "ocsvm": OneClassSVMDetector,
}


def run_case(
    factory: Callable,
    *,
    n_rows: int,
    n_features: int,
    fit_cap: int | None,
    seed: int,
) -> dict:
    """Measure fit/predict/score on the same seeded numerical workload."""
    if n_rows < 20 or n_features < 1 or fit_cap is not None and fit_cap < 2:
        raise ValueError("n_rows, n_features and fit_cap must be positive and usable")
    fit_rows = min(n_rows, fit_cap) if fit_cap is not None else n_rows
    frame = pd.DataFrame(
        np.random.default_rng(seed).normal(size=(n_rows, n_features)),
        columns=[f"feature_{i}" for i in range(n_features)],
    )
    row = {
        "status": "FAIL",
        "reason": "",
        "eval_rows": n_rows,
        "fit_rows": fit_rows,
        "n_features": n_features,
        "seed": seed,
        "fit_s": None,
        "predict_s": None,
        "score_s": None,
        "detect_s": None,
        "peak_python_bytes": None,
    }
    tracemalloc.start()
    try:
        result = detect(frame, factory(), fit_df=frame.iloc[:fit_rows])
        row.update(
            {
                "status": "PASS",
                "fit_s": result.fit_s,
                "predict_s": result.predict_s,
                "score_s": result.score_s,
                "detect_s": result.detect_s,
            }
        )
    except Exception as exc:
        row["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        row["peak_python_bytes"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 300, 900])
    parser.add_argument("--features", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--fit-cap", type=int)
    parser.add_argument("--methods", choices=sorted(METHODS), nargs="+", default=list(METHODS))
    parser.add_argument("--results-dir", type=Path, default=Path("verification/evidence"))
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 10 or any(n < 20 or n > 5000 for n in args.sizes):
        parser.error("use 1–10 repeats and dataset sizes between 20 and 5000")

    rows = []
    for method in args.methods:
        for n_rows in args.sizes:
            for repeat in range(args.repeats):
                row = run_case(
                    METHODS[method],
                    n_rows=n_rows,
                    n_features=args.features,
                    fit_cap=args.fit_cap,
                    seed=42 + repeat,
                )
                rows.append({"method": method, "repeat": repeat, **row})
                print(f"{method} rows={n_rows} repeat={repeat}: {row['status']}")

    args.results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.results_dir / "scaling.csv"
    json_path = args.results_dir / "scaling.json"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    record = {
        "captured_at": datetime.now(UTC).isoformat(),
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "worktree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        ),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "python": sys.version.split()[0],
        "packages": {name: version(name) for name in ("numpy", "pandas", "scikit-learn", "pyod")},
        "sizes": args.sizes,
        "n_features": args.features,
        "repeats": args.repeats,
        "fit_cap": args.fit_cap,
        "methods": args.methods,
        "data_loading": "generated in memory; CSV reading and deduplication excluded",
        "memory_measure": "tracemalloc peak Python allocations; native allocations excluded",
        "timing_measure": (
            "fit_s + predict_s + score_s inside pipeline.detect; data generation excluded"
        ),
        "results": rows,
    }
    json_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if any(row["status"] != "PASS" for row in rows):
        raise SystemExit("one or more scaling cases failed; inspect scaling.json")


if __name__ == "__main__":
    main()
