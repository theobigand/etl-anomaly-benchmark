"""Cost and scalability study (issue 53); protocol in verification/cost_study.md.

Every measurement runs in a fresh process so that the peak resident memory (native allocations
included) belongs to that measurement alone. Not part of FAST or CI; no timing threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT / "experiments")]

SEED = 42
SIZES = (1_000, 3_000, 10_000, 30_000, 100_000, 300_000)
METHODS = ("zscore", "iqr", "isolation_forest", "lof", "ocsvm", "autoencoder", "lstm_autoencoder")
FEATURES = 8
WIDE_FEATURES, WIDE_ROWS = 29, 30_000
TIMEOUT_S = 300
LSTM_EPOCHS, LSTM_FIT_ROWS = 5, 50_000
WARMUP_ROWS = 200


def make_data(n: int, d: int, seed: int = SEED) -> np.ndarray:
    return np.random.default_rng(seed).normal(size=(n, d))


def reps_for(n: int) -> int:
    return 5 if n <= 30_000 else 3


def peak_rss_bytes() -> int:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(raw if sys.platform == "darwin" else raw * 1024)


def is_contended(before: float, after: float, cores: int) -> bool:
    return max(before, after) > cores / 2


def _frame(array: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(array, columns=[f"f{i}" for i in range(array.shape[1])])


def _lstm_run(array: np.ndarray, epochs: int, fit_rows: int) -> dict[str, Any]:
    from lstm_detector import LSTMAutoencoder

    frame = _frame(array)
    frame["t"] = pd.Timestamp("1970-01-01", tz="UTC") + pd.to_timedelta(np.arange(len(frame)), "s")
    columns = [c for c in frame.columns if c != "t"]
    validation = frame.iloc[: max(20, min(len(frame), 5000))]
    model = LSTMAutoencoder(columns, "t", max_epochs=epochs, fit_rows=fit_rows, seed=SEED)
    t0 = time.perf_counter()
    model.fit(frame, validation, contamination=0.01)
    t1 = time.perf_counter()
    scores = model.score(frame)
    t2 = time.perf_counter()
    _ = scores > model.threshold_
    t3 = time.perf_counter()
    return {
        "fit_s": t1 - t0,
        "score_s": t2 - t1,
        "predict_s": t3 - t2,
        "epochs_run": model.settings()["epochs_run"],
        "fit_rows": fit_rows,
    }


def run_detection(
    method: str, array: np.ndarray, lstm_epochs: int = LSTM_EPOCHS, fit_rows: int = LSTM_FIT_ROWS
) -> dict[str, Any]:
    """Time one detector on ``array`` (fit and evaluation on the same rows) in this process."""
    from etl_benchmark.pipeline import detect
    from etl_benchmark.registry import ALL_NAMES, DEEP_NAMES, get_detector

    if method not in (*ALL_NAMES, *DEEP_NAMES, "lstm_autoencoder"):
        return {"status": "FAIL", "reason": f"unknown method {method!r}"}
    try:
        warm = array[:WARMUP_ROWS]
        if method == "lstm_autoencoder":
            _lstm_run(warm, 1, WARMUP_ROWS)
        else:
            detect(_frame(warm), get_detector(method, 0.01))
        frame = _frame(array)
        before = peak_rss_bytes()
        if method == "lstm_autoencoder":
            stages = _lstm_run(array, lstm_epochs, fit_rows)
        else:
            result = detect(frame, get_detector(method, 0.01))
            stages = {
                "fit_s": result.fit_s,
                "predict_s": result.predict_s,
                "score_s": result.score_s,
            }
        peak = peak_rss_bytes()
    except Exception as exc:  # recorded, never hidden
        return {"status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"}
    stages["detect_s"] = stages["fit_s"] + stages["predict_s"] + stages["score_s"]
    return {
        "status": "OK",
        **stages,
        "rss_before_bytes": before,
        "rss_peak_bytes": peak,
        "rss_delta_bytes": peak - before,
    }


def run_etl(csv: Path, method: str, out_dir: Path) -> dict[str, Any]:
    """Time the four stages of the pipeline separately on a real CSV."""
    from etl_benchmark.load import write_csv
    from etl_benchmark.pipeline import detect, extract, transform
    from etl_benchmark.registry import get_detector

    stages: dict[str, float] = {}
    t = time.perf_counter()
    df = extract(csv)
    stages["extract"] = time.perf_counter() - t
    rows_in = len(df)
    t = time.perf_counter()
    df = transform(df)
    stages["transform"] = time.perf_counter() - t
    t = time.perf_counter()
    result = detect(df, get_detector(method, 0.0017), label_column="Class")
    stages["detect"] = time.perf_counter() - t
    t = time.perf_counter()
    write_csv(df[~result.flags], out_dir / "pipeline_clean.csv")
    write_csv(df[result.flags], out_dir / "pipeline_anomalies.csv")
    stages["load"] = time.perf_counter() - t
    return {
        "status": "OK",
        "method": method,
        "rows_in": rows_in,
        "rows_after_transform": len(df),
        "stages_s": stages,
        "detect_stage_share": stages["detect"] / sum(stages.values()),
        "rss_peak_bytes": peak_rss_bytes(),
    }


def measure_in_subprocess(
    method: str, n: int, d: int, rep: int, *, workdir: Path, timeout: int = TIMEOUT_S
) -> dict[str, Any]:
    path = workdir / f"data_{n}_{d}.npy"
    if not path.exists():
        np.save(path, make_data(n, d))
    record: dict[str, Any] = {"method": method, "n": n, "d": d, "rep": rep}
    record["load_before"] = os.getloadavg()[0]
    command = [sys.executable, __file__, "--worker", method, str(path)]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        record.update(status="TIMEOUT", reason=f"more than {timeout} s")
    else:
        if done.returncode != 0 or not done.stdout.strip():
            record.update(status="FAIL", reason=(done.stderr or "no output").strip()[-300:])
        else:
            record.update(json.loads(done.stdout.strip().splitlines()[-1]))
    record["load_after"] = os.getloadavg()[0]
    record["contended"] = is_contended(
        record["load_before"], record["load_after"], os.cpu_count() or 1
    )
    return record


def sweep(methods, sizes, d, measure, reps=reps_for) -> list[dict[str, Any]]:
    """Every method over growing sizes; a failure or timeout skips that method's larger sizes."""
    records: list[dict[str, Any]] = []
    for method in methods:
        stopped_at = None
        for n in sizes:
            if stopped_at is not None:
                records.append({"status": "SKIPPED", "method": method, "n": n, "d": d,
                                "reason": f"{stopped_at[1]} at {stopped_at[0]}"})  # fmt: skip
                continue
            for rep in range(reps(n)):
                record = measure(method, n, d, rep)
                records.append(record)
                if record["status"] != "OK":
                    stopped_at = (n, record["status"])
                    break
    return records


