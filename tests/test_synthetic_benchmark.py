import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from run_synthetic_benchmark import render_heatmap, run  # noqa: E402

from etl_benchmark.synthetic import ANOMALY_TYPES  # noqa: E402


def test_run_produces_metrics_and_heatmap(tmp_path):
    from etl_benchmark.synthetic import make_synthetic

    df = make_synthetic(n_rows=800, seed=0)
    metrics, heatmap = run(df)

    # every registered detector plus the dedup reference row
    assert "transform_dedup" in heatmap.index
    assert {"zscore", "iqr", "isolation_forest", "lof", "ocsvm"} <= set(heatmap.index)

    matrix = heatmap[ANOMALY_TYPES]
    assert matrix.to_numpy().min() >= 0.0
    assert matrix.max().max() <= 1.0

    # the dedup rule catches duplicates and nothing else
    assert heatmap.loc["transform_dedup", "duplicate"] == 1.0
    assert heatmap.loc["transform_dedup", "univariate_outlier"] == 0.0

    for col in ("precision", "recall", "f1", "roc_auc", "pr_auc"):
        assert metrics[col].between(0.0, 1.0).all()

    out = render_heatmap(heatmap, tmp_path / "hm.png")
    assert out.exists() and out.stat().st_size > 0


def test_great_expectations_leads_on_missing_values():
    from etl_benchmark.synthetic import make_synthetic

    _, heatmap = run(make_synthetic(n_rows=800, seed=1))

    assert (
        heatmap.loc["great_expectations", "missing_value"]
        == pd.Series(heatmap["missing_value"]).max()
    )
