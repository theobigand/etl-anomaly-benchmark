import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from run_synthetic_benchmark import evaluate, render_heatmap, run  # noqa: E402

from etl_benchmark.synthetic import ANOMALY_TYPES, make_synthetic  # noqa: E402


def test_evaluate_single_split_shapes():
    res = evaluate(make_synthetic(n_rows=1200, seed=0), seed=0)

    for key in ("metrics", "recall", "precision"):
        assert "transform_dedup" in res[key].index
        assert {"zscore", "iqr", "isolation_forest", "lof", "ocsvm"} <= set(res[key].index)

    rec = res["recall"][ANOMALY_TYPES]
    assert rec.to_numpy()[~pd.isna(rec.to_numpy())].min() >= 0.0
    assert rec.max().max() <= 1.0
    # dedup rule catches duplicates and nothing else
    assert res["recall"].loc["transform_dedup", "duplicate"] == 1.0
    assert res["recall"].loc["transform_dedup", "univariate_outlier"] == 0.0


def test_run_averages_over_seeds_and_reports_std():
    r = run([0, 1], rows=1200)

    for key in ("metrics", "recall", "precision"):
        assert f"{key}_mean" in r and f"{key}_std" in r
        std = r[f"{key}_std"]
        if key == "metrics":
            assert pd.isna(std.loc["transform_dedup", "detect_s"])
            std = std.drop(index="transform_dedup")
        assert (std.to_numpy() >= 0).all()

    for col in ("precision", "recall", "f1", "roc_auc", "pr_auc"):
        assert r["metrics_mean"][col].between(0.0, 1.0).all()

    # per-type precision is a real column now, not just recall
    assert set(ANOMALY_TYPES) <= set(r["precision_mean"].columns)


def test_great_expectations_still_leads_on_missing_values():
    r = run([0, 1], rows=1500)
    col = r["recall_mean"]["missing_value"]
    assert col.idxmax() == "great_expectations"


def test_render_heatmap_writes_a_file(tmp_path):
    r = run([0], rows=1000)
    out = render_heatmap(r["recall_mean"], tmp_path / "hm.png")
    assert out.exists() and out.stat().st_size > 0


def test_ml_contamination_tracks_prevalence():
    # synthetic prevalence is ~0.17, well inside PyOD bounds, so the ML
    # detectors should flag roughly that share rather than a fixed 10%.
    res = evaluate(make_synthetic(n_rows=2000, seed=3), seed=3)
    flagged = res["metrics"].loc["isolation_forest", "flagged_pct"]
    assert 8.0 < flagged < 30.0


def test_one_seed_synthetic_std_is_not_zero():
    result = run([0], rows=1000)
    assert result["recall_std"]["duplicate"].isna().all()