def summarize(records) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for method in sorted({r["method"] for r in records}):
        mine = [r for r in records if r["method"] == method]
        ok = [r for r in mine if r["status"] == "OK"]
        failures: dict[str, int] = {}
        for r in mine:
            if r["status"] != "OK":
                failures[r["status"]] = failures.get(r["status"], 0) + 1
        points = {}
        for n in sorted({r["n"] for r in ok}):
            times = np.array([r["detect_s"] for r in ok if r["n"] == n])
            memory = np.array([r["rss_delta_bytes"] for r in ok if r["n"] == n])
            q1, med, q3 = np.percentile(times, [25, 50, 75])
            points[str(n)] = {
                "runs": len(times), "detect_s_median": float(med), "detect_s_q1": float(q1),
                "detect_s_q3": float(q3), "detect_s_min": float(times.min()),
                "detect_s_max": float(times.max()),
                "rss_delta_bytes_median": float(np.median(memory)),
            }  # fmt: skip
        sizes = sorted(int(n) for n in points)
        exponent = None
        if len(sizes) >= 2:
            medians = [points[str(n)]["detect_s_median"] for n in sizes]
            if min(medians) > 0:
                exponent = float(np.polyfit(np.log(sizes), np.log(medians), 1)[0])
        out[method] = {
            "points": points,
            "growth_exponent": exponent,
            "largest_measured": sizes[-1] if sizes else None,
            "failures": failures,
        }
    return out


