"""Train-only replay of the chronological study (T062/T063, protocol ``chrono-train-only-v1``).

The archived chronological study (``pool_chrono``) builds the feature matrix of a dataset from the
whole table: constant columns, the category cap, the one-hot vocabulary and the removal of exact
duplicates read rows of the test period. Here the rows are ordered in time first, the schema (kept
columns, category levels) is fitted on the oldest 70% of the rows only, and it is applied
unchanged to the later rows (unseen levels become all-zero indicators). Rows are not removed. The
labels, the time rule, the partitions (70/15/15 in time order), the detectors, their caps and the
metrics are those of the archived study. Exploratory; archived results are compared, never
overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import pool_chrono as pc  # noqa: E402
import temporal_decision as td  # noqa: E402
import uci_loader as ul  # noqa: E402

PROTOCOL = "chrono-train-only-v1"
TRAIN_SHARE = 0.70


def fit_schema(
    train: pd.DataFrame,
    cap: int | None = pc.CATEGORY_CAP,
    drop_constant: bool = True,
    na_indicator: bool = False,
) -> dict[str, Any]:
    """Columns and category levels read from training rows only."""
    kept: dict[str, Any] = {}
    for name in train.columns:
        column = train[name]
        if drop_constant and column.dropna().nunique() <= 1:
            continue
        if pd.api.types.is_numeric_dtype(column) and not pd.api.types.is_bool_dtype(column):
            kept[name] = None
        elif cap is None or column.nunique() <= cap:
            levels = sorted(column.dropna().astype(str).unique())
            if not na_indicator and column.isna().any():
                levels = sorted({*levels, "nan"})
            kept[name] = levels
    return {"columns": kept, "na_indicator": na_indicator}


def apply_schema(frame: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    """Numeric columns as floats and the training levels as indicators; unseen levels are zeros."""
    pieces = []
    for name, levels in schema["columns"].items():
        column = frame[name]
        if levels is None:
            pieces.append(column.astype(float).rename(name))
            continue
        text = column.astype(str).where(column.notna(), "nan")
        for level in levels:
            pieces.append((text == level).astype(float).rename(f"{name}_{level}"))
        if schema["na_indicator"]:
            pieces.append(column.isna().astype(float).rename(f"{name}_nan"))
    return pd.concat(pieces, axis=1)


def split_features(
    raw: pd.DataFrame, times: pd.Series, **options: Any
) -> tuple[pd.DataFrame, np.ndarray]:
    """Time-ordered features whose schema comes from the oldest 70% of the rows, and the order."""
    order = np.argsort(pd.to_datetime(times, utc=True).to_numpy(), kind="stable")
    ordered = raw.iloc[order].reset_index(drop=True)
    schema = fit_schema(ordered.iloc[: int(len(ordered) * TRAIN_SHARE)], **options)
    return apply_schema(ordered, schema), order


def credit_card_raw() -> tuple[pd.DataFrame, np.ndarray, pd.Series]:
    import temporal_pilot as tp

    from etl_benchmark.config import CREDIT_CARD_CSV
    from etl_benchmark.extract import read_csv

    frame = read_csv(CREDIT_CARD_CSV)
    times = tp.to_timestamps(frame["Time"])
    return frame.drop(columns=["Time", "Class"]), frame["Class"].to_numpy().astype(int), times


def bank_raw(path: Path) -> tuple[pd.DataFrame, np.ndarray, pd.Series]:
    frame = ul.read_table(path)
    months = pc.MONTHS
    index = frame["month"].map(months.index).to_numpy()
    year = 2008 + np.cumsum(np.r_[0, np.diff(index) < 0])
    within = frame.groupby([year, index]).cumcount().to_numpy()
    times = pd.to_datetime(
        pd.DataFrame({"year": year, "month": index + 1, "day": 1})
    ).dt.tz_localize("UTC") + pd.to_timedelta(within, unit="min")
    y = (frame["y"] == "yes").to_numpy().astype(int)
    return frame.drop(columns=["y", "month"]), y, times


def pool_raw(
    meta: dict[str, Any], path: Path, uci_id: int
) -> tuple[pd.DataFrame, np.ndarray, pd.Series, int]:
    """Raw feature columns, labels by the pool rule and row times, without any encoding."""
    frame = ul.read_table(path)
    times = pc.read_times(frame, uci_id)
    unreadable = int(times.isna().sum())
    frame, times = frame[times.notna().to_numpy()].reset_index(drop=True), times.dropna()
    times = times.reset_index(drop=True)
    marked = frame.assign(__row__=np.arange(len(frame), dtype=float))
    features, labels, _info = ul.derive_labels(marked, meta)
    rows = features.pop("__row__").to_numpy().astype(int)
    columns = set(pc.TIME_COLUMNS[uci_id])
    features = features[[c for c in features.columns if c not in columns]]
    return features.reset_index(drop=True), labels, times.iloc[rows].reset_index(drop=True), unreadable


def run_raw(
    raw: pd.DataFrame, y: np.ndarray, times: pd.Series, methods: list[str] | None = None, **opts
) -> dict[str, Any]:
    """The archived ``run_dataset`` on features whose schema is fitted on training rows."""
    ok, reason = pc.eligible(y, times)
    if not ok:
        return {"excluded": reason}
    features, order = split_features(raw, times, **opts)
    ordered_times = times.iloc[order].reset_index(drop=True)
    result = pc.run_dataset(features, np.asarray(y)[order], ordered_times, methods)
    return {**result, "protocol": PROTOCOL, "feature_count": int(features.shape[1])}


def compare(archive: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    """Paired replay-minus-archive differences of the chronological and stratified metrics."""
    out: dict[str, Any] = {}
    for name in sorted(set(archive) & set(replay)):
        a, r = archive[name], replay[name]
        if "excluded" in a or "excluded" in r:
            out[name] = {"excluded_archive": a.get("excluded"), "excluded_replay": r.get("excluded")}
            continue
        methods = [m for m in a["chronological"] if m in r["chronological"]]
        rows = {}
        for m in methods:
            rows[m] = {
                "pr_auc_archive": a["chronological"][m]["pr_auc"],
                "pr_auc_replay": r["chronological"][m]["pr_auc"],
                "chronological_pr_auc_difference": r["chronological"][m]["pr_auc"]
                - a["chronological"][m]["pr_auc"],
                "chronological_roc_auc_difference": r["chronological"][m]["roc_auc"]
                - a["chronological"][m]["roc_auc"],
                "stratified_pr_auc_difference": r["stratified"][m]["pr_auc"]
                - a["stratified"][m]["pr_auc"],
            }
        ranks = pd.DataFrame(
            {k: [rows[m][k] for m in methods] for k in ("pr_auc_archive", "pr_auc_replay")}
        )
        out[name] = {
            "methods": rows,
            "spearman_of_chronological_pr_auc": float(
                ranks["pr_auc_archive"].corr(ranks["pr_auc_replay"], method="spearman")
            ),
            "median_chronological_difference": float(
                np.median([v["chronological_pr_auc_difference"] for v in rows.values()])
            ),
            "partitions_equal": a["partitions"] == r["partitions"],
            "partitions": {"archive": a["partitions"], "replay": r["partitions"]},
        }
    return out


def write_json(path: Path, payload: Any) -> None:
    """Write ``payload`` atomically as sorted, one-space-indented JSON with a final newline."""
    from etl_benchmark.atomic import atomic_path

    with atomic_path(path) as partial:
        partial.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")


def datasets(meta: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Dataset name -> (loader, schema options) for the five datasets of the archived study."""
    jobs: dict[str, Any] = {
        "credit_card": (credit_card_raw, {"drop_constant": False, "cap": None}),
        "bank_marketing": (
            lambda: bank_raw(ROOT / "data" / "pool" / "222.csv"),
            {"drop_constant": False, "cap": None, "na_indicator": True},
        ),
    }
    for uci_id in pc.TIME_COLUMNS:
        name = meta[uci_id]["name"].strip().lower().replace(" ", "_")
        jobs[name] = (
            lambda u=uci_id: pool_raw(meta[u], ROOT / "data" / "pool" / f"{u}.csv", u),
            {},
        )
    return jobs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="*", help="dataset names, for a quick check")
    parser.add_argument("--methods", nargs="*", help="detector names (default: all 17)")
    parser.add_argument(
        "--archive", type=Path, default=ROOT / "verification/evidence/pool_extension/chrono"
    )
    args = parser.parse_args(argv)
    registry = ROOT / "verification" / "evidence" / "dataset_registry"
    meta = {m["uci_id"]: m for m in json.loads((registry / "uci_curated.json").read_text())["kept"]}
    args.output.mkdir(parents=True, exist_ok=True)
    for name, (loader, options) in datasets(meta).items():
        if args.only and name not in args.only:
            continue
        loaded = loader()
        raw, y, times = loaded[:3]
        result = run_raw(raw, y, times, args.methods, **options)
        if len(loaded) == 4:
            result["rows_without_a_readable_time"] = loaded[3]
        write_json(args.output / f"{name}.json", result)
        print(name, result.get("excluded", "ok"))
    runs = {
        p.stem: json.loads(p.read_text())
        for p in args.output.glob("*.json")
        if p.stem != "comparison"
    }
    archived = {p.stem: json.loads(p.read_text()) for p in args.archive.glob("*.json")}
    write_json(args.output / "comparison.json", {"protocol": PROTOCOL, "datasets": compare(archived, runs)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
