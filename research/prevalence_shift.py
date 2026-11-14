"""Fixed deployment thresholds under a change of anomaly prevalence (T169; exploratory).

The model and its training-score threshold are kept as they are; no threshold is recalibrated. From
the held-out confusion counts of an alert-budget cell, the true-positive rate and the false-positive
rate of that fixed threshold are read. Under pure prior (label) shift, where the score distributions
of the normal rows and of the anomalies do not change and only their mixing proportion does, a test
set resampled to prevalence ``pi`` has, in expectation:

    alert rate = pi * TPR + (1 - pi) * FPR,   recall = TPR,   FPR = FPR,
    precision  = pi * TPR / alert rate

Test labels are therefore used to build the simulated population, never to set the threshold. This
isolates the prevalence effect: a change of the conditional score distributions (T170) is excluded
by construction, and the results say nothing about real deployment drift. The rates carry the
sampling error of the counts they come from, so the number of held-out positives and negatives is
reported.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from source_clustered import bootstrap, holm, source_id  # noqa: E402

PREVALENCES = (0.005, 0.01, 0.02, 0.05, 0.10, 0.20)
METRICS = ("alert_rate", "precision", "recall", "f1", "fpr", "alert_over_budget")
DRAWS = 10_000


def shifted(cell: dict[str, Any], prevalence: float) -> dict[str, float]:
    """Expected metrics of the fixed threshold of ``cell`` at a population with this prevalence."""
    if not 0.0 < prevalence < 1.0:
        raise ValueError("prevalence must be in (0, 1)")
    positives, negatives = cell["tp"] + cell["fn"], cell["fp"] + cell["tn"]
    if positives <= 0 or negatives <= 0:
        raise ValueError("a cell needs held-out positives and negatives")
    tpr, fpr = cell["tp"] / positives, cell["fp"] / negatives
    alert = prevalence * tpr + (1 - prevalence) * fpr
    precision = prevalence * tpr / alert if alert > 0 else 0.0
    f1 = 2 * precision * tpr / (precision + tpr) if precision + tpr > 0 else 0.0
    return {
        "alert_rate": alert, "precision": precision, "recall": tpr, "f1": f1, "fpr": fpr,
        "alert_over_budget": alert / cell["nominal"],
    }  # fmt: skip


def summarize(
    runs: list[dict[str, Any]],
    budgets: tuple[float, ...] = (0.01, 0.02, 0.05),
    prevalences: tuple[float, ...] = PREVALENCES,
    draws: int = DRAWS,
) -> dict[str, Any]:
    """Seed-mean per problem, then the median over problems with a source-resampled interval."""
    methods = sorted(
        {m for r in runs for m, seeds in r["runs"].items() if any("budgets" in s for s in seeds)}
    )
    table: dict[str, Any] = {}
    for method in methods:
        for budget in budgets:
            key = str(budget)
            usable = []
            for run in runs:
                seeds = [
                    s["budgets"][key]
                    for s in run["runs"].get(method, [])
                    if key in s.get("budgets", {}) and "infeasible" not in s["budgets"][key]
                ]
                if seeds:
                    usable.append((run["problem"], seeds))
            if not usable:
                continue
            clusters = np.array([source_id(p) for p, _ in usable])
            cells = [c for _, seeds in usable for c in seeds]
            entry: dict[str, Any] = {
                "problems": len(usable), "seed_runs": len(cells),
                "min_positives": min(c["tp"] + c["fn"] for c in cells),
                "min_negatives": min(c["fp"] + c["tn"] for c in cells),
                "by_prevalence": {},
            }  # fmt: skip
            for pi in prevalences:
                per_problem = {
                    m: np.array(
                        [np.mean([shifted(c, pi)[m] for c in seeds]) for _, seeds in usable]
                    )
                    for m in METRICS
                }
                entry["by_prevalence"][str(pi)] = {
                    m: bootstrap(v, clusters, by_cluster=True, draws=draws)
                    for m, v in per_problem.items()
                }
            table.setdefault(method, {})[key] = entry
    return {"prevalences": list(prevalences), "budgets": list(budgets), "table": table}


MIN_SOURCES = 10  # fewer independent sources than this give no interval
CONTRAST_METRICS = ("alert_over_budget", "precision")


def contrasts(
    runs: list[dict[str, Any]],
    budget: float = 0.02,
    prevalences: tuple[float, ...] = PREVALENCES,
    draws: int = DRAWS,
) -> dict[str, Any]:
    """Change of the fixed threshold's behaviour from the observed prevalence to ``pi``.

    Per problem, the metrics of the threshold at ``pi`` minus its metrics at the problem's own
    held-out prevalence (the observed cell), averaged over the fits of all detectors and seeds
    that share the data. The independent unit is the original source, resampled as a whole; a
    contrast needs at least ``MIN_SOURCES`` sources. Holm adjusts over prevalence-metric pairs.
    """
    key = str(budget)
    problems, per_problem = [], []
    for run in runs:
        cells = [
            c
            for seeds in run["runs"].values()
            for s in seeds
            if key in s.get("budgets", {}) and "infeasible" not in s["budgets"][key]
            for c in [s["budgets"][key]]
        ]
        if not cells:
            continue
        rows = {}
        for pi in prevalences:
            observed = [
                shifted(c, (c["tp"] + c["fn"]) / (c["tp"] + c["fn"] + c["fp"] + c["tn"]))
                for c in cells
            ]
            moved = [shifted(c, pi) for c in cells]
            rows[pi] = {
                m: float(np.mean([a[m] - b[m] for a, b in zip(moved, observed, strict=True)]))
                for m in CONTRAST_METRICS
            }
        problems.append(run["problem"])
        per_problem.append(rows)
    clusters = np.array([source_id(p) for p in problems])
    sources, counts = np.unique(clusters, return_counts=True)
    out: dict[str, Any] = {
        "budget": budget, "problems": len(problems), "sources": int(len(sources)),
        "singleton_sources": int((counts == 1).sum()), "draws": draws, "contrasts": [],
    }  # fmt: skip
    if len(sources) < MIN_SOURCES:
        out["insufficient"] = f"fewer than {MIN_SOURCES} independent sources"
        return out
    for pi in prevalences:
        for metric in CONTRAST_METRICS:
            values = np.array([row[pi][metric] for row in per_problem])
            out["contrasts"].append(
                {"prevalence": pi, "metric": metric}
                | bootstrap(values, clusters, by_cluster=True, draws=draws)
            )
    adjusted = holm([c["p_two_sided"] for c in out["contrasts"]])
    for item, value in zip(out["contrasts"], adjusted, strict=True):
        item["holm_p"] = value
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=DRAWS)
    args = parser.parse_args(argv)
    from matched_alert import load

    runs = load(*args.folders)
    summary = summarize(runs, draws=args.draws)
    summary["contrasts"] = {
        str(b): contrasts(runs, b, draws=args.draws) for b in (0.01, 0.02, 0.05)
    }
    args.output.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
