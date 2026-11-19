"""Detection-stage time of the six neural detectors, measured alone, on the two tables whose time
column was left empty (Credit Card Fraud and the synthetic dataset).

Same splits, seeds, fit cap (20,000 rows) and contamination as the benchmark runs; only fit, predict
and score are timed (``pipeline.detect``). One detector at a time, nothing else started by this
script. The load average before and after each repetition is recorded: this is a measurement on one
machine, not a guarantee of isolation.

    python paper/measure_neural_times.py
"""

from __future__ import annotations

import json
import os
import platform
import sys
import warnings
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "research"), str(ROOT / "src"), str(ROOT / "experiments")]

import run_synthetic_benchmark as rsb  # noqa: E402
from deep_support import build, capped  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES, calibrate_contamination  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402
from etl_benchmark.synthetic import FEATURE_COLUMNS, make_synthetic  # noqa: E402

OUT = ROOT / "verification" / "evidence" / "neural_timing" / "neural_times.json"


def _splits(dataset: str, seed: int):
    if dataset == "credit_card":
        spec = DATASETS["credit_card"]
        df = _splits.cache.setdefault("credit_card", spec.load())
        train, _val, test = stratified_split(df, ANOMALY_COLUMN, config.SPLIT_RATIOS, seed)
        return (
            spec.features(train),
            spec.features(test),
            calibrate_contamination(train[ANOMALY_COLUMN]),
        )
    df = make_synthetic(seed=seed)
    train, _val, test = rsb._split_synthetic(df, seed)
    return train[FEATURE_COLUMNS], test[FEATURE_COLUMNS], float(train["anomaly"].mean())


_splits.cache = {}


def main() -> int:
    warnings.filterwarnings("ignore")
    runs = []
    for dataset in ("credit_card", "synthetic"):
        for seed in config.BENCHMARK_SEEDS:
            fit_x, test_x, contamination = _splits(dataset, seed)
            for name in DEEP_NAMES:
                load_before = os.getloadavg()[0]
                result = detect(
                    test_x, build(name, contamination, seed), fit_df=capped(fit_x, name, seed)
                )
                runs.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "detector": name,
                        "fit_rows": int(min(len(fit_x), 20_000)),
                        "score_rows": len(test_x),
                        "fit_s": result.fit_s,
                        "predict_s": result.predict_s,
                        "score_s": result.score_s,
                        "detect_s": result.detect_s,
                        "load_before": load_before,
                        "load_after": os.getloadavg()[0],
                    }
                )
                print(dataset, seed, name, round(result.detect_s, 2), flush=True)
    summary = {
        d: {
            n: float(
                np.mean([r["detect_s"] for r in runs if r["dataset"] == d and r["detector"] == n])
            )
            for n in DEEP_NAMES
        }
        for d in ("credit_card", "synthetic")
    }
    payload = {
        "machine": platform.platform(),
        "cpu_count": os.cpu_count(),
        "seeds": list(config.BENCHMARK_SEEDS),
        "mean_detect_s": summary,
        "runs": runs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
