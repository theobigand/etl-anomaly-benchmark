"""Chronological study with controlled injection on unlabelled time series (issue 78).

Protocol: verification/chrono_injected.md. A real time variable orders the rows; faults are
injected into the evaluation rows only, with statistics read from the fitting rows, and every
detector is evaluated twice on the same rows: chronological 60/40 and random 60/40.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import injection as inj  # noqa: E402
import uci_loader as ul  # noqa: E402
from deep_support import build, capped  # noqa: E402

from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import ALL_NAMES, DEEP_NAMES  # noqa: E402

PROTOCOL = "chrono-injected-v1"
SEEDS = (42, 1, 2, 3, 4)
FIT_SHARE, CONTAMINATION = 0.6, 0.05
MIN_ROWS, MAX_ROWS, MIN_COLUMNS, TREND = 1500, 20_000, 4, 0.99
DETECTORS = [n for n in ALL_NAMES if n != "drift"]
# column(s) holding the time, and how to read them; read from the first rows of each file
TIME_SPECS: dict[int, dict[str, Any]] = {
    247: {"date": "date", "format": "%d-%b-%y"},
    275: {"date": "dteday", "hour": "hr", "format": "%Y-%m-%d"},
    360: {"date": "Date", "time": "Time", "format": "%m/%d/%Y %H:%M:%S"},
    374: {"date": "date", "format": "%Y-%m-%d%H:%M:%S"},
    560: {"date": "Date", "hour": "Hour", "format": "%d/%m/%Y"},
    799: {"date": "timestamp", "format": "ISO8601", "utc": True},
    849: {"date": "DateTime", "format": "%m/%d/%Y %H:%M"},
    851: {"date": "date", "format": "%d/%m/%Y %H:%M"},
}


def parse_time(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.Series, list[str]]:
    """Timestamps of the rows and the columns that carry them."""
    used = [spec["date"]]
    text = frame[spec["date"]].astype(str)
    if "time" in spec:
        text = text + " " + frame[spec["time"]].astype(str)
        used.append(spec["time"])
    stamps = pd.to_datetime(text, format=spec["format"], errors="coerce", utc=bool(spec.get("utc")))
    if "hour" in spec:
        stamps = stamps + pd.to_timedelta(frame[spec["hour"]].astype(float), unit="h")
        used.append(spec["hour"])
    return stamps, used


def trend_columns(frame: pd.DataFrame, stamps: pd.Series) -> list[str]:
    """Columns that are an index or counter of the time order (rank correlation above TREND)."""
    rank = stamps.rank(method="first")
    return [
        c
        for c in frame.columns
        if pd.api.types.is_numeric_dtype(frame[c]) and abs(frame[c].corr(rank, "spearman")) > TREND
    ]


def load_series(uci_id: int, meta: dict[str, Any], path: Path) -> tuple[pd.DataFrame, dict]:
    """Chronologically sorted continuous columns of one table, with a report."""
    frame = ul.read_table(path)
    stamps, used = parse_time(frame, TIME_SPECS[uci_id])
    if stamps.isna().any():
        raise inj.NotEligible(f"{int(stamps.isna().sum())} timestamps could not be read")
    report: dict[str, Any] = {
        "rows_in": len(frame),
        "time_columns": used,
        "file_order_chronological": bool(stamps.is_monotonic_increasing),
        "span": [str(stamps.min()), str(stamps.max())],
    }
    features, _ = ul.split_columns(frame, meta)
    features = features.drop(columns=[c for c in used if c in features.columns])
    trended = trend_columns(features, stamps)
    features = features.drop(columns=trended)
    columns = inj.continuous_columns(features)
    report["trend_columns_dropped"] = trended
    if len(columns) < MIN_COLUMNS:
        raise inj.NotEligible(f"only {len(columns)} continuous columns")
    table = features[columns].astype(float).assign(_t=stamps.to_numpy())
    table = table.sort_values("_t", kind="stable").dropna()
    table = table.drop_duplicates(subset=columns).reset_index(drop=True)
    if len(table) < MIN_ROWS:
        raise inj.NotEligible(f"only {len(table)} rows after cleaning")
    if len(table) > MAX_ROWS:
        stride = int(np.ceil(len(table) / MAX_ROWS))
        report["stride"] = stride
        table = table.iloc[::stride].reset_index(drop=True)
    report.update(rows_out=len(table), columns=columns)
    return table.drop(columns="_t"), report


def split_arm(table: pd.DataFrame, arm: str, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(FIT_SHARE * len(table))
    if arm == "chronological":
        return table.iloc[:cut].reset_index(drop=True), table.iloc[cut:].reset_index(drop=True)
    order = np.random.default_rng(seed).permutation(len(table))
    return (
        table.iloc[order[:cut]].reset_index(drop=True),
        table.iloc[order[cut:]].reset_index(drop=True),
    )


def evaluate_arm(table, arm, seed, names):
    fit, test = split_arm(table, arm, seed)
    frame = inj.inject(test, seed=seed, reference=fit)
    cols = list(table.columns)
    types = frame["anomaly_type"]
    fit_x = fit.assign(t=pd.Timestamp("2020-01-01"))
    out: dict[str, Any] = {
        "counts": {t: int((types == t).sum()) for t in ["clean", *inj.ANOMALY_TYPES]}
    }
    hits, false_alarms = {}, {}
    for name in names:
        flags = detect(
            frame[[*cols, "t"]], build(name, CONTAMINATION, seed), fit_df=capped(fit_x, name, seed)
        ).flags
        flags = pd.Series(np.asarray(flags), index=frame.index)
        false_alarms[name] = int(flags[types == "clean"].sum())
        hits[name] = {t: int(flags[types == t].sum()) for t in inj.ANOMALY_TYPES}
    out.update(hits=hits, false_alarms=false_alarms)
    return out


def run_one(item: tuple[int, dict[str, Any]], names: list[str] | None = None) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    uci_id, meta = item
    names = names or DETECTORS
    table, report = load_series(uci_id, meta, ROOT / "data" / "pool" / f"{uci_id}.csv")
    arms: dict[str, Any] = {}
    for arm in ("chronological", "random"):
        runs = [evaluate_arm(table, arm, seed, names) for seed in SEEDS]
        clean = sum(r["counts"]["clean"] for r in runs)
        counts = {t: sum(r["counts"][t] for r in runs) for t in inj.ANOMALY_TYPES}
        arms[arm] = {
            "clean_rows": clean,
            "test_counts": counts,
            "fpr": {m: sum(r["false_alarms"][m] for r in runs) / clean for m in names},
            "recall": {
                m: {t: sum(r["hits"][m][t] for r in runs) / counts[t] for t in inj.ANOMALY_TYPES}
                for m in names
            },
        }
    return {
        "protocol": PROTOCOL,
        "id": f"uci:{uci_id}",
        "name": meta["name"],
        "seeds": list(SEEDS),
        "contamination": CONTAMINATION,
        "carrier": report,
        "arms": arms,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--methods", choices=("classical", "deep"), default="classical")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", nargs="*", type=int)
    args = parser.parse_args(argv)
    from concurrent.futures import ProcessPoolExecutor
    from functools import partial as bind

    from etl_benchmark.atomic import atomic_path

    meta = {
        m["uci_id"]: m
        for m in json.loads(
            (ROOT / "verification/evidence/dataset_registry/uci_curated.json").read_text()
        )["kept"]
    }
    ids = [i for i in TIME_SPECS if not args.only or i in args.only]
    folder = args.output / args.methods
    folder.mkdir(parents=True, exist_ok=True)
    names = list(DEEP_NAMES) if args.methods == "deep" else None
    skipped = {}
    todo = []
    for i in ids:  # eligibility is a property of the table: record, do not hide
        try:
            load_series(i, meta[i], ROOT / "data" / "pool" / f"{i}.csv")
            todo.append((i, meta[i]))
        except inj.NotEligible as reason:
            skipped[f"uci:{i}"] = str(reason)
    with atomic_path(args.output / "eligibility.json") as partial:
        partial.write_text(json.dumps({"skipped": skipped, "run": [f"uci:{i}" for i, _ in todo]}))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for (i, _), result in zip(todo, pool.map(bind(run_one, names=names), todo), strict=True):
            with atomic_path(folder / f"uci_{i}.json") as partial:
                partial.write_text(json.dumps(result, sort_keys=True) + "\n")
            print(i, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
