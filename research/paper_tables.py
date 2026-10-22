"""LaTeX rows of the four benchmark tables of the paper, written from the archived results.

The classical rows come from the archived benchmark files, the neural rows from the runs of
``full_registry.py``. The paper keeps the rows of every table in registry order, so that no
number is typed by hand.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "verification" / "evidence"
NAMES = {
    "zscore": "Z-score",
    "iqr": "IQR",
    "great_expectations": "Great Expectations",
    "isolation_forest": "Isolation Forest",
    "lof": "LOF",
    "ocsvm": "One-Class SVM",
    "ecod": "ECOD",
    "copod": "COPOD",
    "hbos": "HBOS",
    "knn": "KNN",
    "pca": "PCA",
    "autoencoder": "Autoencoder",
    "vae": "VAE",
    "deep_svdd": "Deep SVDD",
    "dif": "DIF",
    "ae1svm": "AE1SVM",
    "lunar": "LUNAR",
}
CLASSICAL = list(NAMES)[:11]
NEURAL = list(NAMES)[11:]
#: label -> (archive, neural source, columns, decimals of the metrics, other decimals)
TABLES = {
    "fraud": ("benchmark_credit_card.csv", "real_credit_card.json", 3),
    "cardio": ("benchmark_cardio.csv", "real_cardio.json", 2),
    "water": ("benchmark_water_quality.csv", "real_water_quality.json", 2),
    "synthetic": ("synthetic_metrics.csv", "synthetic", 3),
}
COLUMNS = {
    "fraud": ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct", "detect_s"],
    "cardio": ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"],
    "water": ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"],
    "synthetic": ["precision", "recall", "f1", "roc_auc", "pr_auc", "detect_s"],
}
HIGHER_IS_BETTER = {"precision", "recall", "f1", "roc_auc", "pr_auc"}
LOWER_IS_BETTER = {"detect_s"}
TIME_DECIMALS = {"fraud": 2, "synthetic": 3}


def classical_means(label: str, evidence: Path) -> pd.DataFrame:
    archive = TABLES[label][0]
    index = "method" if label == "synthetic" else "detector"
    frame = pd.read_csv(evidence / archive).set_index(index)
    return frame[[f"{c}_mean" for c in COLUMNS[label]]].set_axis(COLUMNS[label], axis=1)


def neural_means(label: str, evidence: Path) -> pd.DataFrame:
    """Mean over seeds of the neural detectors; the time is left empty (measured under load)."""
    source = TABLES[label][1]
    columns = [c for c in COLUMNS[label] if c not in LOWER_IS_BETTER]
    folder = evidence / "full_registry"
    rows: dict[str, dict[str, float]] = {}
    if source == "synthetic":
        runs = [
            json.loads(p.read_text())["metrics"]
            for p in sorted(folder.glob("synthetic_seed_*.json"))
        ]
        for name in NEURAL:
            rows[name] = {c: sum(r[name][c] for r in runs) / len(runs) for c in columns}
    else:
        runs = json.loads((folder / source).read_text())["runs"]
        for name in NEURAL:
            ok = [r["methods"][name] for r in runs if "error" not in r["methods"][name]]
            rows[name] = {c: sum(r[c] for r in ok) / len(ok) for c in columns}
    return pd.DataFrame(rows).T


def rows(label: str, evidence: Path = EVIDENCE) -> str:
    """The body of a table: one line per detector, the best value of each column in bold."""
    base = classical_means(label, evidence)
    neural = neural_means(label, evidence)
    table = pd.concat([base.reindex(CLASSICAL), neural.reindex(columns=base.columns)])
    table = table.dropna(how="all")  # a detector that was not run on this dataset has no row
    metric_digits = TABLES[label][2]
    best = {}
    for c in COLUMNS[label]:
        if c in HIGHER_IS_BETTER:
            best[c] = table[c].max()
        elif c in LOWER_IS_BETTER:
            best[c] = table[c].min()
    lines = []
    present = list(table.index)
    for name in present:
        cells = []
        for c in COLUMNS[label]:
            value = table.loc[name, c]
            if pd.isna(value):
                cells.append("--")
                continue
            digits = (
                metric_digits
                if c in HIGHER_IS_BETTER
                else 1
                if c == "flagged_pct"
                else TIME_DECIMALS[label]
            )
            text = f"{value:.{digits}f}"
            if c in best and round(value, digits) == round(best[c], digits):
                text = f"\\textbf{{{text}}}"
            cells.append(text)
        lines.append(f"{NAMES[name]:<18} & " + " & ".join(cells) + r" \\")
        families = [n for n in present if n in CLASSICAL]
        if name in (families[2], families[-1]):
            lines.append(r"\midrule")
    return "\n".join(lines)


def pool_rows(evidence: Path = EVIDENCE) -> str:
    """Rows of the labelled-pool table: problems run, median PR-AUC with its interval, ROC, rank."""
    results = json.loads((evidence / "labelled_pool" / "labelled_results.json").read_text())

    def frame(payload: dict) -> pd.DataFrame:
        return pd.DataFrame(payload["data"], payload["index"], payload["columns"])

    pr = pd.concat([frame(results["pr_auc"]), frame(results["deep"]["pr_auc"])])
    roc = pd.concat([frame(results["roc_auc"]), frame(results["deep"]["roc_auc"])])
    ranks = results["median_rank_all"]
    counts: dict[str, int] = {}
    for folder in (
        evidence / "labelled_pool" / "runs",
        evidence / "full_registry" / "pool_deep" / "runs",
    ):
        for path in folder.glob("*.json"):
            for method in json.loads(path.read_text()).get("metrics", {}):
                counts[method] = counts.get(method, 0) + 1
    lines = []
    for name in NAMES:
        a = pr.loc[name]
        lines.append(
            f"{NAMES[name]:<18} & {counts[name]} & {a['median']:.3f} "
            f"[{a['lo']:.3f}, {a['hi']:.3f}] & {roc.loc[name, 'median']:.3f} "
            f"& {ranks[name]:.1f} \\\\"
        )
        if name in (list(NAMES)[2], list(NAMES)[10]):
            lines.append(r"\midrule")
    return "\n".join(lines)


def chrono_rows(evidence: Path = EVIDENCE) -> str:
    """Rows of the chronological-pilot table, in registry order."""
    pilot = json.loads((evidence / "temporal_pilot" / "temporal_pilot.json").read_text())
    lines = []
    for name in NAMES:
        if name not in pilot["chronological"]:
            continue
        chron, strat = pilot["chronological"][name], pilot["stratified"][name]
        ci = chron["pr_auc_ci"]
        lines.append(
            f"{NAMES[name]:<18} & ${strat['pr_auc']['mean']:.3f} "
            f"\\pm {strat['pr_auc']['std']:.3f}$ "
            f"& ${chron['pr_auc']:.3f}$ [{ci['ci_low']:.3f}, {ci['ci_high']:.3f}] "
            f"& {chron['roc_auc']:.3f} & {chron['flagged_pct']:.2f} \\\\"
        )
        if name == list(NAMES)[2]:
            lines.append(r"\midrule")
    return "\n".join(lines)


LABELS = {
    "missing_value": "Miss.",
    "duplicate": "Dup.",
    "univariate_outlier": "Uni.",
    "multivariate_outlier": "Multi.",
    "temporal_drift": "Drift",
    "invalid_format": "Inv.",
}
EXTRA_NAMES = {
    "lstm_autoencoder": "LSTM autoencoder",
    "drift": "Drift detector",
    "transform_dedup": "Dedup rule",
}


def matrix_table(frame: pd.DataFrame, caption: str, label: str) -> str:
    """A LaTeX table of mean recall by method and type, the best value of each column in bold."""
    best = frame.max()
    lines = [
        r"\begin{table}[t]",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{l" + "c" * len(frame.columns) + "}",
        r"\toprule",
        "Method & " + " & ".join(LABELS[c] for c in frame.columns) + r" \\\\",
        r"\midrule",
    ]
    names = {**NAMES, **EXTRA_NAMES}
    for method in frame.index:
        cells = []
        for column in frame.columns:
            text = f"{frame.loc[method, column]:.2f}"
            if method in NAMES and round(frame.loc[method, column], 2) == round(best[column], 2):
                text = f"\\textbf{{{text}}}"
            cells.append(text)
        lines.append(f"{names[method]:<18} & " + " & ".join(cells) + r" \\\\")
        if method in ("great_expectations", "pca", "lunar"):
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def replace_body(tex: str, label: str, body: str) -> str:
    pattern = re.compile(rf"(\\label\{{tab:{label}\}}.*?\\midrule\n).*?(\n\\bottomrule)", re.S)
    if not pattern.search(tex):
        raise ValueError(f"table {label} not found")
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), tex, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tex", type=Path, default=ROOT / "paper" / "main.tex")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--print", action="store_true", help="print the rows instead of writing")
    args = parser.parse_args(argv)
    tex = args.tex.read_text()
    for label in TABLES:
        body = rows(label, args.evidence)
        if args.print:
            print(f"== {label}\n{body}")
        else:
            tex = replace_body(tex, label, body)
    if not args.print:
        args.tex.write_text(tex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
