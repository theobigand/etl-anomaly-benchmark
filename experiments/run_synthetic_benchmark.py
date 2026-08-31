"""Method-by-anomaly-type benchmark on the synthetic dataset.

Protocol, for each of ``--seeds`` random seeds:

    1. generate the labelled synthetic dataset with that seed;
    2. stratified 70 / 15 / 15 split on ``anomaly_type``;
    3. fit every detector on ``train`` (ML contamination = the train-set
       anomaly prevalence), score ``test``;
    4. record aggregate metrics on ``test`` and, per anomaly type, the
       recall and the precision on a stream of clean rows plus that type.

Results are averaged over the seeds (mean and standard deviation). The
mean recall matrix is rendered as the paper's heatmap. Exact duplicates
are a transform-stage concern, so the deduplication rule is carried as an
extra reference row.

Usage::

    python experiments/run_synthetic_benchmark.py
    python experiments/run_synthetic_benchmark.py --seeds 42 --rows 3000   # quick
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
import numpy as np  # noqa: E402
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
from etl_benchmark.registry import ALL_NAMES, all_detectors  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES, FEATURE_COLUMNS, make_synthetic  # noqa: E402

log = logging.getLogger(__name__)

PAPER_FIGURE = config.PROJECT_ROOT / "paper" / "figures" / "heatmap_synthetic.png"
_DEDUP = "__dedup__"

_TYPE_LABELS = {
    "missing_value": "missing\nvalue",
    "duplicate": "duplicate",
    "univariate_outlier": "univariate\noutlier",
    "multivariate_outlier": "multivariate\noutlier",
    "temporal_drift": "temporal\ndrift",
    "invalid_format": "invalid\nformat",
}


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the whole-stream deduplication flag before the split."""
    df = df.copy()
    df[_DEDUP] = df.duplicated(subset=FEATURE_COLUMNS, keep=False).to_numpy()
    return df


def _per_type(flags: pd.Series, anomaly_type: pd.Series) -> tuple[dict, dict]:
    """Recall and precision per type, negatives restricted to clean rows."""
    recall, precision = {}, {}
    clean = anomaly_type == "clean"
    for name in ANOMALY_TYPES:
        is_type = anomaly_type == name
        keep = is_type | clean
        y = is_type[keep].astype(int)
        f = flags[keep]
        recall[name] = recall_score(y, f, zero_division=0) if is_type.any() else np.nan
        precision[name] = precision_score(y, f, zero_division=0)
    return recall, precision


def _dedup_flags_for(part: pd.DataFrame) -> pd.Series:
    return part[_DEDUP].astype(bool)


def evaluate(df: pd.DataFrame, seed: int) -> dict[str, pd.DataFrame]:
    """One split: fit on train, score test. ``df`` must be :func:`_prepare` d."""
    train, _val, test = stratified_split(df, "anomaly_type", config.SPLIT_RATIOS, seed)
    contamination = float(train["anomaly"].mean())
    train_x, test_x = train[FEATURE_COLUMNS], test[FEATURE_COLUMNS]
    y_test = test["anomaly"].astype(int)
    type_test = test["anomaly_type"]

    metrics, recall, precision = [], [], []
    detectors = all_detectors(ml_contamination=contamination, names=ALL_NAMES)
    for det in detectors + ["transform_dedup"]:
        if det == "transform_dedup":
            name, flags, scores = "transform_dedup", _dedup_flags_for(test), _dedup_flags_for(test)
            detect_s = np.nan
        else:
            name = det.name
            res = detect(test_x, det, fit_df=train_x)
            flags, scores, detect_s = res.flags, res.scores, res.detect_s
        log.info("  seed %d: %s done", seed, name)
        metrics.append(
            {
                "method": name,
                "precision": precision_score(y_test, flags, zero_division=0),
                "recall": recall_score(y_test, flags, zero_division=0),
                "f1": f1_score(y_test, flags, zero_division=0),
                "roc_auc": roc_auc_score(y_test, scores),
                "pr_auc": average_precision_score(y_test, scores),
                "flagged_pct": 100.0 * float(np.mean(flags)),
                "detect_s": detect_s,
            }
        )
        r, p = _per_type(pd.Series(np.asarray(flags), index=test.index), type_test)
        recall.append({"method": name, **r})
        precision.append({"method": name, **p})

    return {
        "metrics": pd.DataFrame(metrics).set_index("method"),
        "recall": pd.DataFrame(recall).set_index("method"),
        "precision": pd.DataFrame(precision).set_index("method"),
    }


