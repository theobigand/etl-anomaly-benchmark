"""Benchmark the detectors on a real dataset.

Protocol, for each of ``--seeds`` random seeds:

    1. stratified 70 / 15 / 15 split on the (normalised) anomaly label;
    2. fit every detector for this dataset on ``train`` (ML contamination
       = the train-set anomaly prevalence), score ``test`` through the
       pipeline's :func:`~etl_benchmark.pipeline.detect` stage;
    3. record precision, recall, F1, ROC-AUC, PR-AUC, flagged %, and the
       in-pipeline latency, all on ``test``.

Metrics are averaged over the seeds (mean and standard deviation).

Usage::

    python experiments/run_benchmark.py --dataset credit_card
    python experiments/run_benchmark.py --dataset water_quality
    python experiments/run_benchmark.py --dataset credit_card --seeds 42 --fit-sample 50000
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import UTC, datetime

os.environ.setdefault("TQDM_DISABLE", "1")

import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS, DatasetSpec  # noqa: E402
from etl_benchmark.logging_setup import setup_logging  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import all_detectors  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402

log = logging.getLogger(__name__)

METRIC_COLUMNS = ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct", "detect_s"]


def evaluate(
    spec: DatasetSpec, df: pd.DataFrame, seed: int, fit_sample: int | None
) -> pd.DataFrame:
    """One split: fit on train, score test, one row per detector."""
    train, _val, test = stratified_split(df, ANOMALY_COLUMN, config.SPLIT_RATIOS, seed)
    contamination = float(train[ANOMALY_COLUMN].mean())
    fit_df = spec.features(train)
    if fit_sample is not None and fit_sample < len(fit_df):
        fit_df = fit_df.sample(n=fit_sample, random_state=seed)
    test_x = spec.features(test)
    y_test = test[ANOMALY_COLUMN].to_numpy()

    rows = []
    for det in all_detectors(ml_contamination=contamination, names=spec.detector_names):
        res = detect(test_x, det, fit_df=fit_df)
        row = {
            "detector": det.name,
            "precision": precision_score(y_test, res.flags, zero_division=0),
            "recall": recall_score(y_test, res.flags, zero_division=0),
            "f1": f1_score(y_test, res.flags, zero_division=0),
            "roc_auc": roc_auc_score(y_test, res.scores),
            "pr_auc": average_precision_score(y_test, res.scores),
            "flagged_pct": 100.0 * float(res.flags.mean()),
            "detect_s": res.detect_s,
        }
        rows.append(row)
        log.info(
            "  seed %d %-18s P=%.3f R=%.3f F1=%.3f ROC=%.3f PR=%.3f flag=%.1f%%",
            seed,
            det.name,
            row["precision"],
            row["recall"],
            row["f1"],
            row["roc_auc"],
            row["pr_auc"],
            row["flagged_pct"],
        )
    return pd.DataFrame(rows).set_index("detector")


def run(
    spec: DatasetSpec, seeds: list[int], fit_sample: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    log.info("loading %s", spec.csv)
    df = spec.load()
    prevalence = df[ANOMALY_COLUMN].mean()
    log.info(
        "%d rows x %d cols, %d anomalies (%.3f%%)",
        len(df),
        df.shape[1],
        int(df[ANOMALY_COLUMN].sum()),
        100 * prevalence,
    )

    per_seed = [evaluate(spec, df, s, fit_sample) for s in seeds]
    stack = pd.concat(per_seed, keys=range(len(seeds)))
    grouped = stack.groupby(level=1, sort=False)
    return grouped.mean(), grouped.std().fillna(0.0)


def to_markdown(mean: pd.DataFrame, std: pd.DataFrame) -> str:
    lines = [
        "| detector | " + " | ".join(METRIC_COLUMNS) + " |",
        "| --- | " + " | ".join("---" for _ in METRIC_COLUMNS) + " |",
    ]
    for name in mean.index:
        cells = [f"{mean.loc[name, c]:.3f} ± {std.loc[name, c]:.3f}" for c in METRIC_COLUMNS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="credit_card")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(config.BENCHMARK_SEEDS))
    parser.add_argument(
        "--fit-sample",
        type=int,
        default=None,
        help="cap the train set at N rows before fitting (bounds quadratic models)",
    )
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)

    spec = DATASETS[args.dataset]
    log.info("dataset %s: %s", spec.name, spec.note)
    mean, std = run(spec, args.seeds, args.fit_sample)

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    mean.join(std, lsuffix="_mean", rsuffix="_std").to_csv(
        config.RESULTS_DIR / f"benchmark_{spec.name}_{stamp}.csv"
    )
    header = f"{spec.name}, {len(args.seeds)} seeds, mean ± std on the 15% test split.\n\n"
    md = header + to_markdown(mean, std)
    (config.RESULTS_DIR / f"benchmark_{spec.name}_{stamp}.md").write_text(md)

    print("\n" + md)
    log.info("saved -> experiments/results/benchmark_%s_%s.csv", spec.name, stamp)


if __name__ == "__main__":
    main()
