"""Chronological pilot on Credit Card (issue 51); protocol in verification/temporal_pilot.md.

Compares, with identical rows, features and detectors, a chronological split (fit on the
past, score the future) with the stratified random split of the main benchmark, and runs
the window drift monitor on a known synthetic change. Not part of FAST or CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from etl_benchmark import config  # noqa: E402
from etl_benchmark.atomic import atomic_path  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS, DatasetSpec  # noqa: E402
from etl_benchmark.metrics import compute_metrics  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality.window_drift import WindowDriftMonitor, event_metrics  # noqa: E402
from etl_benchmark.registry import all_detectors  # noqa: E402
from etl_benchmark.split import chronological_split, stratified_split  # noqa: E402

log = logging.getLogger(__name__)

TIME_UTC = "time_utc"
ORIGIN = pd.Timestamp("1970-01-01", tz="UTC")  # relative origin: the file has no calendar date
DRIFT_COLUMNS = ["V1", "V2", "V3", "V4", "V5"]
DELTAS = (0.0, 0.5, 1.0, 2.0)
WINDOW_SIZE = 1000
BLOCK_SECONDS = 1800
RESAMPLES = 1000
BOOTSTRAP_SEED = 42


def to_timestamps(seconds: pd.Series) -> pd.Series:
    """Elapsed seconds since the first transaction as UTC timestamps from a fixed origin."""
    values = pd.to_numeric(seconds, errors="coerce")
    if values.isna().any() or (values < 0).any():
        raise ValueError("elapsed times must be finite and non-negative")
    return ORIGIN + pd.to_timedelta(values, unit="s")


def load(spec: DatasetSpec) -> pd.DataFrame:
    """The benchmark's cleaned rows (exact duplicates dropped) plus a timestamp column."""
    frame = spec.load()
    frame[TIME_UTC] = to_timestamps(frame["Time"])
    return frame


def features(spec: DatasetSpec, frame: pd.DataFrame) -> pd.DataFrame:
    """Detector inputs: the benchmark's features without the clock."""
    return spec.features(frame).drop(columns=["Time", TIME_UTC], errors="ignore")


def chronological_partitions(frame: pd.DataFrame):
    return chronological_split(frame, TIME_UTC, config.SPLIT_RATIOS)


def stratified_partitions(frame: pd.DataFrame, seed: int):
    return stratified_split(frame, ANOMALY_COLUMN, config.SPLIT_RATIOS, seed)