def run(seeds: list[int], rows: int | None = None) -> dict[str, pd.DataFrame]:
    """Repeat :func:`evaluate` over ``seeds`` and average."""
    kw = {"n_rows": rows} if rows else {}
    per_seed = [evaluate(_prepare(make_synthetic(seed=s, **kw)), s) for s in seeds]
    out: dict[str, pd.DataFrame] = {}
    for key in ("metrics", "recall", "precision"):
        stack = pd.concat([p[key] for p in per_seed], keys=range(len(seeds)))
        grouped = stack.groupby(level=1, sort=False)
        out[f"{key}_mean"] = grouped.mean()
        out[f"{key}_std"] = grouped.std().fillna(0.0)
    return out


def render_heatmap(recall_mean: pd.DataFrame, path: Path) -> Path:
    matrix = recall_mean[ANOMALY_TYPES]
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

    ax.set_title("Mean detection rate by anomaly type (synthetic, 5 seeds)")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.03, label="recall on that type")
    fig.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _combined_md(mean: pd.DataFrame, std: pd.DataFrame, cols: list[str]) -> str:
    lines = [
        "| method | " + " | ".join(cols) + " |",
        "| --- | " + " | ".join("---" for _ in cols) + " |",
    ]
    for method in mean.index:
        cells = []
        for c in cols:
            m, s = mean.loc[method, c], std.loc[method, c]
            cells.append("-" if pd.isna(m) else f"{m:.3f} ± {s:.3f}")
        lines.append(f"| {method} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(config.BENCHMARK_SEEDS))
    parser.add_argument("--rows", type=int, default=None, help="smaller dataset for a quick run")
    parser.add_argument("--figure", type=Path, default=PAPER_FIGURE)
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    log.info("seeds: %s", args.seeds)
    r = run(args.seeds, args.rows)

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    metric_cols = ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct", "detect_s"]
    r["metrics_mean"].join(r["metrics_std"], lsuffix="_mean", rsuffix="_std").to_csv(
        config.RESULTS_DIR / f"synthetic_metrics_{stamp}.csv"
    )
    r["recall_mean"].join(r["recall_std"], lsuffix="_mean", rsuffix="_std").to_csv(
        config.RESULTS_DIR / f"synthetic_recall_{stamp}.csv"
    )
    r["precision_mean"].join(r["precision_std"], lsuffix="_mean", rsuffix="_std").to_csv(
        config.RESULTS_DIR / f"synthetic_precision_{stamp}.csv"
    )
    md = (
        f"Synthetic dataset, {len(args.seeds)} seeds, mean ± std on the 15% test split.\n\n"
        "### Aggregate metrics\n\n"
        + _combined_md(r["metrics_mean"], r["metrics_std"], metric_cols)
        + "\n### Recall by anomaly type\n\n"
        + _combined_md(r["recall_mean"], r["recall_std"], ANOMALY_TYPES)
        + "\n### Precision by anomaly type (clean rows as the only negatives)\n\n"
        + _combined_md(r["precision_mean"], r["precision_std"], ANOMALY_TYPES)
    )
    (config.RESULTS_DIR / f"synthetic_{stamp}.md").write_text(md)
    figure = render_heatmap(r["recall_mean"], args.figure)

    print("\n" + md)
    log.info("figure -> %s", figure)


if __name__ == "__main__":
    main()
