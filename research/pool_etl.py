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
ONE_HOT_MAX = 20
_SPARSE = r"^\s*\d+:\s*[-+]?[\d.]+(?:[eE][-+]?\d+)?\s*$"


def _numeric_share(column: pd.Series) -> float:
    return float(
        pd.to_numeric(column, errors="coerce").notna().sum() / max(column.notna().sum(), 1)
    )


def strip_header_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove rows that repeat the header line (concatenated files); numeric tables stay.

    A row matches only when every cell equals its column name: a row of missing values is data.
    """
    if all(pd.api.types.is_numeric_dtype(t) for t in df.dtypes):
        return df, 0
    names = pd.Series(df.columns.astype(str), index=df.columns)
    repeated = df.astype("string").eq(names).fillna(False).all(axis=1)
    if not repeated.any():
        return df, 0
    return df[~repeated].reset_index(drop=True), int(repeated.sum())


def repair_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Make a raw table usable by the numeric detectors, recording every change (issue 79).

    Repeated header lines (concatenated train and test files) are removed, ``index:value`` sparse
    cells are parsed, all-missing columns are dropped, date-times become epoch seconds, and the
    remaining text columns are one-hot encoded (at most ``ONE_HOT_MAX`` values) or replaced by
    their value frequency. Nothing uses a label, and numeric tables pass through unchanged.
    """
    report: dict[str, Any] = {
        "header_rows_removed": 0,
        "sparse_columns": [],
        "all_missing_dropped": [],
        "datetime_columns": [],
        "encoded": [],
    }
    df, report["header_rows_removed"] = strip_header_rows(df)
    out: dict[str, pd.Series] = {}
    for name in df.columns:
        col = df[name]
        if not pd.api.types.is_numeric_dtype(col):
            text = col.astype("string")
            if text.str.match(_SPARSE).fillna(False).mean() > 0.9:
                col = pd.to_numeric(text.str.split(":", n=1).str[1], errors="coerce")
                report["sparse_columns"].append(name)
            elif _numeric_share(col) > 0.95:
                col = pd.to_numeric(col, errors="coerce")
        out[name] = col
    frame = pd.DataFrame(out)
    empty = [c for c in frame.columns if frame[c].isna().all()]
    report["all_missing_dropped"] = empty
    frame = frame.drop(columns=empty)
    parts: list[pd.DataFrame | pd.Series] = []
    for name in frame.columns:
        col = frame[name]
        if pd.api.types.is_numeric_dtype(col):
            parts.append(col)
            continue
        stamps = pd.to_datetime(col, errors="coerce", format="mixed")
        if (
            stamps.notna().mean() > 0.95
            and col.astype("string").str.contains(r"\d[-/:]\d").mean() > 0.9
        ):
            parts.append((stamps - pd.Timestamp("1970-01-01")).dt.total_seconds().rename(name))
            report["datetime_columns"].append(name)
            continue
        report["encoded"].append(name)
        if col.nunique() <= ONE_HOT_MAX:
            parts.append(pd.get_dummies(col, prefix=name, dtype=float))
        else:
            parts.append(col.map(col.value_counts(normalize=True)).astype(float).rename(name))
    report["encoded"].sort()
    return (pd.concat(parts, axis=1) if parts else frame), report


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
            df, header_rows = strip_header_rows(transform(df))
            drop = [c for c in skip if c in df.columns]
            features, repairs = repair_frame(df.drop(columns=drop) if drop else df)
            repairs["header_rows_removed"] += header_rows
            repairs["sparse_columns"] = len(repairs["sparse_columns"])
            stages["transform"] = time.perf_counter() - t
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
        "repairs": repairs,
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