def _worker(method: str, path: str) -> int:
    print(json.dumps(run_detection(method, np.load(path))))
    return 0


def _etl_worker(csv: str, method: str, out_dir: str) -> int:
    print(json.dumps(run_etl(Path(csv), method, Path(out_dir))))
    return 0


def wait_for_quiet(limit_s: int = 600) -> float:
    cores = os.cpu_count() or 1
    deadline = time.time() + limit_s
    while os.getloadavg()[0] > cores / 2 and time.time() < deadline:
        time.sleep(15)
    return os.getloadavg()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, metavar=("METHOD", "NPY"))
    parser.add_argument("--etl-worker", nargs=3, metavar=("CSV", "METHOD", "OUT"))
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments" / "results" / "cost_study.json"
    )
    parser.add_argument("--sizes", type=int, nargs="+", default=list(SIZES))
    parser.add_argument("--methods", nargs="+", default=list(METHODS))
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.worker:
        return _worker(*args.worker)
    if args.etl_worker:
        return _etl_worker(*args.etl_worker)
    from etl_benchmark import config
    from etl_benchmark.atomic import atomic_path

    started = wait_for_quiet()
    workdir = Path(tempfile.mkdtemp(prefix="cost_study_"))
    measure = lambda m, n, d, r: measure_in_subprocess(m, n, d, r, workdir=workdir)  # noqa: E731
    narrow = sweep(args.methods, args.sizes, FEATURES, measure)
    wide = sweep(args.methods, [WIDE_ROWS], WIDE_FEATURES, measure)
    csv = args.csv or config.CREDIT_CARD_CSV
    etl = []
    for method in ("zscore", "isolation_forest"):
        for rep in range(3):
            out = workdir / f"etl_{method}_{rep}"
            out.mkdir()
            done = subprocess.run(
                [sys.executable, __file__, "--etl-worker", str(csv), method, str(out)],
                capture_output=True, text=True, timeout=TIMEOUT_S * 2, check=False,
            )  # fmt: skip
            if done.returncode == 0:
                etl.append(json.loads(done.stdout.splitlines()[-1]))
            else:
                etl.append({"status": "FAIL", "method": method, "reason": done.stderr[-300:]})
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    result = {
        "records": narrow, "wide_records": wide, "etl_records": etl,
        "summary": summarize(narrow), "wide_summary": summarize(wide),
        "settings": {"seed": SEED, "sizes": args.sizes, "features": FEATURES,
                     "wide": [WIDE_ROWS, WIDE_FEATURES], "timeout_s": TIMEOUT_S,
                     "methods": args.methods, "lstm_epochs": LSTM_EPOCHS,
                     "lstm_fit_rows": LSTM_FIT_ROWS,
                     "load_at_start": started},
        "provenance": {
            "script_sha256": sha(__file__), "dataset_sha256": sha(csv),
            "protocol": "verification/cost_study.md",
            "versions": {p: version(p) for p in ("numpy", "pandas", "scikit-learn", "torch")},
            "python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "cpu_count": os.cpu_count(),
        },
    }  # fmt: skip
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(result, indent=2, sort_keys=True, default=float) + "\n")
    from provenance import write_record

    write_record(
        args.output.with_name("run_cost_study.json"),
        experiment="cost_study",
        seeds=[SEED],
        dataset="synthetic_gaussian+credit_card",
        data_path=None,
        outputs=[args.output.name],
        settings=result["settings"] | result["provenance"],
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
