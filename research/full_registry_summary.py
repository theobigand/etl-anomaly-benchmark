"""Tables and figures of the complete-registry study (protocol verification/full_registry.md).

Merges the classical runs archived by the usual experiments with the neural runs of
``full_registry.py``, ``labelled_benchmark.py --methods deep``, ``typed_run.py --methods deep`` and
``multi_schema.py --methods deep``, so that every table and figure lists the whole registry.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import typed_figures as tf  # noqa: E402
import typed_summary as ts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "verification" / "evidence"
ORDER = [
    "zscore",
    "iqr",
    "great_expectations",
    "isolation_forest",
    "lof",
    "ocsvm",
    "ecod",
    "copod",
    "hbos",
    "knn",
    "pca",
    "autoencoder",
    "vae",
    "deep_svdd",
    "dif",
    "ae1svm",
    "lunar",
    "lstm_autoencoder",
    "drift",
    "transform_dedup",
]
TYPES = [
    "missing_value",
    "duplicate",
    "univariate_outlier",
    "multivariate_outlier",
    "temporal_drift",
    "invalid_format",
]


def ordered(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows in registry order (families together), unknown names last."""
    rank = {name: i for i, name in enumerate(ORDER)}
    return frame.iloc[sorted(range(len(frame)), key=lambda i: rank.get(frame.index[i], 99))]


def _split(payload: dict) -> pd.DataFrame:
    return pd.DataFrame(payload["data"], payload["index"], payload["columns"])


def merged_typed(classical: Path, deep: Path) -> dict[str, pd.DataFrame]:
    """One matrix per carrier: the classical rows, then the neural rows of the same carrier."""
    out = {}
    for path in sorted(classical.glob("*.json")):
        base = _split(json.loads(path.read_text())["recall_mean"])
        extra = deep / path.name
        if extra.is_file():
            rows = _split(json.loads(extra.read_text())["recall_mean"])
            base = pd.concat([base, rows.drop(index="transform_dedup", errors="ignore")])
        out[json.loads(path.read_text())["name"]] = ordered(base)
    return out


def typed_fpr(classical: Path, deep: Path) -> pd.DataFrame:
    """Median and maximum over carriers of the share of clean rows each method flags."""
    columns: dict[str, list[float]] = {}
    for path in sorted(classical.glob("*.json")):
        for directory in (classical, deep):
            file = directory / path.name
            if file.is_file():
                for method, value in json.loads(file.read_text())["fpr_mean"].items():
                    columns.setdefault(method, []).append(value)
    table = pd.DataFrame(
        {m: {"median": float(np.median(v)), "max": float(np.max(v))} for m, v in columns.items()}
    ).T
    return ordered(table)


def _merge_fpr(evidence: Path, out: Path, extra: Path) -> pd.DataFrame:
    """Clean-row flag rate over the UCI carriers and the ADBench ones together."""
    columns: dict[str, list[float]] = {}
    for classical, deep in (
        (evidence / "typed_injection" / "runs", out / "typed_deep" / "runs"),
        (extra / "reference_classical", extra / "reference_deep"),
    ):
        for path in sorted(classical.glob("*.json")):
            for folder in (classical, deep):
                file = folder / path.name
                if file.is_file():
                    for method, value in json.loads(file.read_text())["fpr_mean"].items():
                        columns.setdefault(method, []).append(value)
    table = pd.DataFrame(
        {m: {"median": float(np.median(v)), "max": float(np.max(v))} for m, v in columns.items()}
    ).T
    return ordered(table)


def table_md(
    frame: pd.DataFrame, low: pd.DataFrame | None = None, high=None, digits: int = 2
) -> str:
    lines = [
        "| method | " + " | ".join(frame.columns) + " |",
        "|---|" + "---|" * len(frame.columns),
    ]
    for name in frame.index:
        if low is None:
            cells = [f"{v:.{digits}f}" for v in frame.loc[name]]
        else:
            cells = [
                f"{frame.loc[name, c]:.2f} [{low.loc[name, c]:.2f}, {high.loc[name, c]:.2f}]"
                for c in frame.columns
            ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def figure(frame: pd.DataFrame, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 0.3 * len(frame) + 1.6))
    tf._draw(ax, frame, title)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def deep_mean(runs: Path, pattern: str) -> pd.DataFrame:
    frames = [_split(json.loads(p.read_text())["recall"]) for p in sorted(runs.glob(pattern))]
    stack = pd.concat(frames, keys=range(len(frames)))
    return stack.groupby(level=1, sort=False).mean()


