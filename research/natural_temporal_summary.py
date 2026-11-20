# ruff: noqa: E501
"""Summary of the naturally labelled chronological study (protocol verification/natural_temporal.md).

Reads the per-series results, computes N1 to N4 over source groups (the unit of inference) and
writes ``summary.json`` and ``summary.md`` next to them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import paired_inference as pinf  # noqa: E402
import temporal_decision as td  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

RULES = ("zscore", "iqr", "great_expectations")
FAMILIES = {"rule": RULES, "neural": tuple(DEEP_NAMES)}
SUPPORT_SHARE = 2 / 3


def load(directory: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evaluated, excluded = [], []
    for path in sorted(directory.glob("*.json")):
        record = json.loads(path.read_text())
        (excluded if "excluded" in record else evaluated).append(record)
    return evaluated, excluded


def family(method: str) -> str:
    if method in RULES:
        return "rule"
    return "neural" if method in FAMILIES["neural"] else "classical"


def lifts(record: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Chronological and stratified PR-AUC per detector, and their lift over prevalence."""
    part = record["partitions"]
    rows = sum(p["rows"] for p in part.values())
    overall = sum(p["positives"] for p in part.values()) / rows
    test = part["test"]["prevalence"]
    out = {}
    for method, chrono in record["chronological"].items():
        strat = record["stratified"][method]
        out[method] = {
            "chronological": chrono["pr_auc"],
            "stratified": strat["pr_auc"],
            "matched": strat["pr_auc_matched"],
            "chronological_lift": (chrono["pr_auc"] - test) / (1 - test),
            "stratified_lift": (strat["pr_auc"] - overall) / (1 - overall),
        }
    return out


def table_by_group(
    evaluated: list[dict[str, Any]], pick: Any
) -> tuple[list[str], dict[str, np.ndarray]]:
    """One value per source group and detector: the mean over the series of the group."""
    groups = sorted({r["group"] for r in evaluated})
    methods = sorted({m for r in evaluated for m in r["chronological"]})
    table = {}
    for method in methods:
        column = []
        for group in groups:
            values = [
                pick(r, method)
                for r in evaluated
                if r["group"] == group and method in r["chronological"]
            ]
            column.append(float(np.mean(values)) if values else float("nan"))
        table[method] = np.array(column)
    return groups, table


def summarise(
    evaluated: list[dict[str, Any]], excluded: list[dict[str, Any]], draws: int = pinf.DRAWS
) -> dict[str, Any]:
    per_series = {r["id"]: lifts(r) for r in evaluated}
    groups, chrono = table_by_group(evaluated, lambda r, m: per_series[r["id"]][m]["chronological"])
    _, strat = table_by_group(evaluated, lambda r, m: per_series[r["id"]][m]["stratified"])
    pairs = [(r["id"], m) for r in evaluated for m in r["chronological"]]
    lower = sum(
        per_series[i][m]["chronological"] < per_series[i][m]["stratified"] for i, m in pairs
    )
    share = lower / len(pairs)
    detectors = {}
    for method in chrono:
        d = chrono[method] - strat[method]
        detectors[method] = pinf.paired_effect(chrono[method], strat[method], draws)
        detectors[method]["groups_lower"] = int((d < 0).sum())
    median_ci_below = {m: bool(v.get("ci_high", 1) < 0) for m, v in detectors.items()}
    h = td.hypotheses({r["id"]: r for r in evaluated})
    rho = [
        float(
            spearmanr(
                [r["stratified"][m]["pr_auc"] for m in r["chronological"]],
                [r["chronological"][m]["pr_auc"] for m in r["chronological"]],
            ).statistic
        )
        for r in evaluated
    ]
    _, chrono_lift = table_by_group(
        evaluated, lambda r, m: per_series[r["id"]][m]["chronological_lift"]
    )
    _, strat_lift = table_by_group(
        evaluated, lambda r, m: per_series[r["id"]][m]["stratified_lift"]
    )
    lift_lower = sum(
        per_series[i][m]["chronological_lift"] < per_series[i][m]["stratified_lift"]
        for i, m in pairs
    )
    lift_by_detector = {
        m: pinf.paired_effect(chrono_lift[m], strat_lift[m], draws) for m in chrono_lift
    }
    names, matrix = pinf.complete_matrix(chrono)
    ranks = pinf.mean_ranks(matrix)
    intervals = pinf.rank_intervals(matrix, draws)
    fam = {}
    for name in ("rule", "classical", "neural"):
        members = [m for m in chrono if family(m) == name]
        fam[name] = np.nanmean(np.column_stack([chrono[m] for m in members]), axis=1)
    family_rows = pinf.pairwise(fam, draws)
    return {
        "series": {"evaluated": len(evaluated), "excluded": len(excluded)},
        "source_groups": groups,
        "independent_sources": len(groups),
        "N1": {
            "pairs": len(pairs),
            "chronological_lower_share": share,
            "supported_by_share": bool(share >= SUPPORT_SHARE),
            "detectors_with_interval_below_zero": sorted(
                m for m, ok in median_ci_below.items() if ok
            ),
            "by_detector": detectors,
        },
        "N1_lift": {
            "chronological_lower_share": lift_lower / len(pairs),
            "detectors_with_interval_below_zero": sorted(
                m for m, v in lift_by_detector.items() if v.get("ci_high", 1) < 0
            ),
            "by_detector": lift_by_detector,
        },
        "N2": {
            "median_spearman": float(np.median(rho)),
            "supported": bool(np.median(rho) >= 0.8),
            "by_series": dict(zip((r["id"] for r in evaluated), rho, strict=True)),
        },
        "N3": {
            "series_where_matching_closes_half": int(
                sum(v["ok"] for v in h["H4"]["by_dataset"].values())
            ),
            "series": len(evaluated),
        },
        "decision_policies": {
            "H2": {k: v["ok"] for k, v in h["H2"]["by_dataset"].items()},
            "H3": {k: h["H3"][k] for k in ("p2_at_least_p0", "pairs")},
        },
        "N4": {
            "detectors": names,
            "mean_rank": dict(zip(names, map(float, ranks), strict=True)),
            "rank_interval": {
                n: [float(a), float(b)] for n, (a, b) in zip(names, intervals, strict=True)
            },
            "friedman": pinf.friedman(matrix),
            "families": family_rows,
        },
        "per_series": per_series,
        "excluded": [
            {"id": r["id"], "group": r["group"], "reason": r["excluded"]} for r in excluded
        ],
    }


