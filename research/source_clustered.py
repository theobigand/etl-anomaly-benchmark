"""Source-clustered paired comparison of detectors on the labelled pool (T139-T148).

Problems derived from the same original data are not independent: 35 of the 36 ADBench problems
come from a UCI source and 15 of those sources are also labelled UCI problems. This post-hoc
re-analysis of the archived per-seed average precision groups every problem by its original source
(``source_id``), averages the five seeds within a problem, and resamples whole sources with
replacement. The comparisons were chosen from those the manuscript already reports, after the
results were known; they are exploratory and no equivalence is claimed.
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
from dataset_registry import UCI_SOURCES  # noqa: E402

COMPARISONS = (
    ("ecod", "isolation_forest"),
    ("copod", "isolation_forest"),
    ("ocsvm", "isolation_forest"),
    ("dif", "ecod"),
    ("zscore", "isolation_forest"),
    ("great_expectations", "isolation_forest"),
)
BOOTSTRAPS = 10_000
SEED = 2026
LEVEL = 0.95


def source_id(problem: str) -> str:
    """Original source of a problem: the UCI table when an ADBench file is derived from one."""
    kind, _, name = problem.partition(":")
    if kind == "adbench" and name in UCI_SOURCES:
        return f"uci:{UCI_SOURCES[name][0]}"
    return problem


def load_ap(directories: list[Path]) -> tuple[list[str], dict[str, np.ndarray]]:
    """Per-problem mean average precision of every detector (NaN where it did not run)."""
    records: dict[str, dict[str, float]] = {}
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            run = json.loads(path.read_text())
            if "failed" in run:
                continue
            row = records.setdefault(run["problem"], {})
            for method, seeds in run["metrics"].items():
                if len(seeds) == len(run["seeds"]):
                    row[method] = float(np.mean([item["pr_auc"] for item in seeds]))
    problems = sorted(records)
    methods = sorted({m for row in records.values() for m in row})
    table = {m: np.array([records[p].get(m, np.nan) for p in problems]) for m in methods}
    return problems, table


def _interval(values: np.ndarray) -> tuple[float, float]:
    tail = (1 - LEVEL) / 2
    low, high = np.quantile(values, [tail, 1 - tail])
    return float(low), float(high)


def bootstrap(
    differences: np.ndarray, clusters: np.ndarray, *, by_cluster: bool, seed: int = SEED,
    draws: int = BOOTSTRAPS,
) -> dict[str, Any]:  # fmt: skip
    """Mean and median difference with percentile intervals and a two-sided bootstrap p-value."""
    rng = np.random.default_rng(seed)
    n = len(differences)
    labels = np.unique(clusters)
    members = [np.flatnonzero(clusters == label) for label in labels]
    means, medians = np.empty(draws), np.empty(draws)
    for index in range(draws):
        if by_cluster:
            picked = np.concatenate([members[i] for i in rng.integers(0, len(labels), len(labels))])
        else:
            picked = rng.integers(0, n, n)
        sample = differences[picked]
        means[index], medians[index] = sample.mean(), np.median(sample)
    below, above = float((means <= 0).mean()), float((means >= 0).mean())
    return {
        "units": int(len(labels) if by_cluster else n),
        "mean": float(differences.mean()),
        "mean_ci": _interval(means),
        "median": float(np.median(differences)),
        "median_ci": _interval(medians),
        "p_two_sided": float(min(1.0, 2 * min(below, above))),
    }


def holm(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, in the input order."""
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values))
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted.tolist()


def analyse(
    problems: list[str], table: dict[str, np.ndarray], *, draws: int | None = None
) -> dict[str, Any]:
    draws = BOOTSTRAPS if draws is None else draws
    sources = np.array([source_id(p) for p in problems])
    labelled_uci = {p for p in problems if p.startswith("uci:")}
    overlapping = np.array([
        p.startswith("adbench:") and source_id(p) in labelled_uci for p in problems
    ])  # fmt: skip
    results = []
    for first, second in COMPARISONS:
        both = ~np.isnan(table[first]) & ~np.isnan(table[second])
        differences = table[first][both] - table[second][both]
        entry: dict[str, Any] = {"comparison": f"{first} - {second}", "problems": int(both.sum())}
        entry["by_problem"] = bootstrap(differences, sources[both], by_cluster=False, draws=draws)
        entry["by_source"] = bootstrap(differences, sources[both], by_cluster=True, draws=draws)
        keep = both & ~overlapping
        entry["without_overlap"] = bootstrap(
            table[first][keep] - table[second][keep], sources[keep], by_cluster=True, draws=draws
        ) | {"problems": int(keep.sum())}
        results.append(entry)
    adjusted = holm([item["by_source"]["p_two_sided"] for item in results])
    for item, value in zip(results, adjusted, strict=True):
        item["holm_p_by_source"] = value
    return {
        "problems": len(problems),
        "sources": int(len(np.unique(sources))),
        "overlapping_adbench_problems": int(overlapping.sum()),
        "bootstraps": draws,
        "seed": SEED,
        "level": LEVEL,
        "comparisons": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent / "verification" / "evidence"
    parser.add_argument("--classical", type=Path, default=root / "labelled_pool" / "runs")
    parser.add_argument("--deep", type=Path, default=root / "full_registry" / "pool_deep" / "runs")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    problems, table = load_ap([args.classical, args.deep])
    result = analyse(problems, table)
    args.output.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(f"{result['problems']} problems, {result['sources']} sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
