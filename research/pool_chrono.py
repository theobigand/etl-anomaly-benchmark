"""Chronological split and decisions under shift on the pool datasets with a real time variable.

Protocol: verification/pool_extension.md, study 5 (rule fixed before the results). The study of
``temporal_decision.py`` is run with the 17 detectors of the registry on Credit Card, Bank
Marketing and the labelled pool datasets that carry a date: Occupancy Detection, Room Occupancy
Estimation and Online Shoppers. A dataset is kept only if its test partition holds at least
``MIN_TEST_POSITIVES`` anomalies; the others are recorded with the reason.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import normalise as nm  # noqa: E402
import temporal_decision as td  # noqa: E402
import uci_loader as ul  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES, DETECTOR_NAMES  # noqa: E402

MIN_TEST_POSITIVES = 20
CATEGORY_CAP = nm.CATEGORY_CAP
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
#: UCI id -> how the time of a row is read from its columns
TIME_COLUMNS = {357: ("date",), 864: ("Date", "Time"), 468: ("Month",)}
PERIODS = {357: "2015-02", 864: "2017-12", 468: "2017-01"}


def read_times(frame: pd.DataFrame, uci_id: int) -> pd.Series:
    """UTC timestamps of the rows of a raw table; a month alone keeps the file order inside it."""
    columns = TIME_COLUMNS[uci_id]
    if uci_id == 468:
        month = frame["Month"].astype(str).str[:3].str.lower().map(MONTHS.index)
        within = frame.groupby(month).cumcount().to_numpy()
        base = pd.to_datetime(pd.DataFrame({"year": 2017, "month": month + 1, "day": 1}))
        return pd.Series(base.dt.tz_localize("UTC") + pd.to_timedelta(within, unit="min"))
    text = frame[columns[0]].astype(str)
    if len(columns) == 2:
        text = text + " " + frame[columns[1]].astype(str)
    return pd.Series(pd.to_datetime(text, utc=True))


def to_features(features: pd.DataFrame) -> pd.DataFrame:
    """Numeric columns, small categories one-hot, constant and high-cardinality columns dropped."""
    pieces = []
    for name in features.columns:
        column = features[name]
        if column.dropna().nunique() <= 1:
            continue
        if pd.api.types.is_numeric_dtype(column) and not pd.api.types.is_bool_dtype(column):
            pieces.append(column.astype(float).rename(name))
        elif column.nunique() <= CATEGORY_CAP:
            pieces.append(pd.get_dummies(column.astype(str), prefix=str(name), dtype=float))
    return pd.concat(pieces, axis=1)


def load_pool_dataset(
    meta: dict[str, Any], path: Path, uci_id: int
) -> tuple[pd.DataFrame, np.ndarray, pd.Series]:
    """Features, labels by the rule of the pool and row times, aligned."""
    frame = ul.read_table(path)
    times = read_times(frame, uci_id)
    marked = frame.assign(__row__=np.arange(len(frame), dtype=float))
    features, labels, _info = ul.derive_labels(marked, meta)
    rows = features.pop("__row__").to_numpy().astype(int)
    columns = set(TIME_COLUMNS[uci_id])
    features = features[[c for c in features.columns if c not in columns]]
    return to_features(features), labels, times.iloc[rows].reset_index(drop=True)


def eligible(y: np.ndarray, times: pd.Series) -> tuple[bool, str]:
    order = np.argsort(pd.to_datetime(times, utc=True).to_numpy(), kind="stable")
    n = len(y)
    positives = int(np.asarray(y)[order][int(n * 0.85) :].sum())
    if positives < MIN_TEST_POSITIVES:
        return False, f"{positives} anomalies in the test partition (at least {MIN_TEST_POSITIVES})"
    return True, ""


def methods_for(n_train: int, wanted: list[str]) -> tuple[list[str], list[str]]:
    skipped = nm.skipped_detectors(n_train)
    return [m for m in wanted if m not in skipped], [m for m in wanted if m in skipped]


def run_dataset(
    x: pd.DataFrame, y: np.ndarray, times: pd.Series, methods: list[str] | None = None
) -> dict[str, Any]:
    wanted = methods or [*DETECTOR_NAMES, *DEEP_NAMES]
    ok, reason = eligible(y, times)
    if not ok:
        return {"excluded": reason}
    run, skipped = methods_for(int(len(y) * 0.70), wanted)
    return {**td.run_frame(x, y, times, methods=run), "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="*", help="dataset names, for a quick check")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    registry = ROOT / "verification" / "evidence" / "dataset_registry"
    meta = {m["uci_id"]: m for m in json.loads((registry / "uci_curated.json").read_text())["kept"]}
    jobs: dict[str, Any] = {
        "credit_card": td.credit_card,
        "bank_marketing": lambda: td.bank_marketing(ROOT / "data" / "pool" / "222.csv"),
    }
    for uci_id in TIME_COLUMNS:
        name = meta[uci_id]["name"].strip().lower().replace(" ", "_")
        jobs[name] = lambda u=uci_id: load_pool_dataset(
            meta[u], ROOT / "data" / "pool" / f"{u}.csv", u
        )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, loader in jobs.items():
        if args.only and name not in args.only:
            continue
        x, y, times = loader()
        result = run_dataset(x, y, times)
        with atomic_path(args.output / f"{name}.json") as partial:
            partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
        print(name, result.get("excluded", "ok"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
