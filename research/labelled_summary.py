"""Pooled summary of the labelled-pool benchmark and the hypothesis checks of labelled_pool.md.

The thresholds are those of verification/labelled_pool.md, written before any result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# The six detectors of verification/labelled_pool.md: its hypotheses are stated on them.
CORE = ("zscore", "iqr", "great_expectations", "isolation_forest", "lof", "ocsvm")
# The five classical detectors of verification/full_registry.md.
NEW_CLASSICAL = ("ecod", "copod", "hbos", "knn", "pca")
DEEP_FAILURE_SHARE = 0.05
DEEP_MARGIN = 0.02
BINS = (("<5%", 0.0, 0.05), ("5-20%", 0.05, 0.20), (">20%", 0.20, 1.01))


def table(runs: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for run in runs:
        if "failed" in run:
            continue
        for method, per_seed in run["metrics"].items():
            mean = pd.DataFrame(per_seed).mean()
            rows.append(
                {
                    "problem": run["problem"],
                    "source": run["source"],
                    "prevalence": run["prevalence"],
                    "method": method,
                    "pr_auc": mean["pr_auc"],
                    "roc_auc": mean["roc_auc"],
                    "f1": mean["f1"],
                    "flagged_pct": mean["flagged_pct"],
                }
            )
    return pd.DataFrame(rows)


def _wide(data: pd.DataFrame, value: str = "pr_auc") -> pd.DataFrame:
    return data.pivot(index="problem", columns="method", values=value)


def pooled(data: pd.DataFrame, value: str = "pr_auc", resamples: int = 2000, seed: int = 0):
    """Median over problems with a bootstrap interval resampling the problems."""
    wide = _wide(data, value)
    rng = np.random.default_rng(seed)
    values = wide.to_numpy(dtype=float)
    boot = np.stack(
        [
            np.nanmedian(values[rng.integers(0, len(values), len(values))], axis=0)
            for _ in range(resamples)
        ]
    )
    return pd.DataFrame(
        {
            "median": np.nanmedian(values, axis=0),
            "lo": np.nanpercentile(boot, 2.5, axis=0),
            "hi": np.nanpercentile(boot, 97.5, axis=0),
        },
        index=wide.columns,
    )


def ranks(data: pd.DataFrame) -> pd.DataFrame:
    """Rank of each method per problem on PR-AUC (1 is best, ties share the mean rank)."""
    return _wide(data).rank(axis=1, ascending=False).T


def _prevalence(data: pd.DataFrame) -> pd.Series:
    return data.groupby("problem")["prevalence"].first()


def hypotheses(data: pd.DataFrame, resamples: int = 2000) -> dict[str, Any]:
    wide = _wide(data)
    summary = pooled(data, resamples=resamples)
    top = summary.sort_values("median", ascending=False)
    out: dict[str, Any] = {}
    first, second = top.iloc[0], top.iloc[1]
    out["H1"] = {
        "supported": bool(first["lo"] <= second["hi"]),
        "best": top.index[0],
        "second": top.index[1],
    }
    out["H2"] = {
        "supported": bool(
            summary.loc["isolation_forest", "median"] > summary.loc["zscore", "median"]
            and summary.loc["isolation_forest", "median"] > summary.loc["iqr", "median"]
        )
    }
    prevalence = _prevalence(data).reindex(wide.index)
    diff = wide["isolation_forest"] - wide["zscore"]
    by_bin = {}
    for label, low, high in BINS:
        chosen = diff[(prevalence >= low) & (prevalence < high)].dropna()
        by_bin[label] = {
            "median": float(chosen.median()) if len(chosen) else None,
            "n": len(chosen),
        }
    low_bin, high_bin = by_bin["<5%"]["median"], by_bin[">20%"]["median"]
    out["H3"] = {
        "supported": bool(
            low_bin is not None and high_bin is not None and low_bin > 0 and high_bin <= 0
        ),
        "by_prevalence": by_bin,
    }
    ratio = _wide(data, "flagged_pct").div(100 * prevalence, axis=0)
    medians = ratio.median()
    out["H4"] = {
        "supported": bool(medians["iqr"] > 3 and medians["iqr"] == medians.max()),
        "median_flag_to_prevalence": {m: float(v) for m, v in medians.items()},
    }
    by_source = {
        source: pooled(chunk, resamples=1)["median"]
        for source, chunk in data.groupby("source")
        if chunk["problem"].nunique() > 1
    }
    if len(by_source) == 2:
        a, b = by_source.values()
        rho = float(spearmanr(a, b.reindex(a.index)).statistic)
    else:
        rho = float("nan")
    out["H5"] = {"supported": bool(rho >= 0.7), "spearman": rho}
    return out


def registry_hypotheses(
    classical: pd.DataFrame, deep: pd.DataFrame, deep_runs: list[dict[str, Any]]
) -> dict[str, Any]:
    """H1, H2 and H6 of verification/full_registry.md on the labelled pool."""
    medians = pooled(classical, resamples=1)["median"]
    new = medians.reindex(list(NEW_CLASSICAL))
    out: dict[str, Any] = {
        "H1": {
            "supported": bool((new > medians["isolation_forest"]).any()),
            "isolation_forest": float(medians["isolation_forest"]),
            "new_classical": {m: float(v) for m, v in new.items()},
        }
    }
    best = medians.idxmax()
    deep_medians = pooled(deep, resamples=1)["median"]
    out["H2"] = {
        "supported": bool((deep_medians <= medians.max() + DEEP_MARGIN).all()),
        "best_classical": {"method": best, "median": float(medians.max())},
        "deep": {m: float(v) for m, v in deep_medians.items()},
    }
    ran = [r for r in deep_runs if "failed" not in r]
    failures = {}
    for method in deep_medians.index:
        skipped = sum(method in r.get("skipped", []) for r in ran)
        failed = sum(bool(r.get("errors", {}).get(method)) for r in ran)
        failures[method] = {"failed": failed, "problems": len(ran) - skipped}
    out["H6"] = {
        "supported": bool(
            all(v["failed"] <= DEEP_FAILURE_SHARE * v["problems"] for v in failures.values())
        ),
        "failures": failures,
    }
    return out


def load(runs: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in sorted(runs.glob("*.json"))]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument(
        "--deep-runs", type=Path, help="runs of the neural detectors, same problems"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    runs = load(args.runs)
    data = table(runs)
    failed = {r["problem"]: r["failed"] for r in runs if "failed" in r}
    skipped = {r["problem"]: r["skipped"] for r in runs if r.get("skipped")}
    results = {
        "problems": int(data["problem"].nunique()),
        "failed": failed,
        "skipped": skipped,
        "pr_auc": json.loads(pooled(data).to_json(orient="split")),
        "roc_auc": json.loads(pooled(data, "roc_auc").to_json(orient="split")),
        "median_rank": {m: float(v) for m, v in ranks(data).median(axis=1).items()},
        "hypotheses": hypotheses(data[data["method"].isin(CORE)]),
    }
    if args.deep_runs:
        deep_runs = load(args.deep_runs)
        deep = table(deep_runs)
        results["deep"] = {
            "pr_auc": json.loads(pooled(deep).to_json(orient="split")),
            "roc_auc": json.loads(pooled(deep, "roc_auc").to_json(orient="split")),
            "hypotheses": registry_hypotheses(data, deep, deep_runs),
        }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "labelled_results.json").write_text(
        json.dumps(results, indent=1, sort_keys=True) + "\n"
    )
    pr, roc = pooled(data), pooled(data, "roc_auc")
    lines = [
        f"Median over {results['problems']} labelled problems (95% interval over problems)",
        "",
    ]
    lines += ["| method | PR-AUC | ROC-AUC | median rank |", "|---|---|---|---|"]
    for method in pr.index:
        a, b = pr.loc[method], roc.loc[method]
        lines.append(
            f"| {method} | {a['median']:.3f} [{a['lo']:.3f}, {a['hi']:.3f}] "
            f"| {b['median']:.3f} [{b['lo']:.3f}, {b['hi']:.3f}] "
            f"| {results['median_rank'][method]:.1f} |"
        )
    if args.deep_runs:
        both = pd.concat([data, deep])
        dp, dr = pooled(deep), pooled(deep, "roc_auc")
        lines += ["", "Neural detectors (fit rows capped, same problems)", ""]
        lines += ["| method | PR-AUC | ROC-AUC |", "|---|---|---|"]
        for method in dp.index:
            a, b = dp.loc[method], dr.loc[method]
            lines.append(
                f"| {method} | {a['median']:.3f} [{a['lo']:.3f}, {a['hi']:.3f}] "
                f"| {b['median']:.3f} [{b['lo']:.3f}, {b['hi']:.3f}] |"
            )
        results["median_rank_all"] = {m: float(v) for m, v in ranks(both).median(axis=1).items()}
        lines += [
            "",
            "Median rank over all methods: "
            + ", ".join(
                f"{m} {v:.1f}"
                for m, v in sorted(results["median_rank_all"].items(), key=lambda x: x[1])
            ),
        ]
        (args.output / "labelled_results.json").write_text(
            json.dumps(results, indent=1, sort_keys=True) + "\n"
        )
    (args.output / "labelled_results.md").write_text("\n".join(lines) + "\n")
    print(f"{results['problems']} problems, {len(failed)} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
