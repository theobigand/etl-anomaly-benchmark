"""Tables and hypotheses P1 to P6 of the pool extension (verification/pool_extension.md)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

METRICS = ("precision", "recall", "f1", "flagged_pct")
GRID = ("0.001", "0.01", "0.05", "0.1", "0.2")


def load_runs(*folders: Path) -> list[dict[str, Any]]:
    """The problem files of the one-pass runs, the classical and the neural folders together."""
    merged: dict[str, dict[str, Any]] = {}
    for folder in folders:
        for path in sorted(folder.glob("*.json")):
            run = json.loads(path.read_text())
            if "failed" in run:
                continue
            base = merged.setdefault(
                run["problem"], {**run, "runs": {}, "errors": {}, "skipped": []}
            )
            base["runs"].update(run["runs"])
            base["errors"].update(run["errors"])
            base["skipped"] = sorted(set(base["skipped"]) | set(run["skipped"]))
    return list(merged.values())


def per_problem(runs: list[dict[str, Any]], key: str, metric: str) -> pd.DataFrame:
    """Seed-mean of ``metric`` of the table ``key`` ("metrics" or "fixed"): problems by methods."""
    rows = {}
    for run in runs:
        rows[run["problem"]] = {
            method: float(np.mean([r[key][metric] for r in seeds]))
            for method, seeds in run["runs"].items()
        }
    return pd.DataFrame(rows).T


def fixed_threshold(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """P1: the median F1 of each detector at the label-free threshold against the prevalence one."""
    table = {}
    for method in sorted({m for r in runs for m in r["runs"]}):
        entry = {}
        for metric in METRICS:
            prev = per_problem(runs, "metrics", metric)[method].dropna()
            fixed = per_problem(runs, "fixed", metric)[method].dropna()
            entry[metric] = {"prevalence": float(prev.median()), "fixed": float(fixed.median())}
        table[method] = entry
    lower = [m for m, e in table.items() if e["f1"]["fixed"] < e["f1"]["prevalence"]]
    return {
        "supported": bool(len(lower) >= 12),
        "lower_at_fixed": len(lower),
        "detectors": len(table),
        "by_detector": table,
    }


def curve_ranking(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """P2: the rank of the detectors by the average precision of the curves of seed 42."""
    ap: dict[str, dict[str, float]] = {}
    for run in runs:
        for method, seeds in run["runs"].items():
            for row in seeds:
                if "curve" in row:
                    ap.setdefault(method, {})[run["problem"]] = row["curve"]["average_precision"]
    curves = pd.DataFrame(ap).median()
    pooled = per_problem(runs, "metrics", "pr_auc").median()
    common = curves.index.intersection(pooled.index)
    rho = float(spearmanr(curves[common], pooled[common]).statistic)
    return {
        "supported": bool(round(rho, 9) >= 0.99),
        "spearman": rho,
        "median_ap": curves.to_dict(),
    }


def contamination_sweep(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Isolation Forest over the contamination grid: median precision, recall, F1, flagged share."""
    out: dict[str, dict[str, float]] = {}
    for value in GRID:
        cells = {m: [] for m in METRICS}
        for run in runs:
            seeds = run["runs"].get("isolation_forest", [])
            rows = [r["sweep"][value] for r in seeds if "sweep" in r]
            if rows:
                for m in METRICS:
                    cells[m].append(float(np.mean([r[m] for r in rows])))
        out[value] = {m: float(np.median(v)) for m, v in cells.items()}
    return out


