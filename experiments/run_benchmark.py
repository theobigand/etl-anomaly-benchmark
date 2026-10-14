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
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")

import pandas as pd  # noqa: E402
from provenance import write_record, write_split_ids  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS, DatasetSpec  # noqa: E402
from etl_benchmark.logging_setup import setup_logging  # noqa: E402
from etl_benchmark.metrics import compute_metrics  # noqa: E402
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
            **compute_metrics(y_test, res.flags, res.scores),
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
    return grouped.mean(), grouped.std()


def to_markdown(mean: pd.DataFrame, std: pd.DataFrame) -> str:
    lines = [
        "| detector | " + " | ".join(METRIC_COLUMNS) + " |",
        "| --- | " + " | ".join("---" for _ in METRIC_COLUMNS) + " |",
    ]
    for name in mean.index:
        cells = [
            f"{mean.loc[name, c]:.3f} ± "
            + ("n/a" if pd.isna(std.loc[name, c]) else f"{std.loc[name, c]:.3f}")
            for c in METRIC_COLUMNS
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="credit_card")
    parser.add_argument("--csv", type=Path, help="local CSV override for a declared dataset schema")
    parser.add_argument("--detectors", nargs="+", help="subset of this dataset's detectors")
    parser.add_argument("--results-dir", type=Path, default=config.RESULTS_DIR)
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
    if args.detectors:
        unknown = set(args.detectors) - set(spec.detector_names)
        if unknown:
            parser.error(f"detectors not eligible for {spec.name}: {sorted(unknown)}")
        spec = replace(spec, detector_names=args.detectors)
    if args.csv is not None:
        spec = replace(spec, csv=args.csv)
    if args.fit_sample is not None and args.fit_sample <= 0:
        parser.error("--fit-sample must be positive")
    log.info("dataset %s: %s", spec.name, spec.note)
    mean, std = run(spec, args.seeds, args.fit_sample)

    args.results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    csv_out = args.results_dir / f"benchmark_{spec.name}_{stamp}.csv"
    md_out = args.results_dir / f"benchmark_{spec.name}_{stamp}.md"
    mean.join(std, lsuffix="_mean", rsuffix="_std").to_csv(csv_out)
    header = f"{spec.name}, {len(args.seeds)} seeds, mean ± std on the 15% test split.\n\n"
    md = header + to_markdown(mean, std)
    md_out.write_text(md)
    split_out = args.results_dir / f"split_ids_{spec.name}_{stamp}.json.gz"
    write_split_ids(
        split_out,
        spec.load(),
        ANOMALY_COLUMN,
        args.seeds,
        config.SPLIT_RATIOS,
        fit_sample=args.fit_sample,
    )
    feature_names = list(spec.features(pd.read_csv(spec.csv, nrows=0)).columns)
    write_record(
        args.results_dir / f"run_benchmark_{spec.name}_{stamp}.json",
        experiment="real_benchmark",
        seeds=args.seeds,
        dataset=spec.name,
        data_path=spec.csv,
        settings={
            "split_ratios": list(config.SPLIT_RATIOS),
            "split_strategy": "stratified",
            "fit_sample": args.fit_sample,
            "detectors": spec.detector_names,
            "features": feature_names,
            "calibration": "train_label_prevalence",
            "pr_auc_definition": "average_precision",
        },
        outputs=[csv_out.name, md_out.name, split_out.name],
    )

    print("\n" + md)
    log.info("saved -> experiments/results/benchmark_%s_%s.csv", spec.name, stamp)


if __name__ == "__main__":
    main()
