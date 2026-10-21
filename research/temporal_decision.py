"""Decisions under temporal shift: threshold policies and a prevalence-matched control (#63).

Protocol: verification/temporal_decision.md.
"""

from __future__ import annotations

import os

os.environ.setdefault("TQDM_DISABLE", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

from etl_benchmark import config  # noqa: E402
from etl_benchmark.registry import clip_contamination, get_detector  # noqa: E402

METHODS = ["zscore", "iqr", "great_expectations", "isolation_forest"]
POLICIES = ("P0", "P1", "P2")
BLOCKS, BOOT_BLOCKS, RESAMPLES, BOOT_SEED = 20, 50, 1000, 42


def thresholds(s_train, s_val, s_test, pi: float, blocks: int = BLOCKS) -> dict[str, np.ndarray]:
    """Per-row thresholds of the test rows for the three policies (no label of the test period)."""
    q = 1.0 - pi
    n = len(s_test)
    edges = np.linspace(0, n, blocks + 1).round().astype(int)
    stream = np.concatenate([s_val, s_test])
    offset = len(s_val)
    p2 = np.empty(n)
    for b in range(blocks):
        lo, hi = edges[b], edges[b + 1]
        size = max(hi - lo, 1)
        end = offset + lo
        history = stream[max(0, end - 2 * size) : end]
        p2[lo:hi] = np.quantile(history, q)
    return {
        "P0": np.full(n, np.quantile(s_train, q)),
        "P1": np.full(n, np.quantile(s_val, q)),
        "P2": p2,
    }


def decision_metrics(y, scores, thr) -> dict[str, float]:
    y = np.asarray(y).astype(int)
    flags = np.asarray(scores) > np.asarray(thr)
    tp, fp = int((flags & (y == 1)).sum()), int((flags & (y == 0)).sum())
    fn, tn = int((~flags & (y == 1)).sum()), int((~flags & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "flagged_share": float(flags.mean()),
    }


def match_prevalence(y, target: float, rng: np.random.Generator) -> np.ndarray:
    """Indices of a subsample of ``y`` whose positive share is ``target`` (drops one class)."""
    y = np.asarray(y)
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    if len(pos) / len(y) > target:
        keep = max(int(round(target / (1 - target) * len(neg))), 1)
        pos = rng.choice(pos, size=min(keep, len(pos)), replace=False)
    else:
        keep = max(int(round((1 - target) / target * len(pos))), 1)
        neg = rng.choice(neg, size=min(keep, len(neg)), replace=False)
    return np.sort(np.concatenate([pos, neg]))


def _scores(method: str, pi: float, train: pd.DataFrame, parts: list[pd.DataFrame]):
    det = get_detector(method, clip_contamination(pi))
    det.fit(train)
    return [det.score(p).to_numpy(dtype=float) for p in parts]


def _block_ci(y, scores) -> dict[str, float]:
    n = len(y)
    edges = np.linspace(0, n, BOOT_BLOCKS + 1).round().astype(int)
    members = [np.arange(edges[b], edges[b + 1]) for b in range(BOOT_BLOCKS)]
    rng = np.random.default_rng(BOOT_SEED)
    values = []
    for _ in range(RESAMPLES):
        index = np.concatenate([members[k] for k in rng.integers(0, BOOT_BLOCKS, BOOT_BLOCKS)])
        if y[index].min() != y[index].max():
            values.append(average_precision_score(y[index], scores[index]))
    low, high = np.percentile(values, [2.5, 97.5])
    return {"ci_low": float(low), "ci_high": float(high), "resamples_used": len(values)}


def _describe(y) -> dict[str, float]:
    return {"rows": int(len(y)), "positives": int(np.sum(y)), "prevalence": float(np.mean(y))}


def run_frame(
    x: pd.DataFrame,
    y,
    times: pd.Series,
    methods: list[str] | None = None,
    seeds: tuple[int, ...] = config.BENCHMARK_SEEDS,
) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    methods = methods or METHODS
    y = np.asarray(y).astype(int)
    order = np.argsort(pd.to_datetime(times, utc=True).to_numpy(), kind="stable")
    x, y = x.iloc[order].reset_index(drop=True), y[order]
    n = len(y)
    a, b = int(n * 0.70), int(n * 0.85)
    tr, va, te = np.arange(a), np.arange(a, b), np.arange(b, n)
    pi = float(y[tr].mean())
    out: dict[str, Any] = {
        "partitions": {
            k: _describe(y[i]) for k, i in (("train", tr), ("validation", va), ("test", te))
        },
        "chronological": {},
        "stratified": {},
    }
    pi_test = float(y[te].mean())
    for method in methods:
        s_tr, s_va, s_te = _scores(method, pi, x.iloc[tr], [x.iloc[tr], x.iloc[va], x.iloc[te]])
        thr = thresholds(s_tr, s_va, s_te, pi)
        policies = {}
        for name in POLICIES:
            m = decision_metrics(y[te], s_te, thr[name])
            m["share_error"] = float(abs(np.log(max(m["flagged_share"], 1e-6) / pi)))
            policies[name] = m
        out["chronological"][method] = {
            "pr_auc": float(average_precision_score(y[te], s_te)),
            "roc_auc": float(roc_auc_score(y[te], s_te)),
            "pr_ci": {
                "estimate": float(average_precision_score(y[te], s_te)),
                **_block_ci(y[te], s_te),
            },
            "policies": policies,
        }
        rows: dict[str, list[float]] = {"pr_auc": [], "roc_auc": [], "pr_auc_matched": []}
        for seed in seeds:
            idx = np.arange(n)
            s_train, rest = train_test_split(idx, train_size=0.70, stratify=y, random_state=seed)
            _s_val, s_test = train_test_split(
                rest, train_size=0.5, stratify=y[rest], random_state=seed
            )
            pi_s = float(y[s_train].mean())
            (sc,) = _scores(method, pi_s, x.iloc[s_train], [x.iloc[s_test]])
            rows["pr_auc"].append(float(average_precision_score(y[s_test], sc)))
            rows["roc_auc"].append(float(roc_auc_score(y[s_test], sc)))
            keep = match_prevalence(y[s_test], pi_test, np.random.default_rng(seed))
            rows["pr_auc_matched"].append(float(average_precision_score(y[s_test][keep], sc[keep])))
        out["stratified"][method] = {k: float(np.mean(v)) for k, v in rows.items()} | {
            f"{k}_std": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0 for k, v in rows.items()
        }
    return out


def hypotheses(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    h1, h2, h3, h4 = {}, {}, {}, {}
    wins = total = 0
    for name, r in results.items():
        methods = list(r["chronological"])
        strat = [r["stratified"][m]["pr_auc"] for m in methods]
        chrono = [r["chronological"][m]["pr_auc"] for m in methods]
        h1[name] = float(spearmanr(strat, chrono).statistic)
        med = {
            p: float(
                np.median([r["chronological"][m]["policies"][p]["share_error"] for m in methods])
            )
            for p in POLICIES
        }
        h2[name] = {"median_share_error": med, "ok": bool(med["P2"] < med["P1"] < med["P0"])}
        for m in methods:
            pol = r["chronological"][m]["policies"]
            wins += pol["P2"]["f1"] >= pol["P0"]["f1"]
            total += 1
        gap_strat = float(
            np.median(
                [
                    abs(r["stratified"][m]["pr_auc"] - r["chronological"][m]["pr_auc"])
                    for m in methods
                ]
            )
        )
        gap_matched = float(
            np.median(
                [
                    abs(r["stratified"][m]["pr_auc_matched"] - r["chronological"][m]["pr_auc"])
                    for m in methods
                ]
            )
        )
        h4[name] = {
            "gap_stratified": gap_strat,
            "gap_matched": gap_matched,
            "ok": bool(gap_matched <= 0.5 * gap_strat),
        }
    h3 = {"p2_at_least_p0": int(wins), "pairs": int(total)}
    return {
        "H1": {"supported": all(round(v, 9) >= 0.8 for v in h1.values()), "spearman": h1},
        "H2": {"supported": all(v["ok"] for v in h2.values()), "by_dataset": h2},
        "H3": {"supported": wins >= total / 2, **h3},
        "H4": {"supported": all(v["ok"] for v in h4.values()), "by_dataset": h4},
    }


def credit_card() -> tuple[pd.DataFrame, np.ndarray, pd.Series]:
    import temporal_pilot as tp

    from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS

    spec = DATASETS["credit_card"]
    frame = tp.load(spec).sort_values(tp.TIME_UTC, kind="stable")
    return (
        tp.features(spec, frame).reset_index(drop=True),
        frame[ANOMALY_COLUMN].to_numpy(),
        frame[tp.TIME_UTC].reset_index(drop=True),
    )


def bank_marketing(path: Path) -> tuple[pd.DataFrame, np.ndarray, pd.Series]:
    import uci_loader as ul

    frame = ul.read_table(path)
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    index = frame["month"].map(months.index).to_numpy()
    year = 2008 + np.cumsum(np.r_[0, np.diff(index) < 0])
    within = frame.groupby([year, index]).cumcount().to_numpy()
    times = pd.to_datetime(
        pd.DataFrame({"year": year, "month": index + 1, "day": 1})
    ).dt.tz_localize("UTC") + pd.to_timedelta(within, unit="min")
    y = (frame["y"] == "yes").to_numpy().astype(int)
    features = frame.drop(columns=["y", "month"])
    cats = [c for c in features if not pd.api.types.is_numeric_dtype(features[c])]
    features = pd.get_dummies(features, columns=cats, dummy_na=True, dtype=float)
    return features, y, times


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bank", type=Path, default=ROOT / "data" / "pool" / "222.csv")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    args.output.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for name, loader in (
        ("credit_card", credit_card),
        ("bank_marketing", lambda: bank_marketing(args.bank)),
    ):
        x, y, times = loader()
        results[name] = run_frame(x, y, times)
        print(name, flush=True)
    results_all = {"datasets": results, "hypotheses": hypotheses(results)}
    with atomic_path(args.output / "temporal_decision_results.json") as partial:
        partial.write_text(json.dumps(results_all, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