def timings(runs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Median detection time (fit, predict and score) over the problems, per detector."""
    rows: dict[str, list[float]] = {}
    for run in runs:
        for method, seeds in run["runs"].items():
            rows.setdefault(method, []).append(
                float(np.mean([r["fit_s"] + r["predict_s"] + r["score_s"] for r in seeds]))
            )
    return {
        m: {"median_s": float(np.median(v)), "max_s": float(np.max(v))} for m, v in rows.items()
    }


def severity(runs_dirs: Path | list[Path]) -> dict[str, Any]:
    """P3: median over tables of the multivariate recall at severity 4 against 0.5."""
    cells: dict[str, dict[str, list[float]]] = {}
    folders = [runs_dirs] if isinstance(runs_dirs, Path) else runs_dirs
    for path in sorted(p for folder in folders for p in folder.glob("*.json")):
        run = json.loads(path.read_text())
        for sev, payload in run["recall_by_severity"].items():
            frame = pd.DataFrame(payload["data"], payload["index"], payload["columns"])
            for method in frame.index:
                cells.setdefault(method, {}).setdefault(sev, []).append(
                    float(frame.loc[method, "multivariate_outlier"])
                )
    median = {m: {s: float(np.nanmedian(v)) for s, v in by.items()} for m, by in cells.items()}
    learned = [m for m in median if m not in {"transform_dedup", "drift"}]
    higher = [m for m in learned if median[m]["4.0"] > median[m]["0.5"]]
    return {
        "supported": bool(learned and len(higher) == len(learned)),
        "detectors": len(learned),
        "higher_at_4": len(higher),
        "median_multivariate_recall": median,
    }


def severity_rows(median: dict[str, dict[str, float]], names: dict[str, str]) -> str:
    """LaTeX rows: median multivariate recall at the four severity multipliers."""
    return "\n".join(
        f"{label:<18} & "
        + " & ".join(f"{median[m][s]:.2f}" for s in ("0.5", "1.0", "2.0", "4.0"))
        + " \\\\"
        for m, label in names.items()
    )


def pipeline(records: list[dict[str, Any]], large: int = 50_000) -> dict[str, Any]:
    """P4: detection share of the pipeline time on the datasets above ``large`` rows."""
    ok = [r for r in records if r["status"] == "OK"]
    big = [r for r in ok if r["rows_after_transform"] > large]
    share = {
        method: [r["detect_stage_share"] for r in big if r["method"] == method]
        for method in ("zscore", "isolation_forest")
    }
    median = {m: float(np.median(v)) if v else float("nan") for m, v in share.items()}
    return {
        "supported": bool(
            share["isolation_forest"]
            and share["zscore"]
            and median["isolation_forest"] > 0.30
            and median["zscore"] < 0.10
        ),
        "datasets_above": len({r["id"] for r in big}),
        "median_detect_share": median,
        "failed": [r["id"] for r in records if r["status"] != "OK"],
    }


def chronology(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """P5: the chronological PR-AUC below the stratified one for two thirds of the pairs."""
    pairs = lower = 0
    by_dataset = {}
    for name, result in results.items():
        if "excluded" in result:
            by_dataset[name] = {"excluded": result["excluded"]}
            continue
        count = sum(
            result["chronological"][m]["pr_auc"] < result["stratified"][m]["pr_auc"]
            for m in result["chronological"]
        )
        by_dataset[name] = {"lower": int(count), "detectors": len(result["chronological"])}
        pairs += len(result["chronological"])
        lower += count
    return {
        "supported": bool(pairs and lower >= 2 * pairs / 3),
        "lower": int(lower),
        "pairs": int(pairs),
        "by_dataset": by_dataset,
    }


def contract(report: dict[str, Any]) -> dict[str, Any]:
    """P6: no pool file differs from the manifest."""
    return {"supported": bool(report["summary"]["all_ok"]), **report["summary"]}


def fixed_rows(table: dict[str, Any], names: dict[str, str]) -> str:
    """LaTeX rows: median F1 and flagged share at the prevalence and at the fixed threshold."""
    lines = []
    for method, label in names.items():
        e = table["by_detector"][method]
        lines.append(
            f"{label:<18} & {e['f1']['prevalence']:.3f} & {e['f1']['fixed']:.3f} "
            f"& {e['flagged_pct']['prevalence']:.1f} & {e['flagged_pct']['fixed']:.1f} \\\\"
        )
        if method in ("great_expectations", "pca"):
            lines.append(r"\midrule")
    return "\n".join(lines)


def sweep_rows(sweep: dict[str, Any]) -> str:
    """LaTeX rows of the Isolation Forest contamination grid."""
    return "\n".join(
        f"{float(c):.3f} & {v['precision']:.3f} & {v['recall']:.3f} & {v['f1']:.3f} "
        f"& {v['flagged_pct']:.1f} \\\\"
        for c, v in sweep.items()
    )


def _short(reason: str) -> str:
    return reason.replace(" anomalies in the test partition (at least 20)", " test anomalies")


def chrono_rows(results: dict[str, dict[str, Any]], labels: dict[str, str]) -> str:
    """LaTeX rows of the chronological study: partitions, prevalence shift, lower pairs."""
    lines = []
    for name, label in labels.items():
        result = results[name]
        if "excluded" in result:
            lines.append(
                f"{label} & \\multicolumn{{4}}{{l}}{{excluded: {_short(result['excluded'])}}} \\\\"
            )
            continue
        part = result["partitions"]
        lower = sum(
            result["chronological"][m]["pr_auc"] < result["stratified"][m]["pr_auc"]
            for m in result["chronological"]
        )
        lines.append(
            f"{label} & {part['test']['positives']} "
            f"& {100 * part['train']['prevalence']:.1f} & {100 * part['test']['prevalence']:.1f} "
            f"& {lower} of {len(result['chronological'])} \\\\"
        )
    return "\n".join(lines)
