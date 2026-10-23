"""The ETL pipeline end to end on every dataset of the pool (pool_extension.md, study 4).

Each dataset is a CSV (the file of the pool, or the ADBench array written as a CSV with its label).
A fresh process reads it, removes duplicate rows, runs the quality stage with a detector, writes the
clean and the flagged rows, and records the time of each stage, the rows and the peak memory.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import tempfile
import time
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

import pool_typed as pt  # noqa: E402
import uci_loader as ul  # noqa: E402

METHODS = ("zscore", "isolation_forest")
LABEL = "label"


def peak_rss_bytes() -> int:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(raw if sys.platform == "darwin" else raw * 1024)


def prepare_csv(job: dict[str, Any], workdir: Path) -> tuple[Path, str | None, list[str]]:
    """The CSV the pipeline reads, the label column to keep out of the features, ID-like columns."""
    if job["source"] == "adbench":
        data = np.load(job["path"])
        frame = pd.DataFrame(data["X"]).add_prefix("f")
        frame[LABEL] = np.asarray(data["y"]).astype(int)
        path = workdir / f"{job['id'].replace(':', '_')}.csv"
        frame.to_csv(path, index=False)
        return path, LABEL, []
    meta = job["meta"]
    frame = ul.read_table(Path(job["path"]))
    features, _target = ul.split_columns(frame, meta)
    skip = [c for c in frame.columns if c not in features.columns]
    target = (meta.get("target_col") or [None])[0]
    return Path(job["path"]), target if target in frame.columns else None, skip


def run_etl(job: dict[str, Any], method: str) -> dict[str, Any]:
    """One dataset, one detector, in this process: the four stages timed separately."""
    warnings.filterwarnings("ignore")
    from etl_benchmark.load import write_csv
    from etl_benchmark.pipeline import detect, extract, transform
    from etl_benchmark.registry import get_detector

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        stages: dict[str, float] = {}
        try:
            csv, label, skip = prepare_csv(job, work)
            before = peak_rss_bytes()
            t = time.perf_counter()
            df = extract(csv)
            stages["extract"] = time.perf_counter() - t
            rows_in = len(df)
            t = time.perf_counter()
            df = transform(df)
            stages["transform"] = time.perf_counter() - t
            drop = [c for c in skip if c in df.columns]
            features = df.drop(columns=drop) if drop else df
            t = time.perf_counter()
            result = detect(features, get_detector(method, 0.05), label_column=label)
            stages["detect"] = time.perf_counter() - t
            t = time.perf_counter()
            write_csv(df[~result.flags], work / "pipeline_clean.csv")
            write_csv(df[result.flags], work / "pipeline_anomalies.csv")
            stages["load"] = time.perf_counter() - t
        except Exception as error:  # recorded, not hidden
            return {"id": job["id"], "method": method, "status": "FAIL", "reason": repr(error)}
    return {
        "id": job["id"],
        "name": job["name"],
        "method": method,
        "status": "OK",
        "rows_in": int(rows_in),
        "rows_after_transform": int(len(df)),
        "columns": int(df.shape[1]),
        "stages_s": stages,
        "detect_stage_share": stages["detect"] / sum(stages.values()),
        "rss_peak_bytes": peak_rss_bytes(),
        "rss_delta_bytes": peak_rss_bytes() - before,
        "flagged_share": float(result.flags.mean()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--only", nargs="*", help="dataset ids, for a quick check")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    registry = ROOT / "verification" / "evidence" / "dataset_registry"
    todo = [
        (j, m)
        for j in pt.jobs(registry, ROOT / "data" / "pool", ROOT / "data" / "adbench")
        if not args.only or j["id"] in args.only
        for m in METHODS
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    # a fresh process per measurement, so that the peak memory belongs to that run alone
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for record in pool.map(bind(_one), todo):
            records.append(record)
            print(record["id"], record["method"], record["status"], flush=True)
    with atomic_path(args.output / "pool_etl.json") as partial:
        partial.write_text(json.dumps(records, indent=1, sort_keys=True) + "\n")
    return 0


def _one(item: tuple[dict[str, Any], str]) -> dict[str, Any]:
    job, method = item
    return run_etl(job, method)


if __name__ == "__main__":
    raise SystemExit(main())
