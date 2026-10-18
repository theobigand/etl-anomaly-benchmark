"""Precision-recall curves and a contamination-sensitivity table.

Every detector emits a graded score, so a single reported operating point
hides the whole precision-recall trade-off. This script fits each
detector on the train split, takes its continuous scores on the test
split, and draws the full precision-recall curve per detector and per
dataset. It also sweeps Isolation Forest's contamination on each dataset,
to show quantitatively how much that one number moves the operating
point.

    python experiments/run_curves.py
    python experiments/run_curves.py --seed 1
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from provenance import write_record  # noqa: E402
from run_synthetic_benchmark import _split_synthetic  # noqa: E402
from sklearn.metrics import average_precision_score, precision_recall_curve  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.atomic import atomic_path  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS  # noqa: E402
from etl_benchmark.logging_setup import setup_logging  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality import IsolationForestDetector  # noqa: E402
from etl_benchmark.registry import all_detectors, clip_contamination  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402
from etl_benchmark.synthetic import FEATURE_COLUMNS, make_synthetic  # noqa: E402

log = logging.getLogger(__name__)

PAPER_FIGURE = config.PROJECT_ROOT / "paper" / "figures" / "pr_curves.png"
CONTAMINATION_GRID = [0.001, 0.01, 0.05, 0.10, 0.20]


def _split_real(name: str, seed: int):
    spec = DATASETS[name]
    df = spec.load()
    train, _val, test = stratified_split(df, ANOMALY_COLUMN, config.SPLIT_RATIOS, seed)
    return (
        spec.features(train),
        spec.features(test),
        test[ANOMALY_COLUMN].to_numpy(),
        float(train[ANOMALY_COLUMN].mean()),
        spec.detector_names,
        float(df[ANOMALY_COLUMN].mean()),
    )


def _split_synth(seed: int, rows: int | None = None):
    options = {"n_rows": rows} if rows is not None else {}
    df = make_synthetic(seed=seed, **options)
    train, _val, test = _split_synthetic(df, seed)
    y = test["anomaly"].to_numpy().astype(int)
    from etl_benchmark.registry import DETECTOR_NAMES

    return (
        train[FEATURE_COLUMNS],
        test[FEATURE_COLUMNS],
        y,
        float(train["anomaly"].mean()),
        DETECTOR_NAMES,
        float(df["anomaly"].mean()),
    )


def scores_for(dataset: str, seed: int, rows: int | None = None) -> dict:
    if dataset == "synthetic":
        train_x, test_x, y, contamination, names, base = _split_synth(seed, rows)
    else:
        train_x, test_x, y, contamination, names, base = _split_real(dataset, seed)

    out = {"y": y, "base_rate": base, "scores": {}}
    for det in all_detectors(ml_contamination=contamination, names=names):
        res = detect(test_x, det, fit_df=train_x)
        out["scores"][det.name] = np.asarray(res.scores, dtype=float)
        log.info("%s: %s scored", dataset, det.name)
    return out


def render_pr(results: dict[str, dict], path: Path) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    cmap = plt.get_cmap("tab10")
    for ax, (name, data) in zip(axes.flat, results.items(), strict=False):
        for i, (method, s) in enumerate(data["scores"].items()):
            prec, rec, _ = precision_recall_curve(data["y"], s)
            ap = average_precision_score(data["y"], s)
            ax.plot(rec, prec, linewidth=1.4, color=cmap(i % 10), label=f"{method} ({ap:.2f})")
        ax.axhline(data["base_rate"], color="0.7", linewidth=0.8, linestyle="--")
        ax.set_title(name)
        ax.set_xlabel("recall")
        ax.set_ylabel("precision")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.legend(fontsize=7, loc="upper right")
    fig.suptitle("Precision-recall curves on the test split (AP in the legend)")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(path) as partial:
        fig.savefig(partial, dpi=150)
    plt.close(fig)
    return path


def contamination_sweep(
    seed: int, datasets: list[str] | None = None, rows: int | None = None
) -> pd.DataFrame:
    from sklearn.metrics import precision_score, recall_score

    records = []
    for dataset in datasets or ["credit_card", "water_quality", "cardio", "synthetic"]:
        try:
            if dataset == "synthetic":
                train_x, test_x, y, prevalence, _n, _b = _split_synth(seed, rows)
            else:
                train_x, test_x, y, prevalence, _n, _b = _split_real(dataset, seed)
        except FileNotFoundError:
            log.warning("skipping %s (dataset not present)", dataset)
            continue
        for c in [*CONTAMINATION_GRID, prevalence]:
            det = IsolationForestDetector(contamination=clip_contamination(c))
            res = detect(test_x, det, fit_df=train_x)
            records.append(
                {
                    "dataset": dataset,
                    "contamination": round(clip_contamination(c), 4),
                    "is_prevalence": abs(c - prevalence) < 1e-9,
                    "precision": precision_score(y, res.flags, zero_division=0),
                    "recall": recall_score(y, res.flags),
                    "flagged_pct": 100.0 * float(res.flags.mean()),
                }
            )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    parser.add_argument("--figure", type=Path, default=PAPER_FIGURE)
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=[*DATASETS, "synthetic"],
        default=["credit_card", "water_quality", "cardio", "synthetic"],
    )
    parser.add_argument("--rows", type=int, help="synthetic row count for an offline smoke run")
    parser.add_argument("--results-dir", type=Path, default=config.RESULTS_DIR)
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    results: dict[str, dict] = {}
    for dataset in args.datasets:
        try:
            results[dataset] = scores_for(dataset, args.seed, args.rows)
        except FileNotFoundError:
            log.warning("skipping %s (dataset not present)", dataset)

    if not results:
        raise RuntimeError("no datasets available for curve evaluation")

    figure = render_pr(results, args.figure)
    sweep = contamination_sweep(args.seed, args.datasets, args.rows)

    args.results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    csv_out = args.results_dir / f"contamination_sweep_{stamp}.csv"
    with atomic_path(csv_out) as partial:
        sweep.to_csv(partial, index=False)
    write_record(
        args.results_dir / f"run_curves_{stamp}.json",
        experiment="precision_recall_and_contamination",
        seeds=[args.seed],
        dataset=",".join(args.datasets),
        data_path=None,
        settings={
            "datasets": args.datasets,
            "skipped_datasets": [name for name in args.datasets if name not in results],
            "synthetic_rows": args.rows,
            "split_ratios": list(config.SPLIT_RATIOS),
            "synthetic_split_strategy": "customer_identity_grouped_stratified",
            "real_split_strategy": "stratified",
            "calibration": "train_label_prevalence",
            "contamination_grid": CONTAMINATION_GRID,
            "pr_auc_definition": "average_precision",
        },
        outputs=[csv_out.name, str(figure)],
    )

    print("\nIsolation Forest, contamination sweep (test split):\n")
    print(sweep.to_string(index=False))
    log.info("figure -> %s", figure)


if __name__ == "__main__":
    main()
