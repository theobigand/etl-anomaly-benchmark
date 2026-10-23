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


def _medians(values):
    rows = []
    for k in range(20):
        for method, base in values.items():
            rows.append(
                {
                    "problem": f"p{k}",
                    "source": "uci",
                    "prevalence": 0.1,
                    "method": method,
                    "pr_auc": base,
                    "roc_auc": 0.8,
                    "flagged_pct": 10.0,
                }
            )
    return pd.DataFrame(rows)


def _classical(**override):
    base = {"isolation_forest": 0.30, "zscore": 0.2, "ecod": 0.25, "copod": 0.25}
    base |= {"hbos": 0.2, "knn": 0.28, "pca": 0.22} | override
    return _medians(base)


def _runs(method, failed=0, total=20, skipped=0):
    runs = []
    for k in range(total):
        run = {"problem": f"p{k}", "skipped": [method] if k < skipped else [], "errors": {}}
        if skipped <= k < skipped + failed:
            run["errors"] = {method: [{"seed": 42, "error": "boom"}]}
        runs.append(run)
    return runs


def test_h1_holds_when_a_new_classical_detector_beats_isolation_forest():
    deep = _medians({"vae": 0.2})
    assert ls.registry_hypotheses(_classical(ecod=0.31), deep, _runs("vae"))["H1"]["supported"]
    assert not ls.registry_hypotheses(_classical(), deep, _runs("vae"))["H1"]["supported"]


def test_h2_allows_a_margin_of_two_points_over_the_best_classical_detector():
    classical = _classical()
    within = ls.registry_hypotheses(classical, _medians({"vae": 0.319}), _runs("vae"))
    beyond = ls.registry_hypotheses(classical, _medians({"vae": 0.33}), _runs("vae"))
    assert within["H2"]["supported"] and not beyond["H2"]["supported"]
    assert within["H2"]["best_classical"] == {"method": "isolation_forest", "median": 0.3}


def test_h6_counts_failures_among_the_problems_where_the_model_was_not_skipped():
    deep = _medians({"vae": 0.2})
    one_in_twenty = ls.registry_hypotheses(_classical(), deep, _runs("vae", failed=1))["H6"]
    two_in_twenty = ls.registry_hypotheses(_classical(), deep, _runs("vae", failed=2))["H6"]
    assert one_in_twenty["supported"] and not two_in_twenty["supported"]
    skipped = ls.registry_hypotheses(_classical(), deep, _runs("vae", failed=1, skipped=10))["H6"]
    assert skipped["failures"]["vae"] == {"failed": 1, "problems": 10} and not skipped["supported"]
