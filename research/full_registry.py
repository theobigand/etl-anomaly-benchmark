"""Neural detectors on the real datasets and the synthetic matrix, and the hypotheses of the
complete-registry study (protocol verification/full_registry.md, written before any result).

The classical detectors of the registry sweep are archived by the usual runs. The neural ones are
fitted on at most ``DEEP_FIT_CAP`` training rows with the seed of the repetition.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT / "experiments")]

import run_synthetic_benchmark as rsb  # noqa: E402
from deep_support import DEEP_FIT_CAP, build, capped  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS, DatasetSpec  # noqa: E402
from etl_benchmark.metrics import compute_metrics  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES, calibrate_contamination  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES, FEATURE_COLUMNS, make_synthetic  # noqa: E402

SEEDS = config.BENCHMARK_SEEDS
MARGINAL = ("ecod", "copod", "hbos")
NEW_CLASSICAL = ("ecod", "copod", "hbos", "knn", "pca")
NEW_DEEP = tuple(n for n in DEEP_NAMES if n != "autoencoder")
EARLIER_ROW_LEVEL = (
    "zscore",
    "iqr",
    "great_expectations",
    "isolation_forest",
    "lof",
    "ocsvm",
    "autoencoder",
)
METRICS = ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct", "detect_s"]


def _settings(detector: Any) -> dict[str, Any]:
    return json.loads(json.dumps(detector.settings(), default=str))


def real_seed(
    spec: DatasetSpec, df: pd.DataFrame, seed: int, names: tuple[str, ...] | list[str] = DEEP_NAMES
) -> dict[str, Any]:
    """The neural detectors on one split of a real dataset."""
    warnings.filterwarnings("ignore")
    train, _val, test = stratified_split(df, ANOMALY_COLUMN, config.SPLIT_RATIOS, seed)
    contamination = calibrate_contamination(train[ANOMALY_COLUMN])
    fit_df, test_x = spec.features(train), spec.features(test)
    y_test = test[ANOMALY_COLUMN].to_numpy()
    rows: dict[str, Any] = {}
    for name in names:
        detector = build(name, contamination, seed)
        try:
            result = detect(test_x, detector, fit_df=capped(fit_df, name, seed))
        except Exception as error:  # a failing model is recorded, not hidden
            rows[name] = {"error": repr(error)}
            continue
        rows[name] = {
            **compute_metrics(y_test, result.flags, result.scores),
            "detect_s": result.detect_s,
            "settings": _settings(detector),
        }
    return {"seed": seed, "fit_rows": int(min(len(fit_df), DEEP_FIT_CAP)), "methods": rows}


def real_summary(
    runs: list[dict[str, Any]], names: tuple[str, ...] | list[str] = DEEP_NAMES
) -> pd.DataFrame:
    """Mean and standard deviation over seeds of the metrics, one row per detector."""
    table = {}
    for name in names:
        ok = [r["methods"][name] for r in runs if "error" not in r["methods"][name]]
        if not ok:
            continue
        frame = pd.DataFrame([{m: row[m] for m in METRICS} for row in ok])
        table[name] = {
            **{f"{m}_mean": frame[m].mean() for m in METRICS},
            **{f"{m}_std": frame[m].std() for m in METRICS},
            "seeds": len(ok),
        }
    return pd.DataFrame(table).T


def synthetic_seed(
    seed: int, rows: int | None = None, names: tuple[str, ...] | list[str] = DEEP_NAMES
) -> dict[str, Any]:
    """The neural detectors on the identity-disjoint split of the synthetic dataset."""
    warnings.filterwarnings("ignore")
    df = make_synthetic(seed=seed, **({"n_rows": rows} if rows else {}))
    train, _val, test = rsb._split_synthetic(df, seed)
    contamination = float(train["anomaly"].mean())
    recall, precision, fpr, settings, errors = {}, {}, {}, {}, {}
    for name in names:
        detector = build(name, contamination, seed)
        started = time.perf_counter()
        try:
            result = detect(
                test[FEATURE_COLUMNS],
                detector,
                fit_df=capped(train[FEATURE_COLUMNS], name, seed),
            )
        except Exception as error:
            errors[name] = repr(error)
            continue
        flags = pd.Series(result.flags.to_numpy(), index=test.index)
        r, p = rsb._per_type(flags, test["anomaly_type"])
        recall[name], precision[name] = r, p
        fpr[name] = float(flags[test["anomaly_type"] == "clean"].mean())
        settings[name] = {**_settings(detector), "seconds": time.perf_counter() - started}
    return {
        "seed": seed,
        "recall": json.loads(pd.DataFrame(recall).T[ANOMALY_TYPES].to_json(orient="split")),
        "precision": json.loads(pd.DataFrame(precision).T[ANOMALY_TYPES].to_json(orient="split")),
        "fpr": fpr,
        "settings": settings,
        "errors": errors,
    }


def _frame(split: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(split["data"], split["index"], split["columns"])


def mean_matrix(runs: list[dict[str, Any]]) -> pd.DataFrame:
    stack = pd.concat([_frame(r["recall"]) for r in runs], keys=range(len(runs)))
    return stack.groupby(level=1, sort=False).mean()


def hypotheses(classical: pd.DataFrame, deep: pd.DataFrame) -> dict[str, Any]:
    """H3, H4 and H5 of verification/full_registry.md on the synthetic customer matrix.

    ``classical`` and ``deep`` are mean recall by method (rows) and type (columns).
    """
    t = "multivariate_outlier"
    marginal = {m: float(classical.loc[m, t]) for m in MARGINAL}
    forest = float(classical.loc["isolation_forest", t])
    h3 = all(v <= 0.20 for v in marginal.values()) and forest - max(marginal.values()) >= 0.50
    pca, ae = float(classical.loc["pca", t]), float(deep.loc["autoencoder", t])
    best_earlier = pd.concat([classical, deep]).loc[list(EARLIER_ROW_LEVEL), "temporal_drift"]
    bound = float(best_earlier.max()) + 0.10
    new_drift = pd.concat(
        [
            classical.loc[list(NEW_CLASSICAL), "temporal_drift"],
            deep.loc[list(NEW_DEEP), "temporal_drift"],
        ]
    )
    return {
        "H3": {"supported": bool(h3), "marginal_recall": marginal, "isolation_forest": forest},
        "H4": {"supported": bool(abs(pca - ae) < 0.10), "pca": pca, "autoencoder": ae},
        "H5": {
            "supported": bool((new_drift <= bound).all()),
            "best_earlier": {"method": best_earlier.idxmax(), "recall": float(best_earlier.max())},
            "new_drift_recall": {m: float(v) for m, v in new_drift.items()},
        },
    }


def _published(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col="method")
    out = frame[[f"{t}_mean" for t in ANOMALY_TYPES]]
    out.columns = ANOMALY_TYPES
    return out


def _write(path: Path, payload: Any) -> None:
    from etl_benchmark.atomic import atomic_path

    with atomic_path(path) as partial:
        partial.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    real = sub.add_parser("real", help="neural detectors on Credit Card, Cardio and Water Quality")
    real.add_argument("--datasets", nargs="+", default=sorted(DATASETS), choices=sorted(DATASETS))
    synthetic = sub.add_parser("synthetic", help="neural detectors on the synthetic matrix")
    synthetic.add_argument("--rows", type=int, default=None)
    summary = sub.add_parser("summary", help="hypotheses H3 to H5 from the archived matrices")
    summary.add_argument(
        "--classical", type=Path, default=ROOT / "verification/evidence/synthetic_recall.csv"
    )
    for p in (real, synthetic, summary):
        p.add_argument("--output", type=Path, required=True)
    summary.add_argument("--deep-runs", type=Path, help="default: the synthetic runs in --output")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "real":
        for dataset in args.datasets:
            spec = DATASETS[dataset]
            df = spec.load()
            runs = []
            for seed in SEEDS:
                runs.append(real_seed(spec, df, seed))
                print(dataset, "seed", seed, flush=True)
            _write(args.output / f"real_{dataset}.json", {"dataset": dataset, "runs": runs})
            table = real_summary(runs)
            lines = ["| detector | " + " | ".join(METRICS) + " |", "|---|" + "---|" * len(METRICS)]
            for name, row in table.iterrows():
                cells = [f"{row[f'{m}_mean']:.3f} ± {row[f'{m}_std']:.3f}" for m in METRICS]
                lines.append(f"| {name} | " + " | ".join(cells) + " |")
            (args.output / f"real_{dataset}.md").write_text("\n".join(lines) + "\n")
    elif args.command == "synthetic":
        for seed in SEEDS:
            _write(args.output / f"synthetic_seed_{seed}.json", synthetic_seed(seed, args.rows))
            print("seed", seed, flush=True)
    else:
        runs = [
            json.loads(p.read_text())
            for p in sorted((args.deep_runs or args.output).glob("synthetic_seed_*.json"))
        ]
        deep = mean_matrix(runs)
        classical = _published(args.classical)
        results = {
            "seeds": [r["seed"] for r in runs],
            "deep": json.loads(deep.to_json(orient="split")),
            "hypotheses": hypotheses(classical, deep),
            "errors": {r["seed"]: r["errors"] for r in runs if r["errors"]},
        }
        _write(args.output / "synthetic_results.json", results)
        lines = [
            "| method | " + " | ".join(deep.columns) + " |",
            "|---|" + "---|" * len(deep.columns),
        ]
        lines += [
            f"| {i} | " + " | ".join(f"{v:.2f}" for v in deep.loc[i]) + " |" for i in deep.index
        ]
        (args.output / "synthetic_results.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
