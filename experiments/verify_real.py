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

MANIFEST = config.PROJECT_ROOT / "verification" / "evidence" / "manifest.json"
# The research files REAL must verify. A registry that lists fewer, more or
# other datasets cannot produce a PASS.
REQUIRED_DATASETS = ("credit_card", "water_quality", "cardio")


def inspect_dataset(spec: DatasetSpec, expected: dict | None = None) -> dict:
    """Record file identity, label convention and the post-transform population."""
    if not spec.csv.is_file():
        return {
            "dataset": spec.name,
            "status": "NOT_RUN",
            "reason": "dataset file absent",
            "path": str(spec.csv),
        }
    try:
        with spec.csv.open("rb") as stream:
            digest = hashlib.file_digest(stream, hashlib.sha256)
        raw = pd.read_csv(spec.csv)
        frame = spec.load()
        features = spec.features(frame)
        if frame.empty or features.empty or frame[ANOMALY_COLUMN].nunique() != 2:
            raise ValueError("dataset must have rows, features and both label classes")
        record = {
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
        if expected is not None:
            for field, value in expected.items():
                if field not in record:
                    raise ValueError(f"unknown reference field {field}")
                if record[field] != value:
                    label = "checksum" if field == "sha256" else field
                    raise ValueError(f"{label} differs from the reference")
        return record
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        return {"dataset": spec.name, "status": "FAIL", "reason": str(exc), "path": str(spec.csv)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=config.RESULTS_DIR / "real_verification.json"
    )
    args = parser.parse_args()
    reason = None
    if set(DATASETS) != set(REQUIRED_DATASETS):
        reason = (
            f"registry {sorted(DATASETS)} differs from the required {sorted(REQUIRED_DATASETS)}"
        )
        records = []
    else:
        try:
            reference = json.loads(MANIFEST.read_text())["datasets"]
            required = {"sha256", "raw_rows", "rows_after_transform", "anomalies", "positive_value"}
            for spec in DATASETS.values():
                missing = required - reference[spec.name].keys()
                if missing:
                    raise ValueError(f"{spec.name}: reference missing {sorted(missing)}")
            records = [
                inspect_dataset(spec, expected={key: reference[spec.name][key] for key in required})
                for spec in DATASETS.values()
            ]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            records = [
                {"dataset": spec.name, "status": "FAIL", "reason": f"reference unavailable: {exc}"}
                for spec in DATASETS.values()
            ]
    passed = [item["dataset"] for item in records if item["status"] == "PASS"]
    ok = reason is None and sorted(passed) == sorted(REQUIRED_DATASETS)
    report = {
        "captured_at": datetime.now(UTC).isoformat(),
        "required": list(REQUIRED_DATASETS),
        "status": "PASS" if ok else "FAIL",
        "datasets": records,
    }
    if reason is not None:
        report["reason"] = reason
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for item in records:
        print(f"{item['dataset']}: {item['status']}")
    if reason is not None:
        print(f"REAL: FAIL ({reason})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
