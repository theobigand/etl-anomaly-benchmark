"""Summary of the mixed-schema typed injection (verification/typed_mixed.md, hypotheses M1 to M3).

Units are independent sources: entries that share a source are averaged first, so the intervals
are not narrowed by repeated derivations of one table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import source_clustered as sc  # noqa: E402

EVIDENCE = ROOT / "verification" / "evidence"
NUMERIC = EVIDENCE / "pool_extension" / "typed" / "all_classical" / "typed_results.json"
RULES = ("zscore", "iqr", "great_expectations")
DISTANCE = ("knn", "lof", "ocsvm", "isolation_forest")
RENAMED = {"distribution_shift": "temporal_drift"}  # name in the numeric protocol


SEED, DRAWS = 2026, 2000


def load(folder: Path) -> pd.DataFrame:
    """One row per dataset, detector and fault type; absent types are absent rows."""
    rows = []
    for path in sorted(folder.glob("*.json")):
        run = json.loads(path.read_text())
        schema = run["carrier"]["kinds"]
        kinds = {"num": sum(v == "num" for v in schema.values())}
        kinds["cat"] = len(schema) - kinds["num"]
        for method, by_type in run["recall_pooled"].items():
            for fault, value in by_type.items():
                if value is not None:
                    rows.append(
                        {
                            "id": run["id"],
                            "source": sc.source_id(run["id"]),
                            "tier": run["tier"],
                            "numeric_only": kinds["cat"] == 0,
                            "method": method,
                            "type": fault,
                            "recall": value,
                            "test_n": run["test_counts"][fault],
                        }
                    )
    return pd.DataFrame(rows)


def by_source(frame: pd.DataFrame) -> pd.DataFrame:
    """Average of the entries of one source, per detector and type."""
    return frame.groupby(["source", "method", "type"])["recall"].mean().reset_index()


def medians(frame: pd.DataFrame, seed: int = SEED, draws: int = DRAWS) -> list[dict[str, Any]]:
    out = []
    for (method, fault), group in by_source(frame).groupby(["method", "type"]):
        values = group["recall"].to_numpy()
        rng = np.random.default_rng(seed)
        boot = np.median(rng.choice(values, (draws, len(values))), axis=1)
        low, high = np.quantile(boot, [0.025, 0.975])
        out.append(
            {
                "method": method,
                "type": fault,
                "sources": len(values),
                "median": float(np.median(values)),
                "ci": [float(low), float(high)],
            }
        )
    return out


def m1(frame: pd.DataFrame) -> dict[str, Any]:
    """Rank agreement of per-type detector medians: numeric-only mixed tables vs the 58 tables."""
    numeric = json.loads(NUMERIC.read_text())["median"]
    reference = pd.DataFrame(numeric["data"], index=numeric["index"], columns=numeric["columns"])
    sub = by_source(frame[frame["numeric_only"]])
    table = sub.groupby(["method", "type"])["recall"].median().unstack()
    result = {}
    for fault in table.columns:
        ref = RENAMED.get(fault, fault)
        if ref not in reference.columns:
            continue
        both = pd.concat([table[fault], reference[ref]], axis=1).dropna()
        if len(both) >= 5:
            result[fault] = float(spearmanr(both.iloc[:, 0], both.iloc[:, 1]).statistic)
    return {
        "per_type_rank_correlation": result,
        "mean": float(np.mean(list(result.values()))) if result else None,
        "sources": int(sub["source"].nunique()),
    }


def m2(frame: pd.DataFrame) -> dict[str, Any]:
    """Recall of rule detectors against distance and density detectors on categorical faults."""
    sub = by_source(frame)
    sub = sub[sub["type"].isin(["invalid_code", "cross_column_swap"])]
    groups = {"rules": RULES, "distance_density": DISTANCE}
    return {
        fault: {
            name: float(
                sub[(sub["type"] == fault) & sub["method"].isin(members)]["recall"].median()
            )
            for name, members in groups.items()
        }
        for fault in ("invalid_code", "cross_column_swap")
    }


def m3(frame: pd.DataFrame) -> dict[str, Any]:
    """Tier B against tier A recall, per detector, over sources (Mann-Whitney)."""
    sub = frame.groupby(["source", "tier", "method"])["recall"].mean().reset_index()
    result = {}
    for method, group in sub.groupby("method"):
        a = group[group["tier"] == "A"]["recall"]
        b = group[group["tier"] == "B"]["recall"]
        if len(a) >= 5 and len(b) >= 5:
            test = mannwhitneyu(a, b)
            result[method] = {
                "median_A": float(a.median()),
                "median_B": float(b.median()),
                "p": float(test.pvalue),
            }
    adjusted = sc.holm([v["p"] for v in result.values()])
    for n, entry in enumerate(result.values()):
        entry["p_holm"] = adjusted[n]
    return result


def summarise(folder: Path) -> dict[str, Any]:
    frame = load(folder)
    return {
        "datasets": int(frame["id"].nunique()),
        "sources": int(frame["source"].nunique()),
        "tiers": frame.drop_duplicates("id")["tier"].value_counts().to_dict(),
        "types": frame.drop_duplicates(["id", "type"])["type"].value_counts().to_dict(),
        "medians": medians(frame),
        "M1": m1(frame),
        "M2": m2(frame),
        "M3": m3(frame),
    }


def _md(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join([frame.index.name or "", *map(str, frame.columns)]) + " |"
    rule = "|" + "---|" * (len(frame.columns) + 1)
    body = [f"| {row[0]} | " + " | ".join(map(str, row[1:])) + " |" for row in frame.itertuples()]
    return "\n".join([head, rule, *body])


def report(summary: dict[str, Any]) -> str:
    table = pd.DataFrame(summary["medians"]).pivot(index="method", columns="type", values="median")
    lines = [
        "# Typed injection on mixed-schema and small tables",
        "",
        f"{summary['datasets']} tables from {summary['sources']} independent sources "
        f"(tier A {summary['tiers'].get('A', 0)}, tier B {summary['tiers'].get('B', 0)}).",
        "",
        "Median recall over sources, by detector and fault type:",
        "",
        _md(table.round(2)),
        "",
        f"M1 mean rank correlation with the numeric protocol: {summary['M1']['mean']}",
        f"M2: {json.dumps(summary['M2'])}",
        "",
        "M3 (tier B against tier A), Holm-adjusted:",
        "",
        _md(pd.DataFrame(summary["M3"]).T.round(3)),
        "",
    ]
    return "\n".join(lines)


SUMMARY_JSON, SUMMARY_MD = "summary.json", "summary.md"

PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument("folder", type=Path)
PARSER.add_argument("--out", type=Path, required=True)


def write_summary(out: Path, summary: dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / SUMMARY_JSON).write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (out / SUMMARY_MD).write_text(report(summary))


def main(argv: list[str] | None = None) -> int:
    args = PARSER.parse_args(argv)
    summary = summarise(args.folder)
    write_summary(args.out, summary)
    print(json.dumps({k: summary[k] for k in ("datasets", "sources", "tiers")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
