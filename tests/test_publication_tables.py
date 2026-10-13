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
