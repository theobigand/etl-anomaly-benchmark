"""Neural numerical-reproducibility probe (exploratory; not part of the governed sources).

Worker mode fits one detector on one problem/seed in this process and writes its fit scores,
held-out scores and alert-budget outcome. The driver launches workers in fresh processes under
different thread settings and compares them. Run from the repository root with the project's
Python:  python <this file> drive <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
PROBLEMS = ["adbench:breastw", "adbench:cardio", "adbench:musk"]
METHODS = ["ae1svm", "lunar", "deep_svdd", "autoencoder"]
SEEDS = [42, 1]
BUDGET = 0.02


def worker(problem: str, method: str, seed: int, threads: int, deterministic: bool, out: Path):
    warnings.filterwarnings("ignore")
    os.environ["TQDM_DISABLE"] = "1"
    sys.path[:0] = [str(ROOT / "research"), str(ROOT / "src")]
    import labelled_benchmark as lb
    import normalise as nm
    import pandas as pd
    import torch
    from deep_support import build, capped
    from pool_full import fit_scores
    from sklearn.metrics import average_precision_score, roc_auc_score

    torch.set_num_threads(threads)
    if deterministic:
        torch.use_deterministic_algorithms(True)
    job = next(
        j
        for j in lb.jobs(
            ROOT / "verification/evidence/dataset_registry",
            ROOT / "data/adbench",
            ROOT / "data/pool",
        )
        if j["problem"] == problem
    )
    x, y, _ = (
        lb.load_adbench(job["name"], Path(job["path"]))
        if job["source"] == "adbench"
        else lb.load_uci(job["meta"], Path(job["path"]))
    )
    part = nm.split(x, y, seed)
    names = [f"f{i}" for i in range(x.shape[1])]
    train = pd.DataFrame(part["x_train"], columns=names)
    test = pd.DataFrame(part["x_test"], columns=names)
    fit = capped(train, method, seed)
    detector = build(method, 0.02, seed)
    t0 = time.time()
    detector.fit(fit)
    kept = fit_scores(detector, fit)
    s1 = np.asarray(detector.score(test), dtype=float)
    s2 = np.asarray(detector.score(test), dtype=float)  # inference repeated on the same model
    thr = float(np.percentile(kept, 100 * (1 - BUDGET)))
    flags = s1 > thr
    yt = part["y_test"]
    np.savez(out, fit=kept, test=s1, test_again=s2, y=yt)
    print(
        json.dumps(
            {
                "problem": problem,
                "method": method,
                "seed": seed,
                "threads": threads,
                "deterministic": deterministic,
                "fit_rows": len(fit),
                "test_rows": len(yt),
                "seconds": round(time.time() - t0, 2),
                "threshold": thr,
                "alert_rate": float(flags.mean()),
                "recall": float((flags & (yt == 1)).sum() / (yt == 1).sum()),
                "precision": float((flags & (yt == 1)).sum() / max(flags.sum(), 1)),
                "roc_auc": float(roc_auc_score(yt, s1)),
                "ap": float(average_precision_score(yt, s1)),
                "sha_fit": hashlib.sha256(kept.tobytes()).hexdigest()[:16],
                "sha_test": hashlib.sha256(s1.tobytes()).hexdigest()[:16],
                "inference_repeat_identical": bool(np.array_equal(s1, s2)),
            }
        )
    )


def run_worker(problem, method, seed, threads, det, out: Path):
    env = {**os.environ, "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads),
           "OPENBLAS_NUM_THREADS": str(threads), "VECLIB_MAXIMUM_THREADS": str(threads),
           "PYTHONHASHSEED": "0"}  # fmt: skip
    cmd = [sys.executable, __file__, "worker", problem, method, str(seed), str(threads),
           "1" if det else "0", str(out)]  # fmt: skip
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT)
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    if r.returncode or not line:
        raise RuntimeError(r.stderr[-400:])
    return json.loads(line[-1])


def compare(a: Path, b: Path) -> dict:
    x, y = np.load(a), np.load(b)
    from scipy.stats import spearmanr

    return {
        "fit_max_abs": float(np.abs(x["fit"] - y["fit"]).max()),
        "test_max_abs": float(np.abs(x["test"] - y["test"]).max()),
        "test_spearman": float(spearmanr(x["test"], y["test"])[0]),
        "test_bitwise": bool(np.array_equal(x["test"], y["test"])),
        "fit_bitwise": bool(np.array_equal(x["fit"], y["fit"])),
        "flag_disagreements": int(
            (
                (x["test"] > np.percentile(x["fit"], 98))
                != (y["test"] > np.percentile(y["fit"], 98))
            ).sum()
        ),
    }


def drive(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    import numpy
    import pandas
    import scipy
    import sklearn
    import torch

    cpu = subprocess.run(
        ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
    ).stdout.strip()
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu,
        "cores": os.cpu_count(),
        "torch": torch.__version__,
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy.__version__,
        "sklearn": sklearn.__version__,
        "torch_default_threads": torch.get_num_threads(),
        "deterministic_default": torch.are_deterministic_algorithms_enabled(),
    }
    results = []
    for problem in PROBLEMS:
        for method in METHODS:
            for seed in SEEDS:
                tag = f"{problem.replace(':', '_')}__{method}__{seed}"
                runs = {}
                configurations = (
                    ("t4_a", 4, False),
                    ("t4_b", 4, False),
                    ("t4_c", 4, False),
                    ("t1", 1, False),
                    ("t2", 2, False),
                    ("t10", 10, False),
                    ("t4_det", 4, True),
                )
                for label, threads, det in configurations:
                    path = out / f"{tag}__{label}.npz"
                    try:
                        runs[label] = (run_worker(problem, method, seed, threads, det, path), path)
                    except RuntimeError as error:
                        runs[label] = ({"error": str(error)}, path)
                base = runs["t4_a"]
                entry = {"problem": problem, "method": method, "seed": seed,
                         "runs": {k: v[0] for k, v in runs.items()}, "vs_t4_a": {}}  # fmt: skip
                for label, (rec, path) in runs.items():
                    if label != "t4_a" and "error" not in rec and "error" not in base[0]:
                        entry["vs_t4_a"][label] = compare(base[1], path)
                results.append(entry)
                print(
                    tag,
                    {k: ("ERR" if "error" in v[0] else v[0]["sha_test"]) for k, v in runs.items()},
                    flush=True,
                )
    (out / "results.json").write_text(
        json.dumps({"environment": env, "results": results}, indent=1)
    )
    for p in out.glob("*.npz"):
        p.unlink()  # arrays are summarized by hashes and differences


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("mode", choices=["drive", "worker"])
    cli.add_argument("args", nargs="*")
    ns = cli.parse_args()
    if ns.mode == "drive":
        drive(Path(ns.args[0]))
    else:
        p, m, s, t, d, o = ns.args
        worker(p, m, int(s), int(t), d == "1", Path(o))
