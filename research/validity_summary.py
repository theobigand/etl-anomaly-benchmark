# ruff: noqa: E501
"""Statistical validity of the labelled-pool rankings (protocol verification/validity_study.md).

Part A: ten seeds, source-grouped ranks, Friedman and Holm-corrected paired tests. Part B: the
ranking under the alternative label rules. The unit is the source group, never the problem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import paired_inference as pinf  # noqa: E402
import source_clustered as sc  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

EVIDENCE = ROOT / "verification" / "evidence"
ARCHIVE = (EVIDENCE / "labelled_pool" / "runs", EVIDENCE / "full_registry" / "pool_deep" / "runs")
NEW = (
    EVIDENCE / "validity" / "seeds_5_9" / "classical",
    EVIDENCE / "validity" / "seeds_5_9" / "deep",
)
RULE_DIRS = (
    EVIDENCE / "validity" / "label_rules" / "classical",
    EVIDENCE / "validity" / "label_rules" / "deep",
)
RULE_SEEDS = 3
FAMILY = {"zscore": "rule", "iqr": "rule", "great_expectations": "rule"}


def family(method: str) -> str:
    return FAMILY.get(method) or ("neural" if method in DEEP_NAMES else "classical")


def load_seeds(directories: tuple[Path, ...]) -> dict[str, dict[str, list[float]]]:
    """problem -> detector -> per-seed PR-AUC, in the order of the seeds of the run."""
    out: dict[str, dict[str, list[float]]] = {}
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            run = json.loads(path.read_text())
            if "failed" in run or "not_applicable" in run:
                continue
            for method, rows in run["metrics"].items():
                if len(rows) == len(run["seeds"]):
                    out.setdefault(run["problem"], {})[method] = [r["pr_auc"] for r in rows]
    return out


def merge(
    old: dict[str, dict[str, list[float]]], new: dict[str, dict[str, list[float]]]
) -> dict[str, dict[str, list[float]]]:
    out: dict[str, dict[str, list[float]]] = {}
    for problem, methods in old.items():
        out[problem] = {m: v + new.get(problem, {}).get(m, []) for m, v in methods.items()}
    return out


def source_table(ap: dict[str, dict[str, float]]) -> tuple[list[str], dict[str, np.ndarray]]:
    """Source group x detector table of the mean AP of the problems of each group (NaN if none)."""
    methods = sorted({m for v in ap.values() for m in v})
    groups = sorted({sc.source_id(p) for p in ap})
    table = {}
    for m in methods:
        column = []
        for g in groups:
            values = [ap[p][m] for p in ap if sc.source_id(p) == g and m in ap[p]]
            column.append(float(np.mean(values)) if values else float("nan"))
        table[m] = np.array(column)
    return groups, table


def ranking(table: dict[str, np.ndarray], draws: int) -> dict[str, Any]:
    names, matrix = pinf.complete_matrix(table)
    ranks = pinf.mean_ranks(matrix)
    intervals = pinf.rank_intervals(matrix, draws)
    return {
        "detectors": names,
        "units": int(len(matrix)),
        "mean_rank": dict(zip(names, map(float, ranks), strict=True)),
        "rank_interval": {
            n: [float(a), float(b)] for n, (a, b) in zip(names, intervals, strict=True)
        },
        "friedman": pinf.friedman(matrix),
    }


def tau(a: dict[str, float], b: dict[str, float]) -> float:
    names = sorted(set(a) & set(b))
    return pinf.kendall(np.array([a[n] for n in names]), np.array([b[n] for n in names]))


def part_a(seeded: dict[str, dict[str, list[float]]], draws: int) -> dict[str, Any]:
    ten = {
        p: {m: float(np.mean(v)) for m, v in d.items() if len(v) >= 10} for p, d in seeded.items()
    }
    five = {
        p: {m: float(np.mean(v[:5])) for m, v in d.items() if len(v) >= 5}
        for p, d in seeded.items()
    }
    groups, table = source_table(ten)
    _, table5 = source_table(five)
    rank10, rank5 = ranking(table, draws), ranking(table5, draws)
    pairs = pinf.pairwise(table, draws)
    ordered = sorted(rank10["mean_rank"], key=rank10["mean_rank"].get)
    best, second = ordered[0], ordered[1]
    top_pair = next(r for r in pairs if {r["a"], r["b"]} == {best, second})
    fams = {}
    for name in ("rule", "classical", "neural"):
        members = [m for m in table if family(m) == name]
        fams[name] = np.nanmean(np.column_stack([table[m] for m in members]), axis=1)
    problem_table = {m: np.array([ten[p].get(m, np.nan) for p in sorted(ten)]) for m in table}
    return {
        "problems": len(ten),
        "independent_sources": len(groups),
        "ten_seeds": rank10,
        "five_seeds": rank5,
        "V4_tau_5_vs_10": tau(rank10["mean_rank"], rank5["mean_rank"]),
        "problem_level_ranking": ranking(problem_table, draws),
        "pairwise": pairs,
        "pairs_significant_holm_05": sum(r["p_holm"] < 0.05 for r in pairs),
        "pairs_total": len(pairs),
        "V3": {"best": best, "second": second, **top_pair},
        "families": pinf.pairwise(fams, draws),
    }


def part_b(
    seeded: dict[str, dict[str, list[float]]],
    rules: dict[str, dict[str, dict[str, list[float]]]],
    draws: int,
) -> dict[str, Any]:
    uci = {p: d for p, d in seeded.items() if p.startswith("uci:")}
    results: dict[str, Any] = {}
    for rule, runs in rules.items():
        problems = sorted(set(runs) & set(uci))
        r0 = {p: {m: float(np.mean(v[:RULE_SEEDS])) for m, v in uci[p].items()} for p in problems}
        rr = {p: {m: float(np.mean(v)) for m, v in runs[p].items()} for p in problems}
        _, t0 = source_table(r0)
        _, tr = source_table(rr)
        a, b = ranking(t0, draws), ranking(tr, draws)
        common = set(a["mean_rank"]) & set(b["mean_rank"])
        best0 = min(common, key=a["mean_rank"].get)
        order = sorted(common, key=b["mean_rank"].get)
        results[rule] = {
            "problems": len(problems),
            "sources": b["units"],
            "kendall_tau_vs_R0": tau(a["mean_rank"], b["mean_rank"]),
            "R0_leader": best0,
            "R0_leader_rank_under_rule": order.index(best0) + 1,
            "leader_under_rule": order[0],
            "mean_rank_R0": a["mean_rank"],
            "mean_rank_rule": b["mean_rank"],
        }
    return results


def render(summary: dict[str, Any]) -> str:
    a = summary["A"]
    ten = a["ten_seeds"]
    lines = [
        "# Statistical validity of the labelled-pool rankings",
        "",
        f"Problems {a['problems']}; independent source groups {a['independent_sources']} (units of inference). "
        f"Friedman over {ten['friedman']['units']} sources and {ten['friedman']['detectors']} detectors: p = {ten['friedman']['p']:.3g}. "
        f"Pairs significant after Holm: {a['pairs_significant_holm_05']} of {a['pairs_total']}. "
        f"Five-seed versus ten-seed ranking, Kendall tau {a['V4_tau_5_vs_10']:.2f}.",
        "",
        f"V3: best {a['V3']['best']} against second {a['V3']['second']}: median AP difference "
        f"{a['V3']['median_difference']:+.3f} [{a['V3']['ci_low']:+.3f}, {a['V3']['ci_high']:+.3f}], p (Holm) {a['V3']['p_holm']:.3f}.",
        "",
        "| Detector | Mean rank (10 seeds) | 95 % interval | Mean rank (5 seeds) |",
        "|---|---:|---|---:|",
    ]
    for m in sorted(ten["mean_rank"], key=ten["mean_rank"].get):
        lo, hi = ten["rank_interval"][m]
        lines.append(
            f"| {m} | {ten['mean_rank'][m]:.2f} | {lo:.2f} to {hi:.2f} | {a['five_seeds']['mean_rank'].get(m, float('nan')):.2f} |"
        )
    lines += [
        "",
        "| Families | Median difference | 95 % interval | p (Holm) |",
        "|---|---:|---|---:|",
    ]
    for r in a["families"]:
        lines.append(
            f"| {r['a']} - {r['b']} | {r['median_difference']:+.3f} | {r['ci_low']:+.3f} to {r['ci_high']:+.3f} | {r['p_holm']:.3f} |"
        )
    lines += [
        "",
        "## Label rules",
        "",
        "| Rule | Problems | Sources | Kendall tau vs R0 | R0 leader | its rank | Leader under the rule |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for rule, v in summary["B"].items():
        lines.append(
            f"| {rule} | {v['problems']} | {v['sources']} | {v['kendall_tau_vs_R0']:.2f} | {v['R0_leader']} | {v['R0_leader_rank_under_rule']} | {v['leader_under_rule']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    draws = pinf.DRAWS
    seeded = merge(load_seeds(ARCHIVE), load_seeds(NEW))
    rules: dict[str, dict[str, dict[str, list[float]]]] = {}
    for directory in RULE_DIRS:
        for path in sorted(directory.glob("*.json")):
            run = json.loads(path.read_text())
            if "failed" in run or "not_applicable" in run:
                continue
            for method, rows in run["metrics"].items():
                if len(rows) == len(run["seeds"]):
                    rules.setdefault(run["rule"], {}).setdefault(run["problem"], {})[method] = [
                        r["pr_auc"] for r in rows
                    ]
    summary = {"A": part_a(seeded, draws), "B": part_b(seeded, dict(sorted(rules.items())), draws)}
    out = EVIDENCE / "validity"
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (out / "summary.md").write_text(render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
