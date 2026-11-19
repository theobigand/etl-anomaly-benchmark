"""Bounded prospective convergence probe of the neural detectors (T055, protocol 2026-11-18).

For the gradient-trained detectors the probe compares the scores obtained with the registry budget
and with three times that budget (same seed, same train-only partitions); DIF, which has no
epoch budget, is checked for score stability across model seeds on one fixed partition. It
records non-finite scores and warnings. It is a budget-sufficiency check, not a convergence proof.
"""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labelled_benchmark as lb  # noqa: E402

from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality import deep  # noqa: E402
from etl_benchmark.registry import clip_contamination, get_detector  # noqa: E402
from research.deep_support import capped  # noqa: E402
from research.pool_preprocessing import prepare_frozen  # noqa: E402
from research.pool_train_only_replay import grouped_split, load_raw  # noqa: E402

SEEDS = (42, 1, 2)
FACTOR = 3
BUDGETS = {  # registry default epochs, and the argument that sets them
    "vae": ("epoch_num", 30, deep.VAEDetector),
    "deep_svdd": ("epochs", 100, deep.DeepSVDDDetector),
    "ae1svm": ("epochs", 50, deep.AE1SVMDetector),
    "lunar": ("n_epochs", 200, deep.LUNARDetector),
}


def select(jobs: list[dict], rows: dict[str, int], count: int = 8) -> list[dict]:
    """Pre-declared rule: problems with 300-5000 rows, sorted by id, evenly spaced."""
    eligible = sorted(
        (j for j in jobs if 300 <= rows[j["problem"]] <= 5000), key=lambda j: j["problem"]
    )
    step = max(1, len(eligible) // count)
    return eligible[::step][:count]


def _scores(
    detector, train: pd.DataFrame, test: pd.DataFrame, seed: int
) -> tuple[np.ndarray, list[str]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = detect(test, detector, fit_df=capped(train, detector.name, seed))
    return result.scores.to_numpy(dtype=float), sorted({str(w.category.__name__) for w in caught})


def probe_problem(job: dict) -> dict:
    frame, labels = load_raw(job)
    out = {"problem": job["problem"], "rows": len(labels), "runs": []}
    for seed in SEEDS:
        parts = grouped_split(frame, labels, seed)
        prepared = prepare_frozen(frame, parts)
        train, test = prepared["train"], prepared["test"]
        y = labels[parts["test"]]
        contamination = clip_contamination(float(labels[parts["train"]].mean()))
        for name, (arg, default, cls) in BUDGETS.items():
            base, long = (
                cls(contamination=contamination, random_state=seed, **kw)
                for kw in ({}, {arg: default * FACTOR})
            )
            a, warn_a = _scores(base, train, test, seed)
            b, warn_b = _scores(long, train, test, seed)
            out["runs"].append(
                {
                    "detector": name,
                    "seed": seed,
                    "budget": default,
                    "long_budget": default * FACTOR,
                    "spearman_budget_vs_long": float(spearmanr(a, b).statistic),
                    "ap_budget": float(average_precision_score(y, a)),
                    "ap_long": float(average_precision_score(y, b)),
                    "nonfinite": int((~np.isfinite(a)).sum() + (~np.isfinite(b)).sum()),
                    "warnings": sorted(set(warn_a + warn_b)),
                }
            )
        ae = get_detector("autoencoder", contamination)
        ae.random_state = seed
        _scores(ae, train, test, seed)
        out["runs"].append({"detector": "autoencoder", "seed": seed, "settings": ae.settings()})
    out["dif_seed_spearman"] = dif_seed_spearman(frame, labels)
    return out


def dif_seed_spearman(frame: pd.DataFrame, labels: np.ndarray) -> list[float]:
    """Pairwise rank correlation of DIF scores across model seeds on ONE fixed partition."""
    parts = grouped_split(frame, labels, SEEDS[0])
    prepared = prepare_frozen(frame, parts)
    train, test = prepared["train"], prepared["test"]
    contamination = clip_contamination(float(labels[parts["train"]].mean()))
    scores = {}
    for seed in SEEDS:
        dif = get_detector("dif", contamination)
        dif.random_state = seed
        scores[seed], _ = _scores(dif, train, test, seed)
    return [
        float(spearmanr(scores[a], scores[b]).statistic)
        for i, a in enumerate(SEEDS)
        for b in SEEDS[i + 1 :]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    registry = root / "verification/evidence/dataset_registry"
    jobs = lb.jobs(registry, root / "data/adbench", root / "data/pool")
    rows = {}
    for path in (root / "verification/evidence/labelled_pool/runs").glob("*.json"):
        d = json.loads(path.read_text())
        rows[d["problem"]] = d["rows"]
    chosen = select([j for j in jobs if j["problem"] in rows], rows)
    results = [probe_problem(j) for j in chosen]
    args.output.write_text(
        json.dumps({"protocol": "neural-budget-probe-v1", "results": results}, indent=1) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
