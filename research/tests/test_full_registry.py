"""Neural detectors on real data and the synthetic matrix, and H3 to H5 (full_registry.md)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import full_registry as fr  # noqa: E402

from etl_benchmark.datasets import DatasetSpec  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES  # noqa: E402

FAST = ("deep_svdd", "lunar")


def _spec(tmp_path):
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"V1": rng.normal(size=600), "V2": rng.normal(size=600)})
    df["Class"] = 0
    df.loc[:29, "Class"] = 1
    df.loc[:29, ["V1", "V2"]] += 6
    csv = tmp_path / "toy.csv"
    df.sample(frac=1.0, random_state=1).to_csv(csv, index=False)
    return DatasetSpec(name="toy", csv=csv, label_column="Class", positive_value=1)


def test_a_real_split_scores_each_neural_detector_with_the_seed_of_the_repetition(tmp_path):
    spec = _spec(tmp_path)
    run = fr.real_seed(spec, spec.load(), seed=3, names=FAST)
    assert run["seed"] == 3 and run["fit_rows"] == 420
    assert list(run["methods"]) == list(FAST)
    for row in run["methods"].values():
        assert 0.0 <= row["roc_auc"] <= 1.0 and row["settings"]["random_state"] == 3
        assert set(fr.METRICS) <= set(row)


def test_a_failing_neural_detector_is_recorded_with_its_reason(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(fr, "detect", fail)
    spec = _spec(tmp_path)
    run = fr.real_seed(spec, spec.load(), seed=1, names=FAST)
    assert all("boom" in row["error"] for row in run["methods"].values())


def test_the_real_summary_averages_over_seeds_and_leaves_out_a_model_that_never_ran():
    ok = dict.fromkeys(fr.METRICS, 0.5) | {"settings": {}}
    runs = [
        {"methods": {"vae": ok | {"f1": 0.2}, "lunar": {"error": "x"}}},
        {"methods": {"vae": ok | {"f1": 0.4}, "lunar": {"error": "y"}}},
    ]
    table = fr.real_summary(runs, names=("vae", "lunar"))
    assert list(table.index) == ["vae"]
    assert table.loc["vae", "f1_mean"] == pytest.approx(0.3) and table.loc["vae", "seeds"] == 2


def test_a_synthetic_seed_gives_recall_and_precision_for_each_type():
    run = fr.synthetic_seed(seed=2, rows=1500, names=FAST)
    recall = fr._frame(run["recall"])
    assert list(recall.index) == list(FAST) and list(recall.columns) == ANOMALY_TYPES
    assert run["errors"] == {} and set(run["fpr"]) == set(FAST)
    assert set(run["metrics"]) == set(FAST)
    assert {"precision", "recall", "f1", "roc_auc", "pr_auc"} <= set(run["metrics"]["lunar"])
    assert run["settings"]["lunar"]["random_state"] == 2 and run["settings"]["lunar"]["seconds"] > 0


def test_the_mean_matrix_averages_the_seeds():
    def run(value):
        frame = pd.DataFrame({t: [value] for t in ANOMALY_TYPES}, index=["vae"])
        return {
            "recall": {"data": frame.values.tolist(), "index": ["vae"], "columns": ANOMALY_TYPES}
        }

    mean = fr.mean_matrix([run(0.2), run(0.4)])
    assert mean.loc["vae", "temporal_drift"] == pytest.approx(0.3)


def _classical(**override):
    rows = {m: 0.1 for m in ("zscore", "iqr", "great_expectations", "lof", "ocsvm")}
    rows |= {
        "isolation_forest": 0.9,
        "ecod": 0.1,
        "copod": 0.1,
        "hbos": 0.0,
        "knn": 0.5,
        "pca": 0.5,
    }
    frame = pd.DataFrame({t: 0.2 for t in ANOMALY_TYPES}, index=list(rows))
    frame["multivariate_outlier"] = pd.Series(rows)
    for name, value in override.items():
        frame.loc[name, "multivariate_outlier"] = value
    return frame


def _deep(drift=0.1, autoencoder=0.5):
    frame = pd.DataFrame(0.2, index=list(fr.DEEP_NAMES), columns=ANOMALY_TYPES)
    frame["temporal_drift"] = drift
    frame.loc["autoencoder", "temporal_drift"] = 0.1  # an earlier detector, below the bound
    frame.loc["autoencoder", "multivariate_outlier"] = autoencoder
    return frame


def test_h3_needs_weak_marginal_models_and_a_gap_of_half_to_the_isolation_forest():
    assert fr.hypotheses(_classical(), _deep())["H3"]["supported"]
    assert not fr.hypotheses(_classical(ecod=0.25), _deep())["H3"]["supported"]
    assert not fr.hypotheses(_classical(isolation_forest=0.6, ecod=0.15), _deep())["H3"][
        "supported"
    ]


def test_h4_compares_pca_with_the_autoencoder_within_ten_points():
    assert fr.hypotheses(_classical(pca=0.5), _deep(autoencoder=0.59))["H4"]["supported"]
    assert not fr.hypotheses(_classical(pca=0.5), _deep(autoencoder=0.61))["H4"]["supported"]


def test_h5_allows_ten_points_over_the_best_earlier_row_level_drift_recall():
    classical = _classical()
    classical["temporal_drift"] = 0.2
    classical.loc["lof", "temporal_drift"] = 0.4  # the best earlier row-level detector
    assert fr.hypotheses(classical, _deep(drift=0.5))["H5"]["supported"]
    assert not fr.hypotheses(classical, _deep(drift=0.51))["H5"]["supported"]
    assert fr.hypotheses(classical, _deep(drift=0.5))["H5"]["best_earlier"]["method"] == "lof"