def synthetic_matrix(evidence: Path, deep: Path) -> pd.DataFrame:
    classical = pd.read_csv(evidence / "synthetic_recall.csv", index_col="method")
    classical = classical[[f"{t}_mean" for t in TYPES]].set_axis(TYPES, axis=1)
    rows = [classical, deep_mean(deep, "synthetic_seed_*.json")]
    lstm = [
        json.loads(p.read_text())["recall"]
        for p in sorted((evidence / "deep_typed").glob("seed_*.json"))
    ]
    if lstm:
        frame = pd.concat([_split(r) for r in lstm], keys=range(len(lstm)))
        rows.append(frame.groupby(level=1, sort=False).mean().loc[["lstm_autoencoder"]])
    return ordered(pd.concat(rows)[TYPES])


def schema_matrices(multi: Path, deep: Path) -> dict[str, pd.DataFrame]:
    classical = json.loads((multi / "multi_schema_results.json").read_text())["mean"]
    out = {}
    for name, payload in classical.items():
        base = _split(payload)
        if name == "customer":
            continue
        extra = deep_mean(deep, f"{name}_seed_*.json")
        out[name] = ordered(pd.concat([base, extra])[TYPES])
    return out


def real_table(classical_csv: Path, deep_json: Path) -> pd.DataFrame:
    cols = ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"]
    base = pd.read_csv(classical_csv, index_col=0)[[f"{c}_mean" for c in cols]]
    base.columns = cols
    runs = json.loads(deep_json.read_text())["runs"]
    rows = {}
    for name in runs[0]["methods"]:
        ok = [r["methods"][name] for r in runs if "error" not in r["methods"][name]]
        if ok:
            rows[name] = {c: float(np.mean([r[c] for r in ok])) for c in cols}
    return ordered(pd.concat([base, pd.DataFrame(rows).T[cols]]))


def build(evidence: Path, figures: Path) -> dict[str, object]:
    out = evidence / "full_registry"
    sections = []
    extra = evidence / "pool_extension" / "typed"
    typed = merged_typed(evidence / "typed_injection" / "runs", out / "typed_deep" / "runs")
    if (extra / "reference_classical").is_dir():  # the ADBench carriers of the pool extension
        typed |= merged_typed(extra / "reference_classical", extra / "reference_deep")
    pooled = ts.pooled(typed)
    sections += [
        f"### Typed injection, median recall over {len(typed)} real datasets",
        "",
        table_md(ordered(pooled["median"]), ordered(pooled["low"]), ordered(pooled["high"])),
    ]
    figure(
        ordered(pooled["median"]),
        f"Median detection rate over {len(typed)} real datasets (typed injection)",
        figures / "typed_pooled.png",
    )
    fpr = typed_fpr(evidence / "typed_injection" / "runs", out / "typed_deep" / "runs")
    if (extra / "reference_classical").is_dir():
        both = typed_fpr(extra / "reference_classical", extra / "reference_deep")
        fpr = both if len(fpr) == 0 else _merge_fpr(evidence, out, extra)
    sections += ["### Typed injection, clean rows flagged", "", table_md(fpr, digits=3)]
    synthetic = synthetic_matrix(evidence, out)
    sections += ["### Synthetic customer table, mean recall", "", table_md(synthetic)]
    figure(
        synthetic,
        "Mean detection rate by anomaly type (synthetic, 5 seeds)",
        figures / "heatmap_full.png",
    )
    for name, matrix in schema_matrices(evidence / "multi_schema", out / "schemas_deep").items():
        sections += [f"### Schema {name}, mean recall", "", table_md(matrix)]
    for dataset in ("credit_card", "cardio", "water_quality"):
        table = real_table(evidence / f"benchmark_{dataset}.csv", out / f"real_{dataset}.json")
        sections += [f"### {dataset}", "", table_md(table, digits=3)]
    (out / "summary.md").write_text("\n".join(sections) + "\n")
    return {"typed_datasets": len(typed), "synthetic_rows": list(synthetic.index)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--figures", type=Path, default=ROOT / "paper" / "figures")
    args = parser.parse_args(argv)
    print(json.dumps(build(args.evidence, args.figures)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
