"""Rules against learned detectors at comparable alert volume (T167; exploratory).

A rule has no score to threshold, so it keeps its own decision contract and its own alert volume.
For each rule, learned detector, problem and seed, the budget cell whose realized held-out alert
rate is closest (in ratio) to the rule's is taken from the archived alert-budget cells, and the pair
is kept only if the two alert rates differ by less than ``TOLERANCE``. The learned thresholds stay
training-calibrated; only the choice of which budget cell to compare uses the realized alert rates
(never a label). The matching is therefore an evaluation-time construct, not a deployment
procedure, and an exact match is not claimed. Differences (learned minus rule) are averaged over
the eligible seeds of a problem, then compared with a bootstrap that resamples original sources.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from source_clustered import bootstrap, holm, source_id  # noqa: E402

RULES = ("zscore", "iqr", "great_expectations")
TOLERANCE = 1.5  # the larger alert rate may be at most this many times the smaller one
MIN_SEEDS = 3  # eligible seeds a problem needs to enter a comparison
METRICS = ("precision", "recall")
DRAWS = 10_000


def match_cell(budgets: dict[str, Any], rule_rate: float) -> tuple[str, float] | None:
    """The feasible budget cell closest to ``rule_rate`` and its ratio, or None beyond tolerance."""
    if not rule_rate > 0:
        return None
    best: tuple[float, str, float] | None = None
    for key, cell in budgets.items():
        if "infeasible" in cell or not cell["test_alert_rate"] > 0:
            continue
        ratio = cell["test_alert_rate"] / rule_rate
        distance = abs(math.log(ratio))
        if best is None or (distance, float(key)) < (best[0], float(best[1])):
            best = (distance, key, ratio)
    if best is None or best[0] > math.log(TOLERANCE):
        return None
    return best[1], best[2]


def pair_problem(run: dict[str, Any], rule: str, method: str) -> dict[str, Any]:
    """Seed-paired matched differences for one problem, with the reason of every exclusion."""
    rules = {s["seed"]: s["rule"] for s in run["runs"].get(rule, [])}
    learned = {s["seed"]: s["budgets"] for s in run["runs"].get(method, []) if "budgets" in s}
    out: dict[str, Any] = {"rows": [], "unpaired": 0, "no_alerts": 0, "no_match": 0}
    for seed, decision in rules.items():
        if seed not in learned:
            out["unpaired"] += 1
            continue
        found = match_cell(learned[seed], decision["test_alert_rate"])
        if found is None:
            out["no_alerts" if not decision["test_alert_rate"] > 0 else "no_match"] += 1
            continue
        key, ratio = found
        cell = learned[seed][key]
        out["rows"].append(
            {"budget": float(key), "ratio": ratio}
            | {m: cell[m] - decision[m] for m in METRICS}
        )  # fmt: skip
    return out


def compare(runs: list[dict[str, Any]], rule: str, method: str, draws: int = DRAWS) -> dict:
    problems, sources = [], []
    diffs: dict[str, list[float]] = {m: [] for m in METRICS}
    ratios: list[float] = []
    excluded = {"unpaired": 0, "no_alerts": 0, "no_match": 0, "few_seeds": 0}
    seed_runs = 0
    for run in runs:
        paired = pair_problem(run, rule, method)
        for reason in ("unpaired", "no_alerts", "no_match"):
            excluded[reason] += paired[reason]
        rows = paired["rows"]
        if len(rows) < MIN_SEEDS:
            excluded["few_seeds"] += len(rows)
            continue
        problems.append(run["problem"])
        sources.append(source_id(run["problem"]))
        seed_runs += len(rows)
        ratios += [r["ratio"] for r in rows]
        for m in METRICS:
            diffs[m].append(float(np.mean([r[m] for r in rows])))
    entry: dict[str, Any] = {
        "rule": rule, "method": method, "problems": len(problems), "seed_runs": seed_runs,
        "excluded_seed_runs": excluded,
        "median_alert_ratio": float(np.median(ratios)) if ratios else None,
        "alert_ratio_quartiles": [float(q) for q in np.quantile(ratios, [0.25, 0.75])]
        if ratios
        else None,
    }  # fmt: skip
    if problems:
        clusters = np.array(sources)
        for m in METRICS:
            entry[m] = bootstrap(np.array(diffs[m]), clusters, by_cluster=True, draws=draws)
    return entry


def analyse(runs: list[dict[str, Any]], draws: int = DRAWS) -> dict[str, Any]:
    methods = sorted(
        {m for r in runs for m, seeds in r["runs"].items() if m not in RULES and seeds}
    )
    entries = [compare(runs, rule, m, draws) for rule in RULES for m in methods]
    for metric in METRICS:
        scored = [e for e in entries if metric in e]
        adjusted = holm([e[metric]["p_two_sided"] for e in scored]) if scored else []
        for e, value in zip(scored, adjusted, strict=True):
            e[metric]["holm_p"] = value
    return {
        "tolerance": TOLERANCE, "min_seeds": MIN_SEEDS, "draws": draws,
        "problems_read": len(runs), "comparisons": entries,
    }  # fmt: skip


def load(*folders: Path) -> list[dict[str, Any]]:
    """Merge the classical and neural problem files by problem."""
    merged: dict[str, dict[str, Any]] = {}
    for folder in folders:
        for path in sorted(folder.glob("*.json")):
            run = json.loads(path.read_text())
            if "failed" in run:
                continue
            base = merged.setdefault(run["problem"], {"problem": run["problem"], "runs": {}})
            base["runs"].update(run["runs"])
    return list(merged.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.write_text(
        json.dumps(analyse(load(*args.folders)), indent=1, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
