"""Fixed deployment thresholds under score-distribution shift (T170; exploratory).

A detector is fitted once per problem and seed and its alert threshold is the ``1 - budget``
quantile of its training scores, as in ``alert_budget``. The threshold is then kept fixed while the
evaluated scores are changed in controlled ways. Each scenario is a different kind of change:

- ``location`` and ``scale``: affine changes of the held-out scores only (ranking unchanged);
- ``noise``: Gaussian noise added to the held-out scores only (ranking degraded);
- ``monotone_both``: a strictly increasing transform applied to both the training and the held-out
  scores, so that calibration and evaluation shift together (the alerts must not change);
- ``feature_shift``: the held-out features are moved by ``delta`` training standard deviations and
  rescored by the fitted model (a population drift, ranking and scale both change).

Shifts are in units of the standard deviation of the training scores. Labels only score the alerts;
they never enter a threshold. Synthetic shifts do not represent real deployment drift.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import ks_2samp  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labelled_benchmark as lb  # noqa: E402
import normalise as nm  # noqa: E402
from alert_budget import FIXED_BUILD, budget_threshold, build, fit_scores  # noqa: E402
from deep_support import capped  # noqa: E402
from source_clustered import bootstrap, holm, source_id  # noqa: E402

from etl_benchmark import config  # noqa: E402

BUDGETS = (0.01, 0.02, 0.05)
METHODS = ("isolation_forest", "ecod", "hbos", "pca", "copod")
SCENARIOS = (
    ("baseline", 0.0), ("location", -1.0), ("location", -0.5), ("location", 0.5), ("location", 1.0),
    ("scale", 0.5), ("scale", 2.0), ("noise", 0.5), ("noise", 1.0), ("monotone_both", 0.0),
    ("feature_shift", 0.25), ("feature_shift", 0.5), ("feature_shift", 1.0),
)  # fmt: skip
NOISE_SEED = 7


def transform(kind: str, param: float, fit: np.ndarray, scores: np.ndarray, seed: int):
    """Changed (fit, evaluated) scores for the score-level scenarios."""
    sigma = float(np.std(fit)) or 1.0
    if kind == "baseline":
        return fit, scores
    if kind == "location":
        return fit, scores + param * sigma
    if kind == "scale":
        centre = float(np.median(fit))
        return fit, centre + param * (scores - centre)
    if kind == "noise":
        rng = np.random.default_rng([NOISE_SEED, seed])
        return fit, scores + param * sigma * rng.standard_normal(len(scores))
    if kind == "monotone_both":
        return np.arcsinh(fit), np.arcsinh(scores)
    raise ValueError(f"unknown score scenario: {kind}")


def outcome(fit: np.ndarray, scores: np.ndarray, y: np.ndarray, budget: float) -> dict[str, float]:
    """Alerts of the training-score threshold on ``scores`` and their label-based quality."""
    info = budget_threshold(fit, budget)
    flags = scores > info["threshold"]
    positives = int((y == 1).sum())
    tp = int((flags & (y == 1)).sum())
    return {
        "alert_rate": float(flags.mean()),
        "alert_over_budget": float(flags.mean()) / budget,
        "precision": tp / int(flags.sum()) if flags.sum() else 0.0,
        "recall": tp / positives,
        "flagged": int(flags.sum()),
        "ks_fit_vs_eval": float(ks_2samp(fit, scores).statistic),
    }


def quality(y: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y, scores)),
        "ap": float(average_precision_score(y, scores)),
    }


def run_method(method, train, test, y, seed) -> dict[str, Any]:
    detector = build(method, FIXED_BUILD, seed)
    fit_rows = capped(train, method, seed)
    detector.fit(fit_rows)
    fit = fit_scores(detector, fit_rows)
    scores = np.asarray(detector.score(test), dtype=float)
    out: dict[str, Any] = {"seed": seed, "scenarios": {}}
    for kind, param in SCENARIOS:
        if kind == "feature_shift":
            moved = test + param  # training features are standardized: one unit is one sigma
            eval_scores = np.asarray(detector.score(moved), dtype=float)
            f, s = fit, eval_scores
        else:
            f, s = transform(kind, param, fit, scores, seed)
        record = quality(y, s) | {str(b): outcome(f, s, y, b) for b in BUDGETS}
        out["scenarios"][f"{kind}:{param:g}"] = record
    return out


def run_problem(x, y, seeds=config.BENCHMARK_SEEDS, methods=METHODS) -> dict[str, Any]:
    runs: dict[str, list] = {}
    errors: dict[str, list] = {}
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
                runs.setdefault(method, []).append(
                    run_method(method, train, test, part["y_test"], seed)
                )
            except Exception as error:  # recorded, never dropped silently
                errors.setdefault(method, []).append({"seed": seed, "error": repr(error)})
    return {"seeds": list(seeds), "runs": runs, "errors": errors, "skipped": sorted(skipped)}


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    try:
        if job["source"] == "adbench":
            x, y, report = lb.load_adbench(job["name"], Path(job["path"]))
        else:
            x, y, report = lb.load_uci(job["meta"], Path(job["path"]))
        result = run_problem(x, y)
    except Exception as error:
        return {"problem": job["problem"], "failed": repr(error)}
    return {"problem": job["problem"], "rows": int(len(y)), "prevalence": float(y.mean()), **result}


VOLUME_BAND = (0.5, 2.0)  # alert rate within half to twice the budget
KS_LIMIT = 0.25  # largest tolerated Kolmogorov-Smirnov distance between fit and evaluated scores
AUC_DROP = 0.05  # ranking deterioration: ROC-AUC falls by at least this much
PRECISION_FLOOR = 0.5  # precision collapse: below this share of the baseline precision


def _fits(runs):
    for run in runs:
        for method, seeds in run["runs"].items():
            for seed_run in seeds:
                yield run["problem"], method, seed_run["scenarios"]


def _metric(cell: dict[str, Any], budget: str, name: str) -> float:
    return cell[name] if name == "roc_auc" else cell[budget][name]


SUMMARY_METRICS = ("alert_over_budget", "precision", "recall", "ks_fit_vs_eval", "roc_auc")


def summarize(runs: list[dict[str, Any]], budgets: tuple[float, ...] = BUDGETS) -> dict[str, Any]:
    """Median over problems of the seed-mean metric, by method (and pooled), scenario, budget."""
    table: dict[str, Any] = {}
    methods = sorted({m for r in runs for m in r["runs"]})
    for method in [*methods, "all"]:
        use = methods if method == "all" else [method]
        for kind, param in SCENARIOS:
            key = f"{kind}:{param:g}"
            for budget in map(str, budgets):
                per_problem = []
                for run in runs:
                    cells = [s["scenarios"][key] for m in use for s in run["runs"].get(m, [])]
                    if cells:
                        per_problem.append(
                            {
                                n: float(np.mean([_metric(c, budget, n) for c in cells]))
                                for n in SUMMARY_METRICS
                            }
                        )
                if per_problem:
                    table.setdefault(method, {}).setdefault(key, {})[budget] = {
                        "problems": len(per_problem),
                        **{
                            f"median_{n}": float(np.median([p[n] for p in per_problem]))
                            for n in SUMMARY_METRICS
                        },
                    }
    return table


def _share(rows: list[dict[str, bool]], name: str) -> float | None:
    return float(np.mean([r[name] for r in rows])) if rows else None


def monitor_table(runs: list[dict[str, Any]], budget: float = 0.02) -> dict[str, Any]:
    """How often label-free signals fire, against what actually deteriorated, per scenario.

    Every fit of every problem, method and seed counts once. The limits are fixed conventions
    (``VOLUME_BAND``, ``KS_LIMIT``), not values tuned on these results.
    """
    key = str(budget)
    table: dict[str, Any] = {}
    for scenario in (f"{k}:{p:g}" for k, p in SCENARIOS):
        rows = []
        for _, _, sc in _fits(runs):
            base, now = sc["baseline:0"], sc[scenario]
            ratio = now[key]["alert_over_budget"]
            rows.append(
                {
                    "volume": not VOLUME_BAND[0] <= ratio <= VOLUME_BAND[1],
                    "ks": now[key]["ks_fit_vs_eval"] > KS_LIMIT,
                    "ranking": base["roc_auc"] - now["roc_auc"] >= AUC_DROP,
                    "precision": base[key]["precision"] > 0
                    and now[key]["precision"] < PRECISION_FLOOR * base[key]["precision"],
                }
            )
        if not rows:
            continue
        bad = [r for r in rows if r["ranking"] or r["precision"]]
        table[scenario] = {
            "fits": len(rows),
            "volume_trigger": _share(rows, "volume"),
            "ks_trigger": _share(rows, "ks"),
            "ranking_deterioration": _share(rows, "ranking"),
            "precision_collapse": _share(rows, "precision"),
            "deteriorated_fits": len(bad),
            "volume_trigger_given_deteriorated": _share(bad, "volume"),
            "ks_trigger_given_deteriorated": _share(bad, "ks"),
        }
    return table


CONTRAST_METRICS = ("alert_over_budget", "precision", "recall", "roc_auc")
MIN_SOURCES = 10  # fewer independent sources than this give no interval
DRAWS = 10_000


def contrasts(
    runs: list[dict[str, Any]], budget: float = 0.02, draws: int = DRAWS
) -> dict[str, Any]:
    """Each scenario minus the unshifted baseline, with source-resampled uncertainty.

    The independent unit is the original source: problems derived from one table are one cluster
    (``source_clustered.source_id``). Within a problem the fits of all detectors and seeds are
    averaged first, because they share the data; the difference is taken inside each problem, so the
    comparison stays paired. Holm adjusts over all scenario-metric contrasts. Fewer than
    ``MIN_SOURCES`` sources give no interval.
    """
    key = str(budget)
    per_problem: dict[str, dict[str, dict[str, float]]] = {}
    for run in runs:
        cells = [s["scenarios"] for seeds in run["runs"].values() for s in seeds]
        if not cells:
            continue
        per_problem[run["problem"]] = {
            scenario: {
                m: float(
                    np.mean(
                        [c[scenario][m] if m == "roc_auc" else c[scenario][key][m] for c in cells]
                    )
                )
                for m in CONTRAST_METRICS
            }
            for scenario in cells[0]
        }
    problems = sorted(per_problem)
    clusters = np.array([source_id(p) for p in problems])
    sources, counts = np.unique(clusters, return_counts=True)
    out: dict[str, Any] = {
        "budget": budget, "problems": len(problems), "sources": int(len(sources)),
        "singleton_sources": int((counts == 1).sum()), "draws": draws, "contrasts": [],
    }  # fmt: skip
    if len(sources) < MIN_SOURCES:
        out["insufficient"] = f"fewer than {MIN_SOURCES} independent sources"
        return out
    for kind, param in SCENARIOS:
        name = f"{kind}:{param:g}"
        if name == "baseline:0":
            continue
        for metric in CONTRAST_METRICS:
            diff = np.array(
                [
                    per_problem[p][name][metric] - per_problem[p]["baseline:0"][metric]
                    for p in problems
                ]
            )
            out["contrasts"].append(
                {"scenario": name, "metric": metric}
                | bootstrap(diff, clusters, by_cluster=True, draws=draws)
            )
    adjusted = holm([c["p_two_sided"] for c in out["contrasts"]])
    for item, value in zip(out["contrasts"], adjusted, strict=True):
        item["holm_p"] = value
    return out


TEST_SHARE = 0.15  # the held-out share of the rows in the archived 70/15/15 split
ALERT_BINS = (5.0, 30.0)  # expected alerts in the window: few, some, enough


def volume_false_alarms(runs: list[dict[str, Any]], budget: float = 0.02) -> dict[str, Any]:
    """Share of unshifted fits whose alert rate leaves ``VOLUME_BAND``, by expected alerts.

    The expected number of alerts in the held-out window is ``rows * TEST_SHARE * budget``: a rate
    measured on a handful of alerts moves by chance alone, so the band is only meaningful with
    enough of them.
    """
    groups: dict[str, list[bool]] = {"fewer": [], "between": [], "enough": []}
    for run in runs:
        expected = run["rows"] * TEST_SHARE * budget
        name = (
            "fewer"
            if expected < ALERT_BINS[0]
            else "between"
            if expected < ALERT_BINS[1]
            else "enough"
        )
        for seed_runs in run["runs"].values():
            for seed_run in seed_runs:
                ratio = seed_run["scenarios"]["baseline:0"][str(budget)]["alert_over_budget"]
                groups[name].append(not VOLUME_BAND[0] <= ratio <= VOLUME_BAND[1])
    return {
        name: {"fits": len(v), "false_alarm": float(np.mean(v)) if v else None}
        for name, v in groups.items()
    }


def load(folder: Path) -> list[dict[str, Any]]:
    return [
        run
        for run in (json.loads(p.read_text()) for p in sorted(folder.glob("*.json")))
        if "failed" not in run
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent
    parser.add_argument(
        "--registry", type=Path, default=root / "verification/evidence/dataset_registry"
    )
    parser.add_argument("--adbench", type=Path, default=root / "data" / "adbench")
    parser.add_argument("--pool", type=Path, default=root / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--summarize", type=Path, help="summarize this run folder instead of running"
    )
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    if args.summarize:
        runs = load(args.summarize)
        document = {
            "problems": len(runs),
            "summary": summarize(runs),
            "monitors": monitor_table(runs),
            "volume_false_alarms": volume_false_alarms(runs),
            "contrasts": contrasts(runs),
        }
        args.output.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
        return 0

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
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(run_job, todo):
            with atomic_path(
                args.output / f"{result['problem'].replace(':', '_')}.json"
            ) as partial:
                partial.write_text(json.dumps(result, sort_keys=True) + "\n")
            print(result["problem"], result.get("failed", "ok"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
