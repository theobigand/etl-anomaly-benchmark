"""Inspect available real datasets and record provenance without copying raw data."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from etl_benchmark import config
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS, DatasetSpec


def inspect_dataset(spec: DatasetSpec) -> dict:
    """Record file identity, label convention and the post-transform population."""
    if not spec.csv.is_file():
        return {
            "dataset": spec.name,
            "status": "NOT_RUN",
            "reason": "dataset file absent",
            "path": str(spec.csv),
        }
    try:
        digest = hashlib.sha256()
        with spec.csv.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        raw = pd.read_csv(spec.csv)
        frame = spec.load()
        features = spec.features(frame)
        if frame.empty or features.empty or frame[ANOMALY_COLUMN].nunique() != 2:
            raise ValueError("dataset must have rows, features and both label classes")
        return {
            "dataset": spec.name,
            "status": "PASS",
            "path": str(spec.csv),
            "sha256": digest.hexdigest(),
            "bytes": spec.csv.stat().st_size,
            "raw_rows": len(raw),
            "rows_after_transform": len(frame),
            "deduplicated_rows": len(raw) - len(frame),
            "anomalies": int(frame[ANOMALY_COLUMN].sum()),
            "positive_value": spec.positive_value,
            "label_column": spec.label_column,
            "features": list(features.columns),
            "missing_by_feature": {key: int(value) for key, value in features.isna().sum().items()},
        }
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        return {"dataset": spec.name, "status": "FAIL", "reason": str(exc), "path": str(spec.csv)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=config.RESULTS_DIR / "real_verification.json"
    )
    args = parser.parse_args()
    records = [inspect_dataset(spec) for spec in DATASETS.values()]
    report = {"captured_at": datetime.now(UTC).isoformat(), "datasets": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for item in records:
        print(f"{item['dataset']}: {item['status']}")
    return 0 if all(item["status"] == "PASS" for item in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
