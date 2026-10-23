"""Published benchmark tables must agree with the archived result files."""

import re
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
METHODS = {
    "Z-score": "zscore",
    "IQR": "iqr",
    "Great Expectations": "great_expectations",
    "Isolation Forest": "isolation_forest",
    "LOF": "lof",
    "One-Class SVM": "ocsvm",
    "ECOD": "ecod",
    "COPOD": "copod",
    "HBOS": "hbos",
    "KNN": "knn",
    "PCA": "pca",
}


@pytest.mark.parametrize(
    ("label", "archive", "columns"),
    [
        (
            "fraud",
            "benchmark_credit_card.csv",
            ("precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct", "detect_s"),
        ),
        (
            "cardio",
            "benchmark_cardio.csv",
            ("precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"),
        ),
        (
            "water",
            "benchmark_water_quality.csv",
            ("precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"),
        ),
        (
            "synthetic",
            "synthetic_metrics.csv",
            ("precision", "recall", "f1", "roc_auc", "pr_auc", "detect_s"),
        ),
    ],
)
def test_published_numbers_match_archived_runs(label, archive, columns):
    manuscript = (ROOT / "paper/main.tex").read_text()
    match = re.search(rf"\\label\{{tab:{label}\}}(.*?)\\end\{{table\}}", manuscript, re.S)
    assert match, label
    index_column = "method" if label == "synthetic" else "detector"
    source = pd.read_csv(ROOT / "verification/evidence" / archive).set_index(index_column)
    seen = set()
    for line in match.group(1).splitlines():
        if "&" not in line:
            continue
        title, *cells = line.split("&")
        method = METHODS.get(title.strip())
        if method is None:
            continue
        seen.add(method)
        assert len(cells) == len(columns), (label, method)
        for column, cell in zip(columns, cells, strict=True):
            shown = Decimal(re.sub(r"[^0-9.]", "", cell))
            actual = Decimal(str(source.loc[method, f"{column}_mean"]))
            tolerance = Decimal("0.5") * Decimal(10) ** shown.as_tuple().exponent
            assert abs(actual - shown) <= tolerance, (label, method, column, shown, actual)
    extra = {"drift", "transform_dedup"} if label == "synthetic" else set()
    assert seen == set(source.index) - extra


def test_fixed_calibration_table_matches_both_archived_protocols():
    manuscript = (ROOT / "paper/main.tex").read_text()
    table = re.search(r"\\label\{tab:fixed-calibration\}(.*?)\\end\{table\}", manuscript, re.S)
    assert table
    datasets = {
        "Credit Card Fraud": "credit_card",
        "Cardio": "cardio",
        "Water Quality": "water_quality",
    }
    seen = set()
    for line in table.group(1).splitlines():
        title = line.split("&", 1)[0].strip()
        if title not in datasets:
            continue
        name = datasets[title]
        seen.add(name)
        baseline = pd.read_csv(ROOT / "verification/evidence" / f"benchmark_{name}.csv")
        fixed = pd.read_csv(ROOT / "verification/evidence" / f"fixed_benchmark_{name}.csv")
        baseline = baseline.set_index("detector").loc["isolation_forest"]
        fixed = fixed.set_index("detector").loc["isolation_forest"]
        shown = [Decimal(cell.strip().removesuffix(r"\\")) for cell in line.split("&")[1:]]
        actual = [
            baseline.f1_mean,
            fixed.f1_mean,
            baseline.flagged_pct_mean,
            fixed.flagged_pct_mean,
        ]
        assert len(shown) == len(actual)
        for rounded, value in zip(shown, actual, strict=True):
            assert abs(Decimal(str(value)) - rounded) <= Decimal("0.0005")
        assert baseline.pr_auc_mean == pytest.approx(fixed.pr_auc_mean)
    assert seen == set(datasets.values())


def test_contamination_sweep_table_matches_the_archived_sweep():
    manuscript = (ROOT / "paper/main.tex").read_text()
    table = re.search(r"\\label\{tab:contamination\}(.*?)\\end\{table\}", manuscript, re.S)
    assert table
    datasets = {
        "Credit Card Fraud": "credit_card",
        "Cardio": "cardio",
        "Water Quality": "water_quality",
        "Synthetic": "synthetic",
    }
    sweep = pd.read_csv(ROOT / "verification/evidence/contamination_sweep.csv")
    checked = 0
    for line in table.group(1).splitlines():
        if "&" not in line:
            continue
        title, contamination, *cells = (cell.strip() for cell in line.split("&"))
        if title not in datasets:
            continue
        is_prevalence = contamination.startswith("prev.")
        value = Decimal(re.search(r"\d+\.\d+", contamination).group())
        rows = sweep[(sweep.dataset == datasets[title]) & (sweep.is_prevalence == is_prevalence)]
        rows = rows[(rows.contamination.map(Decimal.from_float) - value).abs() < Decimal("0.0006")]
        assert len(rows) == 1, (title, contamination)
        for column, cell in zip(("precision", "recall", "flagged_pct"), cells, strict=True):
            shown = Decimal(re.sub(r"[^0-9.]", "", cell))
            actual = Decimal(str(rows.iloc[0][column]))
            tolerance = Decimal("0.5") * Decimal(10) ** shown.as_tuple().exponent
            assert abs(actual - shown) <= tolerance, (title, contamination, column, shown, actual)
        checked += 1
    assert checked == 8
