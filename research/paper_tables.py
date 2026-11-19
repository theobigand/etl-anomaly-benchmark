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
#: table -> dataset of the separate neural timing run (``paper/measure_neural_times.py``)
TIMING_DATASET = {"fraud": "credit_card", "synthetic": "synthetic"}


def classical_means(label: str, evidence: Path) -> pd.DataFrame:
    archive = TABLES[label][0]
    index = "method" if label == "synthetic" else "detector"
    frame = pd.read_csv(evidence / archive).set_index(index)
    return frame[[f"{c}_mean" for c in COLUMNS[label]]].set_axis(COLUMNS[label], axis=1)


def neural_means(label: str, evidence: Path) -> pd.DataFrame:
    """Mean over seeds of the neural detectors.

    The benchmark runs timed the neural models under load, so their time comes from the separate
    timing run when it exists, and is left empty otherwise."""
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
    timing = evidence / "neural_timing" / "neural_times.json"
    if label in TIMING_DATASET and timing.is_file():
        mean = json.loads(timing.read_text())["mean_detect_s"][TIMING_DATASET[label]]
        for name in NEURAL:
            rows[name]["detect_s"] = mean[name]
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
        elif c in LOWER_IS_BETTER:  # neural times come from another run: never compared
            best[c] = table.loc[table.index.isin(CLASSICAL), c].min()
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
            if c in LOWER_IS_BETTER and name in NEURAL:
                text += "$^{c}$"
            elif c in best and round(value, digits) == round(best[c], digits):
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
        "Method & " + " & ".join(LABELS[c] for c in frame.columns) + r" \\",
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
        lines.append(f"{names[method]:<18} & " + " & ".join(cells) + r" \\")
        if method in ("great_expectations", "pca", "lunar"):
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


EXAMPLES = (
    ("adbench:fraud", "Fraud"),
    ("adbench:cardio", "Cardio"),
    ("adbench:annthyroid", "Annthyroid"),
    ("uci:73", "Mushroom"),
)


def example_rows(evidence: Path = EVIDENCE) -> str:
    """PR-AUC of every detector on four problems of the pool, the best of each column in bold."""
    import sys

    sys.path.insert(0, str(ROOT / "research"))
    import labelled_summary as ls

    runs = ls.load(evidence / "labelled_pool" / "runs") + ls.load(
        evidence / "full_registry" / "pool_deep" / "runs"
    )
    wide = ls.table(runs).pivot(index="problem", columns="method", values="pr_auc")
    best = {problem: wide.loc[problem].max() for problem, _ in EXAMPLES}
    lines = []
    for name in NAMES:
        cells = []
        for problem, _ in EXAMPLES:
            value = wide.loc[problem, name]
            if pd.isna(value):
                cells.append("--")
            elif round(value, 2) == round(best[problem], 2):
                cells.append(f"\\textbf{{{value:.2f}}}")
            else:
                cells.append(f"{value:.2f}")
        lines.append(f"{NAMES[name]:<18} & " + " & ".join(cells) + r" \\")
        if name in (list(NAMES)[2], list(NAMES)[10]):
            lines.append(r"\midrule")
    return "\n".join(lines)


#: detection-stage cost table: label, archive key (the two cost studies), in the order of the table
COST_ORDER = [
    ("Z-score", "zscore"),
    ("IQR", "iqr"),
    ("Isolation Forest", "isolation_forest"),
    ("Autoencoder (MLP)", "autoencoder"),
    ("LSTM autoencoder", "lstm_autoencoder"),
    ("LOF", "lof"),
    ("One-Class SVM", "ocsvm"),
    None,
    ("ECOD", "ecod"),
    ("COPOD", "copod"),
    ("HBOS", "hbos"),
    ("PCA", "pca"),
    ("KNN", "knn"),
    ("VAE", "vae"),
    ("Deep SVDD", "deep_svdd"),
    ("DIF", "dif"),
    ("AE1SVM", "ae1svm"),
    ("LUNAR", "lunar"),
]
COST_SIZES = (10_000, 100_000, 300_000)
ALL_SIZES = (1_000, 3_000, 10_000, 30_000, 100_000, 300_000)
#: the footnote letter of the memory cell when the largest size completed is not 3e5
COST_FOOTNOTE = {30_000: "a", 100_000: "b"}


def sig(value: float, digits: int) -> str:
    """``value`` with ``digits`` significant figures, trailing zeros kept, no exponent."""
    from math import floor, log10

    if value == 0:
        return "0"
    decimals = max(digits - 1 - floor(log10(abs(value))), 0)
    return f"{round(value, decimals):.{decimals}f}"


def cost_row(label: str, summary: dict) -> str:
    """One row of the cost table: three times, the growth exponent and the memory in MiB.

    Three significant figures for every time; the memory is the median resident-set increase at the
    largest size completed (footnote letter when that is not the largest size of the study).
    """
    largest = summary["largest_measured"]
    beyond = [n for n in ALL_SIZES if n > largest]
    cells = []
    for size in COST_SIZES:
        point = summary["points"].get(str(size))
        if point is not None:
            cells.append(f"{sig(point['detect_s_median'], 3)} s")
        elif summary["failures"].get("TIMEOUT") and size == beyond[0]:
            cells.append("$>300$ s")
        else:
            cells.append("not run")
    memory = summary["points"][str(largest)]["rss_delta_bytes_median"] / 2**20
    note = f"$^{{{COST_FOOTNOTE[largest]}}}$" if largest in COST_FOOTNOTE else ""
    return " & ".join(
        [label, *cells, f"{summary['growth_exponent']:.2f}", f"{round(memory)}{note}"]
    ) + r" \\"