def score_partition(spec: DatasetSpec, train: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
    """Fit every detector on ``train`` only and score ``test``."""
    contamination = float(train[ANOMALY_COLUMN].mean())
    fit_df, test_x = features(spec, train), features(spec, test)
    out: dict[str, Any] = {"y": test[ANOMALY_COLUMN].to_numpy(), "scores": {}, "flags": {}}
    for det in all_detectors(ml_contamination=contamination, names=spec.detector_names):
        result = detect(test_x, det, fit_df=fit_df)
        out["scores"][det.name] = np.asarray(result.scores, dtype=float)
        out["flags"][det.name] = np.asarray(result.flags, dtype=bool)
        log.info("scored %s", det.name)
    return out


def time_blocks(times: pd.Series, block_seconds: int) -> np.ndarray:
    seconds = (pd.to_datetime(times, utc=True) - ORIGIN).dt.total_seconds()
    return (seconds // block_seconds).astype(int).to_numpy()


def block_bootstrap_ci(y, scores, times, block_seconds, resamples, seed) -> dict[str, float]:
    """Percentile interval of average precision, resampling whole blocks of time."""
    y, scores = np.asarray(y), np.asarray(scores, dtype=float)
    if len(y) != len(scores) or len(y) != len(times):
        raise ValueError("labels, scores and times must have equal length")
    if y.min() == y.max():
        raise ValueError("both classes are required")
    blocks = time_blocks(times, block_seconds)
    members = {b: np.flatnonzero(blocks == b) for b in np.unique(blocks)}
    keys = list(members)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(resamples):
        chosen = rng.choice(len(keys), size=len(keys), replace=True)
        index = np.concatenate([members[keys[k]] for k in chosen])
        if y[index].min() != y[index].max():
            values.append(average_precision_score(y[index], scores[index]))
    low, high = np.percentile(values, [2.5, 97.5])
    return {
        "estimate": float(average_precision_score(y, scores)),
        "ci_low": float(low),
        "ci_high": float(high),
        "resamples_used": len(values),
    }


def inject_shift(frame, columns, change_time, delta, scale) -> pd.DataFrame:
    """Add ``delta`` training standard deviations to ``columns`` from ``change_time`` on."""
    shifted = frame.copy()
    mask = pd.to_datetime(shifted[TIME_UTC], utc=True) >= pd.Timestamp(change_time)
    shifted.loc[mask, list(columns)] += delta * scale[list(columns)].to_numpy()
    return shifted


def monitor_control(train, val, test, columns, deltas=DELTAS, window_size=WINDOW_SIZE):
    """Known-change control: the threshold comes from validation, the change from the test."""
    scale = train[list(columns)].std(ddof=0).replace(0.0, 1.0)
    monitor = WindowDriftMonitor(TIME_UTC, columns, window_size=window_size, threshold=1e12)
    monitor.fit(train)
    threshold = float(monitor.evaluate(val)["score"].max())
    monitor.threshold = threshold
    val_windows = monitor.evaluate(val)
    ordered = sorted(test[TIME_UTC].unique())
    change = pd.Timestamp(ordered[len(ordered) // 2])
    controls = {}
    for delta in deltas:
        windows = monitor.evaluate(inject_shift(test, columns, change, delta, scale))
        metrics = event_metrics(windows, change)
        after = windows[pd.to_datetime(windows["window_end"], utc=True) >= change]
        alerts = np.flatnonzero(after["alert"].to_numpy())
        controls[str(float(delta))] = {
            "detected": metrics["detected"],
            "false_alarm_rate": metrics["false_alarm_rate"],
            "delay_seconds": (
                float(metrics["detection_delay"].total_seconds()) if metrics["detected"] else None
            ),
            "delay_windows": int(alerts[0]) + 1 if len(alerts) else None,
            "windows_before": int((pd.to_datetime(windows["window_end"], utc=True) < change).sum()),
            "windows_after": len(after),
        }
    return {
        "threshold": threshold,
        "validation_windows": len(val_windows),
        "validation_false_alarms": int(val_windows["alert"].sum()),
        "change_time": change.isoformat(),
        "window_size": window_size,
        "columns": list(columns),
        "controls": controls,
    }


def describe(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": len(frame),
        "frauds": int(frame[ANOMALY_COLUMN].sum()),
        "prevalence": float(frame[ANOMALY_COLUMN].mean()),
        "time_min_s": float(frame["Time"].min()),
        "time_max_s": float(frame["Time"].max()),
    }


def run(spec: DatasetSpec, seeds=config.BENCHMARK_SEEDS) -> dict[str, Any]:
    frame = load(spec)
    train, val, test = chronological_partitions(frame)
    scored = score_partition(spec, train, test)
    chrono = {}
    for name, score in scored["scores"].items():
        metrics = compute_metrics(scored["y"], scored["flags"][name], score)
        ci = block_bootstrap_ci(
            scored["y"], score, test[TIME_UTC], BLOCK_SECONDS, RESAMPLES, BOOTSTRAP_SEED
        )
        chrono[name] = {**metrics, "pr_auc_ci": ci}
    control: dict[str, dict[str, list[float]]] = {}
    for seed in seeds:
        s_train, _s_val, s_test = stratified_partitions(frame, seed)
        s_scored = score_partition(spec, s_train, s_test)
        for name, score in s_scored["scores"].items():
            m = compute_metrics(s_scored["y"], s_scored["flags"][name], score)
            for key, value in m.items():
                control.setdefault(name, {}).setdefault(key, []).append(float(value))
    stratified = {
        name: {k: {"mean": float(np.mean(v)), "std": float(np.std(v, ddof=1)), "values": v}
               for k, v in metrics.items()}
        for name, metrics in control.items()
    }  # fmt: skip
    return {
        "partitions": {
            "train": describe(train),
            "validation": describe(val),
            "test": describe(test),
        },
        "chronological": chrono,
        "stratified": stratified,
        "drift_control": monitor_control(train, val, test, DRIFT_COLUMNS),
        "settings": {
            "seeds": list(seeds),
            "block_seconds": BLOCK_SECONDS,
            "resamples": RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "window_size": WINDOW_SIZE,
            "deltas": list(DELTAS),
            "ratios": list(config.SPLIT_RATIOS),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=config.RESULTS_DIR / "temporal_pilot.json")
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    spec = DATASETS["credit_card"]
    if args.csv is not None:
        spec = DatasetSpec(**{**spec.__dict__, "csv": args.csv})
    result = run(spec)
    with spec.csv.open("rb") as stream:
        data_sha = hashlib.file_digest(stream, hashlib.sha256).hexdigest()
    with Path(__file__).open("rb") as stream:
        script_sha = hashlib.file_digest(stream, hashlib.sha256).hexdigest()
    result["provenance"] = {
        "dataset_sha256": data_sha,
        "script_sha256": script_sha,
        "protocol": "verification/temporal_pilot.md",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    from provenance import write_record

    write_record(
        args.output.with_name("run_temporal_pilot.json"),
        experiment="temporal_pilot",
        seeds=list(config.BENCHMARK_SEEDS),
        dataset="credit_card",
        data_path=None,
        settings={**result["settings"], **result["provenance"]},
        outputs=[args.output.name],
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
