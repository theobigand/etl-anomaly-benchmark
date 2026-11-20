"""Summary of the chronological study with controlled injection (verification/chrono_injected.md).

The unit is the table. For each detector the paired difference (chronological minus random) of
the false-positive rate and of the mean recall is taken per table, then summarised over tables
with a bootstrap interval; hypotheses C1 to C3 are evaluated on those differences.
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


SEED, DRAWS = 2026, 5000


def load(folder: Path) -> dict[str, dict[str, Any]]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))}


def _mean_recall(arm: dict[str, Any], method: str) -> float:
    return float(np.mean(list(arm["recall"][method].values())))


def _cell(median: float, ci: list[float]) -> str:
    return f"{median:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]"


def paired(runs: dict[str, dict[str, Any]]) -> dict[str, dict[str, np.ndarray]]:
    """Per detector: per-table FPR and mean-recall differences, chronological minus random."""
    methods = sorted(next(iter(runs.values()))["arms"]["random"]["fpr"])
    out: dict[str, dict[str, np.ndarray]] = {}
    for m in methods:
        d_fpr, d_rec = [], []
        for run in runs.values():
            c, r = run["arms"]["chronological"], run["arms"]["random"]
            d_fpr.append(c["fpr"][m] - r["fpr"][m])
            d_rec.append(
                np.mean(list(c["recall"][m].values())) - np.mean(list(r["recall"][m].values()))
            )
        out[m] = {"fpr": np.array(d_fpr), "recall": np.array(d_rec)}
    return out


def interval(values: np.ndarray, seed: int = SEED, draws: int = DRAWS) -> list[float]:
    rng = np.random.default_rng(seed)
    boot = np.median(rng.choice(values, (draws, len(values))), axis=1)
    return [float(x) for x in np.quantile(boot, [0.025, 0.975])]


def ranking_agreement(runs: dict[str, dict[str, Any]]) -> float:
    """Mean over tables of the rank correlation of detector mean recall between the arms."""
    scores = []
    for run in runs.values():
        arms = {a: run["arms"][a]["recall"] for a in ("chronological", "random")}
        methods = sorted(arms["random"])
        x = [np.mean(list(arms["chronological"][m].values())) for m in methods]
        y = [np.mean(list(arms["random"][m].values())) for m in methods]
        scores.append(spearmanr(x, y).statistic)
    return float(np.nanmean(scores))


def summarise(folder: Path) -> dict[str, Any]:
    return summarise_runs(load(folder))


def summarise_runs(runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    diffs = paired(runs)
    rows = {
        m: {
            "fpr_median_difference": float(np.median(v["fpr"])),
            "fpr_ci": interval(v["fpr"]),
            "recall_median_difference": float(np.median(v["recall"])),
            "recall_ci": interval(v["recall"]),
            "tables_fpr_higher": int((v["fpr"] > 0).sum()),
        }
        for m, v in diffs.items()
    }
    fpr_all = np.array([r["fpr_median_difference"] for r in rows.values()])
    rec_all = np.array([r["recall_median_difference"] for r in rows.values()])
    return {
        "tables": sorted(r["id"] for r in runs.values()),
        "n_tables": len(runs),
        "detectors": rows,
        "C1_median_detector_fpr_difference": float(np.median(fpr_all)),
        "C2_median_detector_recall_difference": float(np.median(rec_all)),
        "C2_abs_recall_smaller_than_fpr": bool(abs(np.median(rec_all)) < abs(np.median(fpr_all))),
        "C3_mean_rank_correlation": ranking_agreement(runs),
    }


def report(s: dict[str, Any]) -> str:
    lines = [
        "# Chronological study with controlled injection",
        "",
        f"{s['n_tables']} real time-series tables. Differences are chronological minus random.",
        "",
        "| detector | FPR difference (median, 95% CI) | recall difference | higher FPR |",
        "|---|---|---|---|",
    ]
    for m, r in s["detectors"].items():
        fpr = _cell(r["fpr_median_difference"], r["fpr_ci"])
        rec = _cell(r["recall_median_difference"], r["recall_ci"])
        lines.append(f"| {m} | {fpr} | {rec} | {r['tables_fpr_higher']}/{s['n_tables']} |")
    lines += [
        "",
        f"C1 median detector FPR difference: {s['C1_median_detector_fpr_difference']:+.4f}",
        f"C2 median detector recall difference: {s['C2_median_detector_recall_difference']:+.4f}"
        f" (smaller in magnitude than the FPR difference: {s['C2_abs_recall_smaller_than_fpr']})",
        f"C3 mean rank correlation of detector recall between the arms: "
        f"{s['C3_mean_rank_correlation']:.2f}",
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
    print(report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