def cost_rows(evidence: Path = EVIDENCE) -> str:
    """Rows of the cost table, from the two archived cost studies (the seven first, the ten later)."""
    summary: dict[str, dict] = {}
    for path in (
        evidence / "cost_study" / "cost_study.json",
        evidence / "full_registry" / "cost" / "cost_study.json",
    ):
        summary.update(json.loads(path.read_text())["summary"])
    lines = [r"\midrule" if item is None else cost_row(item[0], summary[item[1]]) for item in COST_ORDER]
    return "\n".join(lines)


def pct(value: float) -> str:
    """A percentage: two decimals below 1, one decimal from 1."""
    return f"{value:.2f}" if round(value, 2) < 1 else f"{value:.1f}"


def signed(value: float, decimals: int = 3) -> str:
    return f"{value:+.{decimals}f}"


#: dataset label, archive key, contamination values shown (None: the training prevalence)
CONTAMINATION_ROWS = [
    ("Credit Card Fraud", "credit_card", (0.001, 0.1, None)),
    None,
    ("Cardio", "cardio", (0.01, 0.2, None)),
    None,
    ("Water Quality", "water_quality", (None,)),
    ("Synthetic", "synthetic", (None,)),
]


def _grid_value(value: float, prevalence: bool) -> str:
    if prevalence:
        return rf"prev.\ {round(value, 3):g}"
    text = f"{value:g}"
    return text + "0" if len(text) == 3 else text


def contamination_rows(evidence: Path = EVIDENCE) -> str:
    """Rows of the contamination sweep (Isolation Forest, one seed), from its archived CSV."""
    sweep = pd.read_csv(evidence / "contamination_sweep.csv")
    lines = []
    for item in CONTAMINATION_ROWS:
        if item is None:
            lines.append(r"\midrule")
            continue
        label, key, wanted = item
        table = sweep[sweep["dataset"] == key]
        for value in wanted:
            row = (
                table[table["is_prevalence"]].iloc[0]
                if value is None
                else table[(table["contamination"] - value).abs() < 1e-9].iloc[0]
            )
            lines.append(
                f"{label:<17} & {_grid_value(row['contamination'], value is None)} "
                f"& {row['precision']:.2f} & {row['recall']:.2f} & {pct(row['flagged_pct'])} \\\\"
            )
    return "\n".join(lines)


def fixed_rows(evidence: Path = EVIDENCE) -> str:
    """Rows of the fixed-contamination table: Isolation Forest, training prevalence against 0.02."""
    lines = []
    for label, key in (
        ("Credit Card Fraud", "credit_card"),
        ("Cardio", "cardio"),
        ("Water Quality", "water_quality"),
    ):
        prev = pd.read_csv(evidence / f"benchmark_{key}.csv").set_index("detector")
        fixed = pd.read_csv(evidence / f"fixed_benchmark_{key}.csv").set_index("detector")
        a, b = prev.loc["isolation_forest"], fixed.loc["isolation_forest"]
        lines.append(
            f"{label:<17} & {a['f1_mean']:.3f} & {b['f1_mean']:.3f} "
            f"& {a['flagged_pct_mean']:.3f} & {b['flagged_pct_mean']:.3f} \\\\"
        )
    return "\n".join(lines)


def clustered_rows(evidence: Path = EVIDENCE) -> str:
    """Rows of the paired-difference table: problem and source bootstrap, Holm-adjusted p."""
    analysis = json.loads((evidence / "source_clustered" / "analysis.json").read_text())

    def cell(part: dict) -> str:
        low, high = part["mean_ci"]
        return f"{signed(part['mean'])} [{signed(low)}, {signed(high)}]"

    lines = []
    for item in analysis["comparisons"]:
        first, second = item["comparison"].split(" - ")
        lines.append(
            rf"{NAMES[first]} $-$ {NAMES[second]} & {item['problems']} & {cell(item['by_problem'])} "
            f"& {cell(item['by_source'])} & {item['holm_p_by_source']:.3f} \\\\"
        )
    return "\n".join(lines)


def replace_body(tex: str, label: str, body: str) -> str:
    pattern = re.compile(rf"(\\label\{{tab:{label}\}}.*?\\midrule\n).*?(\n\\bottomrule)", re.S)
    if not pattern.search(tex):
        raise ValueError(f"table {label} not found")
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), tex, count=1)


#: tables whose rows come from one archive each, rewritten after the four benchmark tables
EXTRA_TABLES = {
    "labelled": pool_rows,
    "examples": example_rows,
    "cost": cost_rows,
    "chrono": chrono_rows,
    "contamination": contamination_rows,
    "fixed-calibration": fixed_rows,
    "clustered": clustered_rows,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tex", type=Path, default=ROOT / "paper" / "main.tex")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--print", action="store_true", help="print the rows instead of writing")
    args = parser.parse_args(argv)
    tex = args.tex.read_text()
    bodies = {label: rows(label, args.evidence) for label in TABLES}
    bodies.update({label: write(args.evidence) for label, write in EXTRA_TABLES.items()})
    for label, body in bodies.items():
        if args.print:
            print(f"== {label}\n{body}")
        else:
            tex = replace_body(tex, label, body)
    if not args.print:
        args.tex.write_text(tex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
