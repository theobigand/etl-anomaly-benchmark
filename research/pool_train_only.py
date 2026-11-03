"""Explicit exploratory consumer of source-bound, frozen pool partitions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import pandas as pd

from etl_benchmark.atomic import atomic_path
from etl_benchmark.metrics import compute_metrics
from etl_benchmark.pipeline import detect
from etl_benchmark.registry import DEEP_NAMES, DETECTOR_NAMES, clip_contamination
from experiments.provenance import write_record
from research.deep_support import build, capped
from research.normalise import skipped_detectors
from research.pool_preprocessing import PARTITIONS, prepare_frozen

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "pool-train-only-v1"
RESEARCH_SOURCES = (
    "research/pool_preprocessing.py",
    "research/pool_train_only.py",
    "research/deep_support.py",
    "research/normalise.py",
)


def evaluate_frozen(
    frame: pd.DataFrame, labels, partitions: dict, *, seed: int, methods: list[str]
) -> dict:
    """Run named detectors on unchanged positions with training-only preparation."""
    if (
        not methods
        or len(set(methods)) != len(methods)
        or set(methods) - set([*DETECTOR_NAMES, *DEEP_NAMES])
    ):
        raise ValueError("detectors must be explicit, unique row-level registry names")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be a nonnegative 32-bit integer")
    prepared = prepare_frozen(frame, partitions)
    y = np.asarray(labels)
    if y.ndim != 1 or len(y) != len(frame) or set(np.unique(y)) - {0, 1}:
        raise ValueError("labels must be an aligned binary vector")
    for name in PARTITIONS:
        if set(np.unique(y[partitions[name]])) != {0, 1}:
            raise ValueError("both classes are required in every frozen partition")
    train, test = prepared["train"], prepared["test"]
    contamination = clip_contamination(float(y[partitions["train"]].mean()))
    result = {
        "protocol": PROTOCOL,
        "exploratory": True,
        "seed": seed,
        "partitions": {name: list(partitions[name]) for name in PARTITIONS},
        "preprocessing": prepared["fit"],
        "calibration": {"policy": "train_prevalence", "value": contamination},
        "prevalence": {name: float(y[partitions[name]].mean()) for name in PARTITIONS},
        "runs": {},
        "errors": [],
        "skipped": [],
    }
    skipped = skipped_detectors(len(train))
    for method in methods:
        if method in skipped:
            result["skipped"].append(method)
            continue
        fit = capped(train, method, seed)
        try:
            detector = build(method, contamination, seed)
            found = detect(test, detector, fit_df=fit)
            result["runs"][method] = {
                "metrics": compute_metrics(y[partitions["test"]], found.flags, found.scores),
                "scores": found.scores.tolist(),
                "flags": found.flags.tolist(),
                "fit_rows": len(fit),
            }
        except Exception as error:
            result["errors"].append({"detector": method, "error": repr(error)})
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _optional_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--partitions", type=Path, required=True)
    parser.add_argument("--label-column", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--detectors", nargs="+", required=True)
    args = parser.parse_args(argv)
    record_path = args.output.with_suffix(".record.json")
    if args.output.exists() or record_path.exists():
        raise FileExistsError("choose unused output and record paths")
    manifest = json.loads(args.partitions.read_text())
    if manifest["schema_version"] != 1 or manifest["input_sha256"] != _sha256(args.csv):
        raise ValueError("partition manifest version or source hash differs")
    with args.csv.open(newline="") as stream:
        header = next(csv.reader(stream))
    if len(set(header)) != len(header):
        raise ValueError("duplicate CSV column names are not accepted")
    frame = pd.read_csv(args.csv, dtype=str)
    if manifest["row_count"] != len(frame):
        raise ValueError("partition manifest row count differs")
    labels = pd.to_numeric(frame.pop(args.label_column), errors="raise").to_numpy()
    result = evaluate_frozen(
        frame, labels, manifest["partitions"], seed=manifest["seed"], methods=args.detectors
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    write_record(
        record_path,
        experiment=PROTOCOL,
        seeds=[manifest["seed"]],
        dataset=args.csv.name,
        data_path=args.csv,
        settings={
            "protocol": PROTOCOL,
            "exploratory": True,
            "label_column": args.label_column,
            "detectors": args.detectors,
            "partition_sha256": _sha256(args.partitions),
            "research_sha256": {name: _sha256(ROOT / name) for name in RESEARCH_SOURCES},
            "torch": _optional_version("torch"),
        },
        outputs=[args.output.name],
    )
    return 1 if result["errors"] or not result["runs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
