"""Method-by-anomaly-type benchmark on the synthetic dataset.

Every detector is run through the pipeline's quality stage on the
controlled synthetic dataset, then scored two ways:

    * aggregate detection metrics (precision, recall, F1, ROC-AUC,
      PR-AUC, flagged %, in-pipeline latency), exactly as
      ``run_benchmark.py`` does on Credit Card Fraud;
    * a per-anomaly-type recall matrix -- for each of the six injected
      categories, the share of that category's rows the method flags.
      This matrix is the paper's central figure: it maps each family of
      detectors to the kinds of data-quality problem it actually catches.

The exact-duplicate rows are a transform-stage concern, not a detector
one, so the deduplication rule (``DataFrame.duplicated``) is reported as
an extra reference row.

Usage::

    python experiments/run_synthetic_benchmark.py
    python experiments/run_synthetic_benchmark.py --rows 4000   # quick
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")  # silence Great Expectations progress bars

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from etl_benchmark import config  # noqa: E402
from etl_benchmark.logging_setup import setup_logging  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import all_detectors  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES, FEATURE_COLUMNS, make_synthetic  # noqa: E402

log = logging.getLogger(__name__)

PAPER_FIGURE = config.PROJECT_ROOT / "paper" / "figures" / "heatmap_synthetic.png"

_TYPE_LABELS = {
    "missing_value": "missing\nvalue",
    "duplicate": "duplicate",
    "univariate_outlier": "univariate\noutlier",
    "multivariate_outlier": "multivariate\noutlier",
    "temporal_drift": "temporal\ndrift",
    "invalid_format": "invalid\nformat",
}


def _load(rows: int | None, seed: int) -> pd.DataFrame:
    if rows is not None:
        return make_synthetic(n_rows=rows, seed=seed)
    if config.SYNTHETIC_CSV.exists():
        log.info("loading %s", config.SYNTHETIC_CSV)
        return pd.read_csv(config.SYNTHETIC_CSV)
    log.info("no data/synthetic.csv, generating in memory")
    return make_synthetic(seed=seed)


def _per_type_recall(flags: pd.Series, anomaly_type: pd.Series) -> dict[str, float]:
    row: dict[str, float] = {}
    for name in ANOMALY_TYPES:
        mask = anomaly_type == name
        row[name] = float(flags[mask].mean()) if mask.any() else float("nan")
    row["clean_fp_rate"] = float(flags[anomaly_type == "clean"].mean())
    return row


def run(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = df[FEATURE_COLUMNS]
    y_true = df["anomaly"].astype(int)
    anomaly_type = df["anomaly_type"]
    log.info("%d rows, %d anomalies (%.1f%%)", len(df), int(y_true.sum()), 100 * y_true.mean())

    metrics_rows: list[dict] = []
    heatmap_rows: list[dict] = []

    for detector in all_detectors():
        log.info("evaluating %s", detector.name)
        res = detect(features, detector)
        metrics_rows.append(
            {
                "method": detector.name,
                "precision": precision_score(y_true, res.flags, zero_division=0),
                "recall": recall_score(y_true, res.flags, zero_division=0),
                "f1": f1_score(y_true, res.flags, zero_division=0),
                "roc_auc": roc_auc_score(y_true, res.scores),
                "pr_auc": average_precision_score(y_true, res.scores),
                "flagged_pct": 100.0 * float(res.flags.mean()),
                "detect_s": res.detect_s,
            }
        )
        heatmap_rows.append({"method": detector.name, **_per_type_recall(res.flags, anomaly_type)})

    # Deduplication rule: a transform-stage check, reported for reference.
    # ``keep=False`` flags every row of a duplicate group -- a naive rule
    # cannot tell the original from its copy, hence the clean false positives.
    dedup_flags = df.duplicated(subset=FEATURE_COLUMNS, keep=False)
    dedup_flags.index = df.index
    metrics_rows.append(
        {
            "method": "transform_dedup",
            "precision": precision_score(y_true, dedup_flags, zero_division=0),
            "recall": recall_score(y_true, dedup_flags, zero_division=0),
            "f1": f1_score(y_true, dedup_flags, zero_division=0),
            "roc_auc": roc_auc_score(y_true, dedup_flags.astype(float)),
            "pr_auc": average_precision_score(y_true, dedup_flags.astype(float)),
            "flagged_pct": 100.0 * float(dedup_flags.mean()),
            "detect_s": float("nan"),
        }
    )
    heatmap_rows.append(
        {"method": "transform_dedup", **_per_type_recall(dedup_flags, anomaly_type)}
    )

    metrics = pd.DataFrame(metrics_rows).set_index("method")
    heatmap = pd.DataFrame(heatmap_rows).set_index("method")
    return metrics, heatmap


def render_heatmap(heatmap: pd.DataFrame, path: Path) -> Path:
    matrix = heatmap[ANOMALY_TYPES]
    fig, ax = plt.subplots(figsize=(8.0, 0.7 * len(matrix) + 1.6))
    im = ax.imshow(matrix.to_numpy(), cmap="YlGnBu", vmin=0.0, vmax=1.0, aspect="auto")

    ax.set_xticks(range(len(ANOMALY_TYPES)))
    ax.set_xticklabels([_TYPE_LABELS[t] for t in ANOMALY_TYPES])
    ax.set_yticks(range(len(matrix)))
    ax.set_yticklabels(matrix.index)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.to_numpy()[i, j]
            ax.text(
                j,
                i,
                "-" if pd.isna(value) else f"{value:.2f}",
                ha="center",
                va="center",
                color="white" if value > 0.55 else "black",
                fontsize=9,
            )

    ax.set_title("Detection rate by anomaly type (synthetic dataset)")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.03, label="recall on that type")
    fig.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _to_markdown(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = [
        "| method | " + " | ".join(cols) + " |",
        "| --- | " + " | ".join("---" for _ in cols) + " |",
    ]
    for method, row in df.iterrows():
        cells = [floatfmt.format(row[c]) if pd.notna(row[c]) else "-" for c in cols]
        lines.append(f"| {method} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=None, help="generate N rows in memory instead")
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    parser.add_argument("--figure", type=Path, default=PAPER_FIGURE)
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    df = _load(args.rows, args.seed)
    metrics, heatmap = run(df)

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    metrics.to_csv(config.RESULTS_DIR / f"synthetic_metrics_{stamp}.csv")
    heatmap.to_csv(config.RESULTS_DIR / f"synthetic_heatmap_{stamp}.csv")
    (config.RESULTS_DIR / f"synthetic_{stamp}.md").write_text(
        "### Aggregate metrics\n\n"
        + _to_markdown(metrics)
        + "\n### Detection rate by anomaly type\n\n"
        + _to_markdown(heatmap[ANOMALY_TYPES])
    )
    figure = render_heatmap(heatmap, args.figure)

    print("\n### Aggregate metrics\n")
    print(_to_markdown(metrics))
    print("### Detection rate by anomaly type\n")
    print(_to_markdown(heatmap[ANOMALY_TYPES]))
    log.info("figure -> %s", figure)


if __name__ == "__main__":
    main()
