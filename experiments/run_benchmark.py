"""Compare the rule-based detectors on the Credit Card Fraud dataset.

Each detector is fitted on the (cleaned) feature matrix, then its row
predictions and continuous scores are scored against the ground-truth
``Class`` label. Results go to a timestamped CSV and a Markdown table
that can be pasted into the paper.

Usage::

    python experiments/run_benchmark.py            # full dataset
    python experiments/run_benchmark.py --limit 50000
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from etl_benchmark import config
from etl_benchmark.extract import read_csv
from etl_benchmark.logging_setup import setup_logging
from etl_benchmark.quality import (
    Detector,
    GreatExpectationsDetector,
    IQRDetector,
    ZScoreDetector,
)
from etl_benchmark.transform import clean

log = logging.getLogger(__name__)

LABEL_COLUMN = "Class"


def build_detectors() -> list[Detector]:
    return [
        ZScoreDetector(threshold=config.ZSCORE_THRESHOLD),
        IQRDetector(multiplier=config.IQR_MULTIPLIER),
        GreatExpectationsDetector(),
    ]


def evaluate(detector: Detector, features: pd.DataFrame, y_true: pd.Series) -> dict[str, float]:
    start = time.perf_counter()
    detector.fit(features)
    y_pred = detector.predict(features)
    y_score = detector.score(features)
    elapsed = time.perf_counter() - start

    n_flagged = int(y_pred.sum())
    return {
        "detector": detector.name,
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_score),
        "pr_auc": average_precision_score(y_true, y_score),
        "n_flagged": n_flagged,
        "flagged_pct": 100.0 * n_flagged / len(y_true),
        "time_s": elapsed,
    }


def run(input_path: Path, limit: int | None) -> pd.DataFrame:
    log.info("loading %s", input_path)
    df = clean(read_csv(input_path))
    if limit is not None:
        df = df.sample(n=min(limit, len(df)), random_state=config.RANDOM_SEED).reset_index(
            drop=True
        )
    log.info("%d rows x %d cols", len(df), df.shape[1])

    y_true = df[LABEL_COLUMN].astype(int)
    features = df.drop(columns=[LABEL_COLUMN])
    log.info("prevalence: %d positives (%.3f%%)", int(y_true.sum()), 100 * y_true.mean())

    rows = []
    for detector in build_detectors():
        log.info("evaluating %s", detector.name)
        rows.append(evaluate(detector, features, y_true))
    return pd.DataFrame(rows)


def to_markdown(results: pd.DataFrame) -> str:
    fmt = {
        "precision": "{:.3f}",
        "recall": "{:.3f}",
        "f1": "{:.3f}",
        "roc_auc": "{:.3f}",
        "pr_auc": "{:.3f}",
        "flagged_pct": "{:.2f}",
        "time_s": "{:.1f}",
    }
    header = "| " + " | ".join(results.columns) + " |"
    sep = "| " + " | ".join("---" for _ in results.columns) + " |"
    lines = [header, sep]
    for _, row in results.iterrows():
        cells = [fmt.get(c, "{}").format(row[c]) for c in results.columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def save(results: pd.DataFrame, results_dir: Path) -> tuple[Path, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    csv_path = results_dir / f"benchmark_{stamp}.csv"
    results.to_csv(csv_path, index=False)

    md_path = results_dir / f"benchmark_{stamp}.md"
    md_path.write_text(to_markdown(results))

    return csv_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=config.CREDIT_CARD_CSV)
    parser.add_argument("--limit", type=int, default=None, help="subsample N rows for a quick run")
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)

    results = run(args.input, args.limit)
    csv_path, md_path = save(results, config.RESULTS_DIR)

    print("\n" + results.to_string(index=False))
    log.info("saved -> %s", csv_path)
    log.info("saved -> %s", md_path)


if __name__ == "__main__":
    main()
