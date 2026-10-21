"""Autoencoder and LSTM autoencoder rows for the per-type matrix (issue #64).

Protocol: verification/deep_typed.md. Needs the environment of research/requirements-lstm.txt.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT / "experiments")]

import run_synthetic_benchmark as rsb  # noqa: E402
from lstm_detector import LSTMAutoencoder  # noqa: E402

from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality.autoencoder import AutoencoderDetector  # noqa: E402
from etl_benchmark.synthetic import (  # noqa: E402
    ANOMALY_TYPES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    make_synthetic,
)

SEEDS = (42, 1, 2, 3, 4)
MAX_EPOCHS, PATIENCE = 300, 5
ROW_LEVEL = ("zscore", "iqr", "great_expectations", "isolation_forest", "lof", "ocsvm")


def _with_time(part: pd.DataFrame) -> pd.DataFrame:
    """Order key for the windows: the signup date, an unreadable date goes first in its partition."""
    dates = pd.to_datetime(part["signup_date"], errors="coerce", utc=True, format="mixed")
    out = part.copy()
    out["t"] = dates.fillna(dates.min())
    return out


def _frame(recall: pd.DataFrame) -> dict[str, Any]:
    return json.loads(recall.to_json(orient="split"))


def run_seed(seed: int, rows: int | None = None, max_epochs: int = MAX_EPOCHS) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    kw = {"n_rows": rows} if rows else {}
    df = make_synthetic(seed=seed, **kw)
    base = rsb.evaluate(df, seed)
    train, val, test = (_with_time(p) for p in rsb._split_synthetic(df, seed))
    contamination = float(train["anomaly"].mean())
    recall, precision = base["recall"].copy(), base["precision"].copy()
    deep: dict[str, Any] = {}

    def add(name: str, flags: np.ndarray, settings: dict[str, Any], seconds: float) -> None:
        series = pd.Series(np.asarray(flags, dtype=bool), index=test.index)
        r, p = rsb._per_type(series, test["anomaly_type"])
        recall.loc[name] = pd.Series(r)
        precision.loc[name] = pd.Series(p)
        clean = test["anomaly_type"] == "clean"
        deep[name] = {"fpr": float(series[clean].mean()), "settings": settings, "seconds": seconds}

    started = time.perf_counter()
    ae = AutoencoderDetector(contamination=contamination, random_state=seed)
    result = detect(test[FEATURE_COLUMNS], ae, fit_df=train[FEATURE_COLUMNS])
    add("autoencoder", result.flags.to_numpy(), ae.settings(), time.perf_counter() - started)

    started = time.perf_counter()
    lstm = LSTMAutoencoder(
        NUMERIC_FEATURES,
        "t",
        max_epochs=max_epochs,
        patience=PATIENCE,
        fit_rows=len(train),
        validation_rows=len(val),
        seed=seed,
    ).fit(train, val, contamination)
    add(
        "lstm_autoencoder",
        lstm.flags(test).to_numpy(),
        lstm.settings(),
        time.perf_counter() - started,
    )
    return {
        "seed": seed,
        "rows": {"train": len(train), "validation": len(val), "test": len(test)},
        "recall": _frame(recall[ANOMALY_TYPES]),
        "precision": _frame(precision[ANOMALY_TYPES]),
        "deep": deep,
    }


def mean_std(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    stack = pd.concat(frames, keys=range(len(frames)))
    grouped = stack.groupby(level=1, sort=False)
    return grouped.mean(), grouped.std()


def hypotheses(frames: list[pd.DataFrame], deep: list[dict[str, Any]]) -> dict[str, Any]:
    mean, _ = mean_std(frames)
    rows = [m for m in ROW_LEVEL + ("autoencoder",) if m in mean.index]
    drift = mean.loc["lstm_autoencoder", "temporal_drift"]
    best_row = mean.loc[rows, "temporal_drift"]
    out: dict[str, Any] = {
        "H1": {
            "supported": bool((drift - best_row >= 0.10).all()),
            "lstm_drift_recall": float(drift),
            "best_row_level": {"method": best_row.idxmax(), "recall": float(best_row.max())},
        }
    }
    structural = ("missing_value", "duplicate", "invalid_format")
    gap = {t: float(mean.loc["lstm_autoencoder", t] - mean.loc[rows, t].max()) for t in structural}
    out["H2"] = {"supported": bool(all(g <= 0.05 for g in gap.values())), "gap_to_best_row": gap}
    converged = {
        name: sum(bool(d[name]["settings"]["converged"]) for d in deep)
        for name in ("autoencoder", "lstm_autoencoder")
    }
    out["H3"] = {"supported": bool(all(n >= 4 for n in converged.values())), "converged": converged}
    t = "multivariate_outlier"
    ae = mean.loc["autoencoder", t]
    out["H4"] = {
        "supported": bool(
            ae >= max(mean.loc["zscore", t], mean.loc["iqr", t])
            and ae - mean.loc["isolation_forest", t] <= 0.05
        ),
        "recall": {
            m: float(mean.loc[m, t]) for m in ("autoencoder", "zscore", "iqr", "isolation_forest")
        },
    }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-epochs", type=int, default=MAX_EPOCHS)
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    args.output.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in SEEDS:
        run = run_seed(seed, max_epochs=args.max_epochs)
        runs.append(run)
        with atomic_path(args.output / f"seed_{seed}.json") as partial:
            partial.write_text(json.dumps(run, indent=1, sort_keys=True) + "\n")
        print("seed", seed, flush=True)
    frames = [
        pd.DataFrame(r["recall"]["data"], r["recall"]["index"], r["recall"]["columns"])
        for r in runs
    ]
    mean, std = mean_std(frames)
    results = {
        "mean": json.loads(mean.to_json(orient="split")),
        "std": json.loads(std.to_json(orient="split")),
        "hypotheses": hypotheses(frames, [r["deep"] for r in runs]),
    }
    with atomic_path(args.output / "deep_typed_results.json") as partial:
        partial.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    lines = ["| method | " + " | ".join(mean.columns) + " |", "|---|" + "---|" * len(mean.columns)]
    for method in mean.index:
        cells = [f"{mean.loc[method, c]:.2f} ± {std.loc[method, c]:.2f}" for c in mean.columns]
        lines.append(f"| {method} | " + " | ".join(cells) + " |")
    with atomic_path(args.output / "deep_typed_results.md") as partial:
        partial.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
