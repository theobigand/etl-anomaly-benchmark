"""One pass over the labelled pool for every threshold-dependent table (pool_extension.md).

For each problem, seed and detector one fit gives: the metrics at the training-prevalence
threshold, the metrics at the label-free threshold of 0.02, the metrics of the contamination grid
of the sweep, the stage times and, for the seed of the curves, the precision-recall curve. The
thresholds other than the fitted one are read from the scores kept at fit: the flag threshold of a
detector is the ``1 - contamination`` quantile of its fit scores and does not change the model. A
test checks this equivalence against a refit for every detector of the registry.
"""

from __future__ import annotations

import argparse
import json
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
from sklearn.metrics import average_precision_score, precision_recall_curve  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labelled_benchmark as lb  # noqa: E402
import normalise as nm  # noqa: E402
from deep_support import build, capped  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.metrics import compute_metrics  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES, DETECTOR_NAMES, clip_contamination  # noqa: E402

FIXED = 0.02
GRID = (0.001, 0.01, 0.05, 0.10, 0.20)
CURVE_SEED = 42
CURVE_POINTS = 200
SWEEP_METHOD = "isolation_forest"
KNOWN = [*DETECTOR_NAMES, *DEEP_NAMES]


def fit_scores(detector: Any, fit_df: pd.DataFrame) -> np.ndarray | None:
    """The scores whose quantile is the flag threshold; ``None`` when contamination is not used."""
    model = getattr(detector, "_model", None)
    if model is None:
        return None
    scores = getattr(model, "decision_scores_", None)
    if scores is None:  # the project's own estimators threshold the scores of the fit rows
        scores = detector.score(fit_df)
    return np.asarray(scores, dtype=float)


def flags_at(fit_score: np.ndarray, test_scores: np.ndarray, contamination: float) -> np.ndarray:
    """Flags a detector fitted with this contamination would raise (PyOD's threshold rule)."""
    threshold = np.percentile(fit_score, 100 * (1 - clip_contamination(contamination)))
    return np.asarray(test_scores) > threshold


def _curve(y: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    precision, recall, _ = precision_recall_curve(y, scores)
    keep = np.unique(
        np.linspace(0, len(precision) - 1, min(CURVE_POINTS, len(precision))).astype(int)
    )
    return {
        "precision": precision[keep].tolist(),
        "recall": recall[keep].tolist(),
        "average_precision": float(average_precision_score(y, scores)),
    }


def run_method(
    method: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    y: np.ndarray,
    seed: int,
    prevalence: float,
) -> dict[str, Any]:
    detector = build(method, clip_contamination(prevalence), seed)
    fit = capped(train, method, seed)
    result = detect(test, detector, fit_df=fit)
    scores = result.scores.to_numpy()
    flags = result.flags.to_numpy()
    row: dict[str, Any] = {
        "seed": seed,
        "metrics": compute_metrics(y, flags, scores),
        "fit_s": result.fit_s,
        "predict_s": result.predict_s,
        "score_s": result.score_s,
        "fit_rows": int(len(fit)),
    }
    kept = fit_scores(detector, fit)
    if kept is None:
        row["fixed"] = row["metrics"]  # a rule does not read the contamination
        row["fixed_is_same"] = True
    else:
        row["fixed"] = compute_metrics(y, flags_at(kept, scores, FIXED), scores)
        if method == SWEEP_METHOD:
            row["sweep"] = {
                str(c): compute_metrics(y, flags_at(kept, scores, c), scores) for c in GRID
            }
    if seed == CURVE_SEED:
        row["curve"] = _curve(y, scores)
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
    skipped: list[str] = []
    for seed in seeds:
        part = nm.split(x, y, seed)
        names = [f"f{i}" for i in range(x.shape[1])]
        train = pd.DataFrame(part["x_train"], columns=names)
        test = pd.DataFrame(part["x_test"], columns=names)
        prevalence = float(part["y_train"].mean())
        skip = nm.skipped_detectors(len(train))
        skipped = [m for m in methods if m in skip]
        for method in methods:
            if method in skip:
                continue
            try:
                row = run_method(method, train, test, part["y_test"], seed, prevalence)
            except Exception as error:  # a failing model is recorded, not hidden
                errors.setdefault(method, []).append({"seed": seed, "error": repr(error)})
                continue
            runs.setdefault(method, []).append(row)
    return {"seeds": list(seeds), "runs": runs, "skipped": skipped, "errors": errors}


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
        "problem": job["problem"],
        "source": job["source"],
        "name": report["name"],
        "prevalence": float(y.mean()),
        "rows": int(len(y)),
        "features": int(x.shape[1]),
        **result,
    }


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
    parser.add_argument("--resume", action="store_true", help="skip the problems already written")
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
