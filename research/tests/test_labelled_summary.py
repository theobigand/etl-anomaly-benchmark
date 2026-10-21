"""Pool summary and the pre-registered hypothesis checks of labelled_pool.md."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_summary as ls  # noqa: E402

METHODS = ["zscore", "iqr", "isolation_forest"]


def _table():
    rng = np.random.default_rng(0)
    rows = []
    for k in range(30):
        prevalence = [0.02, 0.1, 0.3][k % 3]
        source = "adbench" if k < 15 else "uci"
        for method in METHODS:
            base = {"zscore": 0.3, "iqr": 0.2, "isolation_forest": 0.5}[method]
            rows.append(
                {
                    "problem": f"p{k}",
                    "source": source,
                    "prevalence": prevalence,
                    "method": method,
                    "pr_auc": base + rng.normal(0, 0.02),
                    "roc_auc": 0.8,
                    "flagged_pct": 100 * prevalence * (4 if method == "iqr" else 1),
                }
            )
    return pd.DataFrame(rows)


def test_median_with_a_bootstrap_interval_per_method():
    out = ls.pooled(_table(), resamples=200)
    assert set(out.index) == set(METHODS)
    row = out.loc["isolation_forest"]
    assert row["lo"] <= row["median"] <= row["hi"]
    assert abs(row["median"] - 0.5) < 0.05


def test_ranks_are_one_for_the_best_method_per_problem():
    ranks = ls.ranks(_table())
    assert ranks.loc["isolation_forest"].median() == 1
    assert ranks.loc["iqr"].median() == 3


def test_hypotheses_follow_their_preregistered_rules():
    h = ls.hypotheses(_table(), resamples=200)
    assert h["H1"]["supported"] is False  # IF wins every problem here
    assert h["H2"]["supported"] is True
    assert h["H4"]["supported"] is True
    assert h["H5"]["spearman"] >= 0.7
    assert set(h["H3"]["by_prevalence"]) == {"<5%", "5-20%", ">20%"}