def render(summary: dict[str, Any]) -> str:
    n1, n2, n3, n4 = summary["N1"], summary["N2"], summary["N3"], summary["N4"]
    lines = [
        "# Naturally labelled chronological study: results",
        "",
        f"Series evaluated: {summary['series']['evaluated']} of "
        f"{summary['series']['evaluated'] + summary['series']['excluded']}; independent source groups: "
        f"{summary['independent_sources']} ({', '.join(summary['source_groups'])}).",
        "",
        f"- N1: chronological PR-AUC below stratified for {n1['chronological_lower_share']:.1%} of "
        f"{n1['pairs']} (series, detector) pairs; share rule {'met' if n1['supported_by_share'] else 'not met'}; "
        f"detectors whose group-level median difference interval is below zero: "
        f"{len(n1['detectors_with_interval_below_zero'])} of {len(n1['by_detector'])}.",
        f"- N1 on the lift over prevalence (exploratory, prevalence-adjusted): chronological lower for "
        f"{summary['N1_lift']['chronological_lower_share']:.1%} of pairs; detectors with an interval below zero: "
        f"{len(summary['N1_lift']['detectors_with_interval_below_zero'])} of {len(summary['N1_lift']['by_detector'])}.",
        f"- N2: median Spearman between arms {n2['median_spearman']:.2f} ({'supported' if n2['supported'] else 'not supported'}).",
        f"- N3: matching closes at least half of the gap in {n3['series_where_matching_closes_half']} of {n3['series']} series.",
        f"- N4: Friedman over {n4['friedman']['units']} source groups, p = {n4['friedman']['p']:.3g}.",
        "",
        "| Detector | Mean rank | 95 % interval | Median chronological - stratified | 95 % interval |",
        "|---|---|---|---|---|",
    ]
    for m in sorted(n4["mean_rank"], key=n4["mean_rank"].get):
        lo, hi = n4["rank_interval"][m]
        e = n1["by_detector"][m]
        lines.append(
            f"| {m} | {n4['mean_rank'][m]:.2f} | {lo:.2f} to {hi:.2f} | {e['median_difference']:+.3f} | {e['ci_low']:+.3f} to {e['ci_high']:+.3f} |"
        )
    lines += [
        "",
        "| Families | Median difference | 95 % interval | p (Holm) | Probability of superiority |",
        "|---|---|---|---|---|",
    ]
    for r in n4["families"]:
        lines.append(
            f"| {r['a']} - {r['b']} | {r['median_difference']:+.3f} | {r['ci_low']:+.3f} to {r['ci_high']:+.3f} | {r['p_holm']:.3f} | {r['probability_of_superiority']:.2f} |"
        )
    lines += ["", "Not evaluated:", ""]
    for e in summary["excluded"]:
        lines.append(f"- {e['id']} ({e['group']}): {e['reason']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=ROOT / "verification/evidence/natural_temporal/results"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "verification/evidence/natural_temporal"
    )
    args = parser.parse_args(argv)
    evaluated, excluded = load(args.results)
    summary = summarise(evaluated, excluded)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (args.output / "summary.md").write_text(render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
