"""Compare the rule-based detectors on the Credit Card Fraud dataset.

Extract and transform run once; each detector is then scored through the
pipeline's quality stage (:func:`etl_benchmark.pipeline.detect`), so every
method sees the exact same data path and its in-pipeline latency is
measured. Predictions and continuous scores are compared against the
ground-truth ``Class`` label. Results go to a timestamped CSV and a
Markdown table that can be pasted into the paper.

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
from etl_benchmark.logging_setup import setup_logging
from etl_benchmark.pipeline import detect, extract, transform
from etl_benchmark.registry import all_detectors

log = logging.getLogger(__name__)

LABEL_COLUMN = "Class"


def run(input_path: Path, limit: int | None, fit_sample: int | None = None) -> pd.DataFrame:
    log.info("extract: loading %s", input_path)
    t0 = time.perf_counter()
    df = extract(input_path)
    extract_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    df = transform(df)
    transform_s = time.perf_counter() - t0

    if limit is not None:
        df = df.sample(n=min(limit, len(df)), random_state=config.RANDOM_SEED).reset_index(
            drop=True
        )
    log.info(
        "%d rows x %d cols (extract %.2fs, transform %.2fs, shared)",
        len(df),
        df.shape[1],
        extract_s,
        transform_s,
    )

    fit_df = None
    if fit_sample is not None and fit_sample < len(df):
        fit_df = df.sample(n=fit_sample, random_state=config.RANDOM_SEED)
        log.info("fitting detectors on a %d-row sample, scoring all %d rows", fit_sample, len(df))

    y_true = df[LABEL_COLUMN].astype(int)
    log.info("prevalence: %d positives (%.3f%%)", int(y_true.sum()), 100 * y_true.mean())

    rows = []
    for detector in all_detectors():
        log.info("evaluating %s", detector.name)
        res = detect(df, detector, label_column=LABEL_COLUMN, fit_df=fit_df)
        rows.append(
            {
                "detector": detector.name,
                "precision": precision_score(y_true, res.flags, zero_division=0),
                "recall": recall_score(y_true, res.flags, zero_division=0),
                "f1": f1_score(y_true, res.flags, zero_division=0),
                "roc_auc": roc_auc_score(y_true, res.scores),
                "pr_auc": average_precision_score(y_true, res.scores),
                "n_flagged": int(res.flags.sum()),
                "flagged_pct": 100.0 * float(res.flags.mean()),
                "fit_s": res.fit_s,
                "predict_s": res.predict_s,
                "detect_s": res.detect_s,
            }
        )
    return pd.DataFrame(rows)


def to_markdown(results: pd.DataFrame) -> str:
    fmt = {
        "precision": "{:.3f}",
        "recall": "{:.3f}",
        "f1": "{:.3f}",
        "roc_auc": "{:.3f}",
        "pr_auc": "{:.3f}",
        "flagged_pct": "{:.2f}",
        "fit_s": "{:.3f}",
        "predict_s": "{:.3f}",
        "detect_s": "{:.3f}",
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
    parser.add_argument(
        "--fit-sample",
        type=int,
        default=None,
        help="fit each detector on N rows but score the whole dataset "
        "(keeps every labelled positive in the evaluation while bounding "
        "the cost of quadratic models such as One-Class SVM)",
    )
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)

    results = run(args.input, args.limit, args.fit_sample)
    csv_path, md_path = save(results, config.RESULTS_DIR)

    print("\n" + to_markdown(results))
    log.info("saved -> %s", csv_path)
    log.info("saved -> %s", md_path)


if __name__ == "__main__":
    main()
