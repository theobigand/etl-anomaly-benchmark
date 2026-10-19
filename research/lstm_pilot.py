"""LSTM autoencoder pilot (issue 52); protocol in verification/lstm_pilot.md.

Run with the environment of research/requirements-lstm.txt. Not part of FAST or CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT / "experiments")]

import temporal_pilot as tp  # noqa: E402
from lstm_detector import LSTMAutoencoder  # noqa: E402
from paired_bootstrap import paired_block_bootstrap  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.atomic import atomic_path  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS  # noqa: E402
from etl_benchmark.metrics import compute_metrics  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality.autoencoder import AutoencoderDetector  # noqa: E402

log = logging.getLogger(__name__)
SEEDS = (42, 1, 2, 3, 4)
FIT_ROWS = 50_000
WINDOW, HIDDEN = 10, 32
BLOCK_SECONDS, RESAMPLES, BOOTSTRAP_SEED = 1800, 1000, 42


def synthetic_sequence_stream(n: int = 24_000, rate: float = 0.01, seed: int = 0) -> pd.DataFrame:
    """AR(1) features whose anomalies break continuity while staying inside the marginal range."""
    rng = np.random.default_rng(seed)
    d = 5
    x = np.zeros((n, d))
    noise = rng.normal(scale=0.35, size=(n, d))
    for t in range(1, n):
        x[t] = 0.95 * x[t - 1] + noise[t]
    label = np.zeros(n, dtype=int)
    hits = rng.choice(np.arange(20, n), size=int(n * rate), replace=False)
    sd = x.std(axis=0)
    for t in hits:
        x[t] = (
            -x[t - 1] * 0.9 + 0.0
        )  # sign flip of the previous state: a plausible value, an implausible step
        x[t] = np.clip(x[t], -1.5 * sd, 1.5 * sd)
        label[t] = 1
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(d)])
    frame[ANOMALY_COLUMN] = label
    frame["Time"] = np.arange(n, dtype=float)
    frame[tp.TIME_UTC] = tp.to_timestamps(frame["Time"])
    return frame


def _row_autoencoder(train_x: pd.DataFrame, test_x: pd.DataFrame, contamination: float):
    detector = AutoencoderDetector(contamination=contamination)
    result = detect(test_x, detector, fit_df=train_x)
    return (
        np.asarray(result.scores, dtype=float),
        np.asarray(result.flags, dtype=bool),
        detector.settings(),
    )


def compare(
    train,
    val,
    test,
    columns,
    seed,
    *,
    fit_rows=FIT_ROWS,
    window=WINDOW,
    hidden=HIDDEN,
    max_epochs=20,
):
    """Fit the row autoencoder and the LSTM autoencoder on the same rows; score the same test."""
    contamination = float(train[ANOMALY_COLUMN].mean())
    sample = train.sample(n=min(fit_rows, len(train)), random_state=seed).sort_values(tp.TIME_UTC)
    a_scores, a_flags, a_settings = _row_autoencoder(sample[columns], test[columns], contamination)
    started = time.perf_counter()
    model = LSTMAutoencoder(
        columns, tp.TIME_UTC, window=window, hidden=hidden, max_epochs=max_epochs,
        fit_rows=fit_rows, seed=seed,
    ).fit(train, val, contamination)  # fmt: skip
    seconds = time.perf_counter() - started
    b_scores = model.score(test).to_numpy()
    b_flags = model.flags(test).to_numpy()
    y = test[ANOMALY_COLUMN].to_numpy()
    return {
        "y": y,
        "autoencoder": {"scores": a_scores, "metrics": compute_metrics(y, a_flags, a_scores), "settings": a_settings},
        "lstm": {
            "scores": b_scores,
            "metrics": compute_metrics(y, b_flags, b_scores),
            "settings": model.settings(),
            "fit_seconds": seconds,
        },
    }  # fmt: skip


def _summary(result, times) -> dict[str, Any]:
    paired = paired_block_bootstrap(
        result["y"], result["lstm"]["scores"], result["autoencoder"]["scores"], times,
        BLOCK_SECONDS, RESAMPLES, BOOTSTRAP_SEED,
    )  # fmt: skip
    return {
        "autoencoder": {k: result["autoencoder"][k] for k in ("metrics", "settings")},
        "lstm": {k: result["lstm"][k] for k in ("metrics", "settings", "fit_seconds")},
        "lstm_minus_autoencoder": paired,
    }


def run_synthetic() -> dict[str, Any]:
    frame = synthetic_sequence_stream()
    train, val, test = tp.chronological_partitions(frame)
    columns = [c for c in frame.columns if c.startswith("f")]
    result = compare(train, val, test, columns, seed=42, fit_rows=len(train), max_epochs=20)
    summary = _summary(result, test[tp.TIME_UTC])
    summary["passes_gate"] = bool(summary["lstm_minus_autoencoder"]["ci_low"] > 0)
    summary["rows"] = {"train": len(train), "validation": len(val), "test": len(test)}
    return summary


def run_credit_card(spec, reference: dict[str, Any] | None) -> dict[str, Any]:
    frame = tp.load(spec)
    train, val, test = tp.chronological_partitions(frame)
    columns = list(tp.features(spec, frame).columns)
    by_seed = {}
    for seed in SEEDS:
        log.info("credit card, seed %d", seed)
        result = compare(train, val, test, columns, seed)
        by_seed[str(seed)] = _summary(result, test[tp.TIME_UTC])
    partitions = {
        "train": tp.describe(train),
        "validation": tp.describe(val),
        "test": tp.describe(test),
    }
    out: dict[str, Any] = {"by_seed": by_seed, "partitions": partitions}
    if reference:
        out["reference_pilot_51"] = {
            name: reference["chronological"][name]["pr_auc"] for name in reference["chronological"]
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=config.RESULTS_DIR / "lstm_pilot.json")
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    spec = DATASETS["credit_card"]
    result: dict[str, Any] = {"synthetic_control": run_synthetic()}
    log.info("synthetic control gate passed: %s", result["synthetic_control"]["passes_gate"])
    reference_path = ROOT / "verification" / "evidence" / "temporal_pilot" / "temporal_pilot.json"
    if not args.synthetic_only:
        if not result["synthetic_control"]["passes_gate"]:
            log.warning("the synthetic gate failed: Credit Card is run but must not be interpreted")
        reference = json.loads(reference_path.read_text()) if reference_path.is_file() else None
        result["credit_card"] = run_credit_card(spec, reference)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    result["provenance"] = {
        "dataset_sha256": sha(spec.csv),
        "script_sha256": sha(__file__),
        "detector_sha256": sha(HERE / "lstm_detector.py"),
        "protocol": "verification/lstm_pilot.md",
        "versions": {p: version(p) for p in ("torch", "numpy", "pandas", "scikit-learn")},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(result, indent=2, sort_keys=True, default=float) + "\n")
    from provenance import write_record

    write_record(
        args.output.with_name("run_lstm_pilot.json"), experiment="lstm_pilot", seeds=list(SEEDS),
        dataset="credit_card", data_path=None, outputs=[args.output.name],
        settings={"window": WINDOW, "hidden": HIDDEN, "fit_rows": FIT_ROWS, **result["provenance"]},
    )  # fmt: skip
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
