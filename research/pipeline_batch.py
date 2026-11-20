"""Batch-level ETL pipeline fault detection on replayed real tables.

Protocol: verification/pipeline_batch_faults.md.

A timestamped table is replayed in time order as successive loads (batches). Eight pipeline fault
mechanisms are injected into some test batches; every detector scores each batch from a profile
computed against the reference batches only, and is evaluated at a label-free alert budget.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import ks_2samp  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

PROTOCOL = "pipeline-batch-v1"
SEEDS = (42, 1, 2, 3, 4)
ALERT_BUDGET = 0.05
FAULT_SHARE = 0.30
CONTAMINATION_SHARE = 0.05
REFERENCE_SHARE, VALIDATION_SHARE = 0.40, 0.20
MIN_BATCH, TARGET_BATCHES, MIN_REFERENCE_FOR_NEURAL = 24, 100, 200
KS_SAMPLE = 2000
TIME = "_t"
MECHANISMS = (
    "partial_load",
    "duplicate_load",
    "stale_batch",
    "null_spike",
    "schema_drop",
    "unit_change",
    "distribution_shift",
    "silent_corruption",
)
LEVELS = (0, 1, 2)  # low, medium, high
SEVERITY = {
    "partial_load": (0.7, 0.4, 0.1),  # share of rows kept
    "duplicate_load": (0.2, 0.5, 1.0),  # share of rows repeated
    "stale_batch": (1, 3, 10),  # loads back
    "null_spike": (0.1, 0.3, 1.0),  # share of one column missing
    "schema_drop": (1, 2, -1),  # columns absent (-1: one third)
    "unit_change": (2.0, 10.0, 1000.0),  # scale factor
    "distribution_shift": (0.5, 1.0, 2.0),  # reference standard deviations
    "silent_corruption": (0.2, 0.5, 1.0),  # share of rows permuted
}
LEARNED = ("isolation_forest", "ecod", "copod", "hbos", "pca", "knn", "lof")
RULE_DETECTORS = ("constraint_rules", "volume_freshness")
STATISTICAL = ("distribution_distance",)
DETECTORS = (*RULE_DETECTORS, *STATISTICAL, *LEARNED, "random")
FAMILY = {
    **dict.fromkeys(RULE_DETECTORS, "rules"),
    **dict.fromkeys(STATISTICAL, "statistical"),
    **dict.fromkeys(LEARNED, "learned"),
    "random": "floor",
}
WIDEN, SHARE_FLOOR, RATIO_FLOOR = 0.20, 0.02, 0.10


def batch_size(n_rows: int) -> int:
    return max(MIN_BATCH, n_rows // TARGET_BATCHES)


def make_batches(table: pd.DataFrame) -> list[pd.DataFrame]:
    """Consecutive equal-size batches in time order; the remainder rows are dropped."""
    k = batch_size(len(table))
    return [table.iloc[i * k : (i + 1) * k].reset_index(drop=True) for i in range(len(table) // k)]


def split_batches(n: int) -> tuple[range, range, range]:
    a, b = int(n * REFERENCE_SHARE), int(n * (REFERENCE_SHARE + VALIDATION_SHARE))
    return range(0, a), range(a, b), range(b, n)


def value_columns(batch: pd.DataFrame) -> list[str]:
    return [c for c in batch.columns if c != TIME]


def apply_fault(
    batch: pd.DataFrame,
    mechanism: str,
    level: int,
    rng: np.random.Generator,
    *,
    history: list[pd.DataFrame],
    sd: pd.Series,
) -> pd.DataFrame:
    """The batch as delivered after one fault; ``history`` holds the clean earlier batches."""
    if mechanism not in SEVERITY:
        raise ValueError(f"unknown mechanism {mechanism}")
    value = SEVERITY[mechanism][level]
    out = batch.copy()
    columns = value_columns(batch)
    n = len(out)
    if mechanism == "partial_load":
        keep = max(2, int(round(n * value)))
        return out.iloc[np.sort(rng.choice(n, keep, replace=False))].reset_index(drop=True)
    if mechanism == "duplicate_load":
        extra = max(1, int(round(n * value)))
        rows = out.iloc[rng.choice(n, extra, replace=extra > n)]
        return pd.concat([out, rows], ignore_index=True)
    if mechanism == "stale_batch":
        lag = min(int(value), len(history))
        return history[-lag].copy() if lag else out
    column = columns[int(rng.integers(len(columns)))]
    if mechanism == "null_spike":
        hit = rng.choice(n, max(1, int(round(n * value))), replace=False)
        out.loc[out.index[hit], column] = np.nan
        return out
    if mechanism == "schema_drop":
        count = max(1, len(columns) // 3) if value < 0 else min(int(value), len(columns) - 1)
        drop = list(rng.choice(columns, count, replace=False))
        return out.drop(columns=drop)
    if mechanism == "unit_change":
        out[column] = out[column] * value
        return out
    if mechanism == "distribution_shift":
        out[column] = out[column] + value * float(sd[column])
        return out
    if mechanism == "silent_corruption":
        chosen = list(rng.choice(columns, min(2, len(columns)), replace=False))
        rows = np.sort(rng.choice(n, max(2, int(round(n * value))), replace=False))
        for name in chosen:
            out.loc[out.index[rows], name] = rng.permutation(
                out.loc[out.index[rows], name].to_numpy()
            )
        return out
    raise AssertionError(mechanism)  # unreachable: every known mechanism returns above


class Reference:
    """Statistics of the reference batches only; everything a profile is read against."""

    def __init__(self, batches: list[pd.DataFrame]):
        self.columns = value_columns(batches[0])
        pooled = pd.concat(batches, ignore_index=True)
        self.sd = pooled[self.columns].std(ddof=0).replace(0, 1.0)
        self.rows = float(np.median([len(b) for b in batches]))
        ends = np.array([b[TIME].max().value for b in batches], dtype=float)
        gaps = np.diff(ends)
        self.lag = float(np.median(gaps)) if len(gaps) and np.median(gaps) > 0 else 1.0
        self.corr = pooled[self.columns].corr().fillna(0.0).to_numpy()
        rng = np.random.default_rng(0)
        self.sample = {
            c: pooled[c].dropna().to_numpy()[rng.permutation(pooled[c].notna().sum())[:KS_SAMPLE]]
            for c in self.columns
        }
        raw = pd.DataFrame(
            [self.raw(b, batches[i - 1] if i else None) for i, b in enumerate(batches)]
        )
        self.raw_reference = raw
        self.mean, self.std = raw.mean(), raw.std(ddof=0).replace(0, 1.0).fillna(1.0)
        self.lo, self.hi = raw.min(), raw.max()

    def raw(self, batch: pd.DataFrame, previous: pd.DataFrame | None) -> dict[str, float]:
        """Raw profile features of one delivered batch (previous: the batch delivered before)."""
        present = [c for c in self.columns if c in batch.columns]
        row: dict[str, float] = {
            "rows": len(batch) / self.rows,
            "dup_share": float(batch[present].duplicated().mean())
            if present and len(batch)
            else 0.0,
            "absent": float(len(self.columns) - len(present)),
        }
        if previous is None:
            row["repeat_prev"], row["lag"] = 0.0, 1.0
        else:
            both = [c for c in present if c in previous.columns]
            seen = set(map(tuple, previous[both].round(9).to_numpy())) if both else set()
            keys = list(map(tuple, batch[both].round(9).to_numpy())) if both else []
            row["repeat_prev"] = float(np.mean([k in seen for k in keys])) if keys else 0.0
            gap = batch[TIME].max().value - previous[TIME].max().value
            row["lag"] = float(gap) / self.lag
        for c in self.columns:
            if c not in batch.columns:
                row[f"null_{c}"] = 1.0
                row.update({f"{s}_{c}": np.nan for s in ("mean", "std", "q05", "q50", "q95", "ks")})
                continue
            values = batch[c]
            row[f"null_{c}"] = float(values.isna().mean())
            clean = values.dropna()
            if clean.empty:
                row.update({f"{s}_{c}": np.nan for s in ("mean", "std", "q05", "q50", "q95", "ks")})
                continue
            q = clean.quantile([0.05, 0.5, 0.95]).to_numpy()
            row.update(
                {
                    f"mean_{c}": float(clean.mean()),
                    f"std_{c}": float(clean.std(ddof=0)),
                    f"q05_{c}": float(q[0]),
                    f"q50_{c}": float(q[1]),
                    f"q95_{c}": float(q[2]),
                    f"ks_{c}": float(ks_2samp(clean.to_numpy(), self.sample[c]).statistic),
                }
            )
        if len(present) >= 2 and len(batch) > 2:
            local = batch[present].corr().fillna(0.0).to_numpy()
            index = [self.columns.index(c) for c in present]
            row["corr_dist"] = float(np.abs(local - self.corr[np.ix_(index, index)]).mean())
        else:
            row["corr_dist"] = np.nan
        return row

    def standardise(self, raw: pd.DataFrame) -> pd.DataFrame:
        return (raw[self.mean.index] - self.mean) / self.std


def profile_stream(
    ref: Reference, batches: list[pd.DataFrame], first_previous: pd.DataFrame | None
):
    """Raw profiles of delivered batches, each against the batch delivered before it."""
    rows, previous = [], first_previous
    for b in batches:
        rows.append(ref.raw(b, previous))
        previous = b
    return pd.DataFrame(rows).reindex(columns=ref.mean.index)


def constraint_scores(ref: Reference, raw: pd.DataFrame) -> np.ndarray:
    """Largest normalised excess over declarative constraints learned from the reference batches.

    Allowed interval of a feature: the reference range widened by 20 % of its width plus a floor
    (0.02 for shares, 0.10 for ratios, 0.5 for the absent-column count). Zero means no violation.
    """
    names = [
        "rows", "dup_share", "repeat_prev", "lag", "absent",
        *[f"null_{c}" for c in ref.columns], *[f"mean_{c}" for c in ref.columns],
    ]  # fmt: skip
    excess = np.zeros((len(raw), len(names)))
    for j, name in enumerate(names):
        lo, hi = float(ref.lo[name]), float(ref.hi[name])
        floor = (
            0.5
            if name == "absent"
            else RATIO_FLOOR
            if name in ("rows", "lag")
            else SHARE_FLOOR
            if name.startswith(("null_", "dup_", "repeat_"))
            else 0.0
        )
        slack = WIDEN * (hi - lo) + floor
        low, high = lo - slack, hi + slack
        half = max(0.5 * (high - low), 1e-12)
        x = raw[name].to_numpy(dtype=float)
        over = np.where(np.isnan(x), 0.0, np.maximum(low - x, x - high))
        excess[:, j] = np.maximum(over, 0.0) / half
    return excess.max(axis=1)


def detector_scores(
    name: str, ref: Reference, raw: pd.DataFrame, fitted: dict[str, Any], seed: int
) -> np.ndarray:
    z = ref.standardise(raw)
    if name == "constraint_rules":
        return constraint_scores(ref, raw)
    if name == "volume_freshness":
        return np.nanmax(np.abs(z[["rows", "lag"]].to_numpy()), axis=1)
    if name == "distribution_distance":
        ks = z[[f"ks_{c}" for c in ref.columns]].to_numpy()
        return np.nanmax(np.where(np.isnan(ks), 0.0, ks), axis=1)
    if name == "random":
        return np.random.default_rng(seed).random(len(raw))
    return fitted[name].score(z).to_numpy(dtype=float)


def fit_learned(ref: Reference, seed: int, names: tuple[str, ...] = LEARNED) -> dict[str, Any]:
    from deep_support import build

    z = ref.standardise(ref.raw_reference)
    fitted = {}
    for name in names:
        detector = build(name, 0.05, seed)
        detector.fit(z)
        fitted[name] = detector
    return fitted


def alert_metrics(
    val_scores: np.ndarray, scores: np.ndarray, faulty: np.ndarray
) -> dict[str, float]:
    """ROC-AUC, average precision, recall and clean false-alert rate at the validation budget."""
    threshold = float(np.quantile(val_scores, 1.0 - ALERT_BUDGET))
    flags = scores > threshold
    out = {
        "recall": float(flags[faulty].mean()),
        "false_alert_rate": float(flags[~faulty].mean()),
    }
    if faulty.any() and (~faulty).any():
        out["roc_auc"] = float(roc_auc_score(faulty, scores))
        out["ap"] = float(average_precision_score(faulty, scores))
    return out


def deliver(
    clean: list[pd.DataFrame],
    indices: range,
    mechanism: str | None,
    level: int,
    rng: np.random.Generator,
    ref: Reference,
    share: float = FAULT_SHARE,
) -> tuple[list[pd.DataFrame], np.ndarray]:
    """The test stream with a share of its batches faulted by one mechanism, and the truth mask."""
    faulty = np.zeros(len(indices), dtype=bool)
    if mechanism is not None:
        count = max(1, int(round(share * len(indices))))
        faulty[rng.choice(len(indices), count, replace=False)] = True
    out = []
    for position, i in enumerate(indices):
        if faulty[position]:
            out.append(apply_fault(clean[i], mechanism, level, rng, history=clean[:i], sd=ref.sd))
        else:
            out.append(clean[i])
    return out, faulty


def run_source(
    table: pd.DataFrame, seeds: tuple[int, ...] = SEEDS, contaminated: bool = False,
    learned: tuple[str, ...] = LEARNED,
) -> dict[str, Any]:  # fmt: skip
    """All mechanisms, severities and detectors on one replayed table (with a time column)."""
    warnings.filterwarnings("ignore")
    clean = make_batches(table)
    ref_idx, val_idx, test_idx = split_batches(len(clean))
    reference = [clean[i] for i in ref_idx]
    if contaminated:  # a production history that already holds faults, unlabelled to the detectors
        rng = np.random.default_rng(7)
        pre = Reference(reference)
        picks = rng.choice(
            len(reference), max(1, int(round(CONTAMINATION_SHARE * len(reference)))), replace=False
        )
        for i in picks:
            m = MECHANISMS[int(rng.integers(len(MECHANISMS)))]
            reference[i] = apply_fault(
                reference[i], m, int(rng.integers(3)), rng, history=reference[:i], sd=pre.sd
            )
    ref = Reference(reference)
    names = tuple(learned)
    active = [d for d in DETECTORS if d not in LEARNED or d in names]
    cells: dict[str, dict[str, dict[str, list[dict[str, float]]]]] = {
        d: {m: {str(lv): [] for lv in LEVELS} for m in MECHANISMS} for d in DETECTORS
    }
    first = clean[val_idx[0] - 1]
    val_raw = profile_stream(ref, [clean[i] for i in val_idx], first)
    for seed in seeds:
        fitted = fit_learned(ref, seed, names)
        val = {d: detector_scores(d, ref, val_raw, fitted, seed) for d in active}
        for mechanism in MECHANISMS:
            for level in LEVELS:
                rng = np.random.default_rng([seed, MECHANISMS.index(mechanism), level])
                stream, faulty = deliver(clean, test_idx, mechanism, level, rng, ref)
                raw = profile_stream(ref, stream, clean[test_idx[0] - 1])
                for d in active:
                    scores = detector_scores(d, ref, raw, fitted, seed)
                    cells[d][mechanism][str(level)].append(alert_metrics(val[d], scores, faulty))
    results = {
        d: {
            m: {
                lv: {
                    k: float(np.mean([r[k] for r in rows if k in r]))
                    for k in ("recall", "false_alert_rate", "roc_auc", "ap")
                    if any(k in r for r in rows)
                }
                for lv, rows in by_level.items()
                if rows
            }
            for m, by_level in by_mech.items()
        }
        for d, by_mech in cells.items()
        if d in active
    }
    return {
        "protocol": PROTOCOL,
        "contaminated_reference": contaminated,
        "batch_rows": batch_size(len(table)),
        "batches": {"reference": len(ref_idx), "validation": len(val_idx), "test": len(test_idx)},
        "faulty_test_batches": max(1, int(round(FAULT_SHARE * len(test_idx)))),
        "seeds": list(seeds),
        "features": int(len(ref.mean)),
        "detectors": active,
        "neural": "not run: fewer than MIN_REFERENCE_FOR_NEURAL reference batches"
        if len(reference) < MIN_REFERENCE_FOR_NEURAL
        else "not run in this pilot",
        "results": results,
    }


def load_table(uci_id: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    """A real timestamped table: continuous columns plus its parsed time, sorted by time."""
    import chrono_injected as ci
    import injection as inj
    import uci_loader as ul

    meta = {
        m["uci_id"]: m
        for m in json.loads(
            (ROOT / "verification/evidence/dataset_registry/uci_curated.json").read_text()
        )["kept"]
    }[uci_id]
    frame = ul.read_table(ROOT / "data" / "pool" / f"{uci_id}.csv")
    stamps, used = ci.parse_time(frame, ci.TIME_SPECS[uci_id])
    if stamps.isna().any():
        raise inj.NotEligible(f"{int(stamps.isna().sum())} timestamps could not be read")
    features, _ = ul.split_columns(frame, meta)
    features = features.drop(columns=[c for c in used if c in features.columns])
    features = features.drop(columns=ci.trend_columns(features, stamps))
    columns = inj.continuous_columns(features)
    if len(columns) < ci.MIN_COLUMNS:
        raise inj.NotEligible(f"only {len(columns)} continuous columns")
    table = (features[columns] * 1.0).assign(**{TIME: pd.to_datetime(stamps.to_numpy())})
    table = table.sort_values(TIME, kind="stable").dropna().drop_duplicates(subset=columns)
    table = table.reset_index(drop=True)
    if len(table) < ci.MIN_ROWS:
        raise inj.NotEligible(f"only {len(table)} rows after cleaning")
    return table, {"name": meta["name"], "rows": len(table), "columns": columns}


def run_one(uci_id: int, seeds: tuple[int, ...] = SEEDS) -> dict[str, Any]:
    table, info = load_table(uci_id)
    return {
        "id": f"uci:{uci_id}",
        **info,
        "arms": {
            "clean_reference": run_source(table, seeds),
            "contaminated_reference": run_source(table, seeds, contaminated=True),
        },
    }


def main(argv: list[str] | None = None) -> int:
    import chrono_injected as ci
    import injection as inj

    from etl_benchmark.atomic import atomic_path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="*", type=int)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    skipped = {}
    for uci_id in ci.TIME_SPECS:
        if args.only and uci_id not in args.only:
            continue
        try:
            result = run_one(uci_id)
        except inj.NotEligible as reason:
            skipped[f"uci:{uci_id}"] = str(reason)
            continue
        with atomic_path(args.output / f"uci_{uci_id}.json") as partial:
            partial.write_text(json.dumps(result, sort_keys=True) + "\n")
        print(uci_id, flush=True)
    tag = "_".join(map(str, args.only)) if args.only else "all"
    with atomic_path(args.output / f"skipped_{tag}.json") as partial:
        partial.write_text(json.dumps(skipped) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
