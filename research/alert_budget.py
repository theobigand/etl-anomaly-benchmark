"""Fixed alert budgets, label-free (T163, T164; thesis-remediation/ALERT_BUDGETS_2026-11-11.md).

An alert budget is a nominal share of the training rows a detector may flag. The threshold is the
``1 - budget`` quantile of the detector's scores on the unlabelled fit rows. It never reads a test
label, a test score, or the training prevalence: the detector is built with a constant
contamination, and the labels only score the flags afterwards. The nominal budget (a property of
the training scores), the realized fit rate (differs from it under ties) and the realized alert
rate on the held-out rows (differs from it under drift) are three different numbers and are all
kept. Rules have no score to threshold: their own decision is reported as a separate, untuned
reference and is never part of a budget comparison.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from functools import partial as bind
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labelled_benchmark as lb  # noqa: E402
import normalise as nm  # noqa: E402
from deep_support import build, capped  # noqa: E402
from pool_full import KNOWN, fit_scores  # noqa: E402,F401

from etl_benchmark import config  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES, DETECTOR_NAMES  # noqa: E402

BUDGETS = (0.005, 0.01, 0.02, 0.05, 0.10)
FIXED_BUILD = 0.02  # constant contamination used only to construct the detector; no label is read
SELECT = ("precision", "recall", "f1", "fpr", "test_alert_rate", "fit_alert_rate")


def budget_threshold(fit: np.ndarray, budget: float) -> dict[str, Any]:
    """The ``1 - budget`` quantile of the unlabelled training scores and what it realizes there."""
    if not isinstance(budget, int | float) or not 0.0 < budget < 0.5 or math.isnan(budget):
        raise ValueError("budget must be a share in (0, 0.5)")
    fit = np.asarray(fit, dtype=float)
    if fit.ndim != 1 or len(fit) < math.ceil(1 / budget) or not np.isfinite(fit).all():
        raise ValueError("training scores must be finite and at least 1/budget in number")
    threshold = float(np.percentile(fit, 100 * (1 - budget)))
    return {
        "nominal": float(budget),
        "threshold": threshold,
        "fit_alert_rate": float(np.mean(fit > threshold)),
        "ties_at_threshold": int(np.sum(fit == threshold)),
    }


def flags_for(fit: np.ndarray, scores: np.ndarray, budget: float) -> np.ndarray:
    """Flags raised on ``scores`` (higher is more anomalous) by the training-score threshold."""
    scores = np.asarray(scores, dtype=float)
    if not np.isfinite(scores).all():
        raise ValueError("test scores must be finite")
    return scores > budget_threshold(fit, budget)["threshold"]


def _counts(y: np.ndarray, flags: np.ndarray) -> dict[str, Any]:
    tp = int(np.sum(flags & (y == 1)))
    fp = int(np.sum(flags & (y == 0)))
    fn = int(np.sum(~flags & (y == 1)))
    tn = int(np.sum(~flags & (y == 0)))
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn),
        "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0,
        "fpr": fp / (fp + tn),
        "test_alert_rate": (tp + fp) / len(y),
    }  # fmt: skip


def run_method(
    method: str, train: pd.DataFrame, test: pd.DataFrame, y: np.ndarray, seed: int
) -> dict[str, Any]:
    detector = build(method, FIXED_BUILD, seed)
    fit = capped(train, method, seed)
    result = detect(test, detector, fit_df=fit)
    scores = result.scores.to_numpy(dtype=float)
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("a held-out evaluation needs both classes")
    row: dict[str, Any] = {"seed": seed, "fit_rows": int(len(fit)), "test_rows": int(len(y))}
    kept = fit_scores(detector, fit)
    if kept is None:
        row["rule"] = _counts(y, result.flags.to_numpy(dtype=bool))
        return row
    row["roc_auc"] = float(roc_auc_score(y, scores))
    row["pr_auc"] = float(average_precision_score(y, scores))
    row["budgets"] = {}
    for budget in BUDGETS:
        info = budget_threshold(kept, budget)
        cell = _counts(y, scores > info["threshold"])
        row["budgets"][str(budget)] = {**info, **cell}
    return row


def run_problem(
    x: np.ndarray,
    y: np.ndarray,
    seeds: tuple[int, ...] = config.BENCHMARK_SEEDS,
    methods: list[str] | None = None,
) -> dict[str, Any]:
    methods = methods or list(DETECTOR_NAMES)
    unknown = [m for m in methods if m not in KNOWN]
    if unknown:
        raise ValueError(f"unknown detector names: {unknown}")
    runs: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, list[dict[str, Any]]] = {}
    skipped: set[str] = set()
    for seed in seeds:
        part = nm.split(x, y, seed)
        names = [f"f{i}" for i in range(x.shape[1])]
        train = pd.DataFrame(part["x_train"], columns=names)
        test = pd.DataFrame(part["x_test"], columns=names)
        skip = nm.skipped_detectors(len(train))
        skipped |= {m for m in methods if m in skip}
        for method in methods:
            if method in skip:
                continue
            try:
                row = run_method(method, train, test, part["y_test"], seed)
            except Exception as error:  # a failing model is recorded, not hidden
                errors.setdefault(method, []).append({"seed": seed, "error": repr(error)})
                continue
            runs.setdefault(method, []).append(row)
    return {"seeds": list(seeds), "runs": runs, "skipped": sorted(skipped), "errors": errors}


def run_job(job: dict[str, Any], methods: list[str] | None = None) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    try:
        if job["source"] == "adbench":
            x, y, report = lb.load_adbench(job["name"], Path(job["path"]))
        else:
            x, y, report = lb.load_uci(job["meta"], Path(job["path"]))
        result = run_problem(x, y, methods=methods)
    except Exception as error:  # recorded, never dropped silently
        return {"problem": job["problem"], "source": job["source"], "failed": repr(error)}
    return {
        "problem": job["problem"], "source": job["source"], "name": report["name"],
        "prevalence": float(y.mean()), "rows": int(len(y)), "features": int(x.shape[1]),
        **result,
    }  # fmt: skip


def accounting(runs: list[dict[str, Any]]) -> dict[str, int]:
    """Exact denominators: problems read, failed seed runs, skipped (problem, detector) pairs."""
    return {
        "problems": len(runs),
        "failed_runs": sum(len(e) for r in runs for e in r["errors"].values()),
        "skipped_detectors": sum(len(r["skipped"]) for r in runs),
    }


def summarize(
    runs: list[dict[str, Any]], budgets: tuple[float, ...] = BUDGETS
) -> dict[str, dict[str, dict[str, float]]]:
    """Seed-mean per problem, then the median over the problems that evaluated the detector."""
    table: dict[str, dict[str, dict[str, float]]] = {}
    methods = sorted({m for r in runs for m, seeds in r["runs"].items() if seeds})
    for method in methods:
        for budget in budgets:
            key = str(budget)
            per: dict[str, list[float]] = {name: [] for name in (*SELECT, "ratio")}
            seed_runs = 0
            for run in runs:
                seeds = [s for s in run["runs"].get(method, []) if "budgets" in s]
                if not seeds:
                    continue
                seed_runs += len(seeds)
                for name in SELECT:
                    per[name].append(float(np.mean([s["budgets"][key][name] for s in seeds])))
                per["ratio"].append(per["test_alert_rate"][-1] / budget)
            if not per["recall"]:
                continue
            table.setdefault(method, {})[key] = {
                "problems": len(per["recall"]), "seed_runs": seed_runs,
                **{f"median_{n}": float(np.median(v)) for n, v in per.items() if n != "ratio"},
                "median_realized_over_nominal": float(np.median(per["ratio"])),
            }  # fmt: skip
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent
    registry = root / "verification" / "evidence" / "dataset_registry"
    parser.add_argument("--registry", type=Path, default=registry)
    parser.add_argument("--adbench", type=Path, default=root / "data" / "adbench")
    parser.add_argument("--pool", type=Path, default=root / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", nargs="*", help="problem ids, for a quick check")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--methods", choices=("classical", "deep"), default="classical")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    todo = [
        j
        for j in lb.jobs(args.registry, args.adbench, args.pool)
        if not args.only or j["problem"] in args.only
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    if args.resume:
        todo = [
            j for j in todo if not (args.output / f"{j['problem'].replace(':', '_')}.json").exists()
        ]
    methods = list(DEEP_NAMES) if args.methods == "deep" else list(DETECTOR_NAMES)
    failed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(bind(run_job, methods=methods), todo):
            failed += "failed" in result
            stem = result["problem"].replace(":", "_")
            with atomic_path(args.output / f"{stem}.json") as partial:
                partial.write_text(json.dumps(result, sort_keys=True) + "\n")
            print(result["problem"], result.get("failed", "ok"), flush=True)
    print(f"{len(todo)} problems, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
