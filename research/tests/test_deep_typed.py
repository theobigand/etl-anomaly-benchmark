"""Deep rows in the per-type matrix (issue #64); miniature runs, needs the LSTM environment."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deep_typed as dt  # noqa: E402

TYPES = [
    "missing_value",
    "duplicate",
    "univariate_outlier",
    "multivariate_outlier",
    "temporal_drift",
    "invalid_format",
]


def test_one_seed_adds_the_two_deep_rows_next_to_the_existing_methods():
    out = dt.run_seed(seed=1, rows=1500, max_epochs=3)
    recall = pd.DataFrame(out["recall"]["data"], out["recall"]["index"], out["recall"]["columns"])
    assert {"zscore", "isolation_forest", "autoencoder", "lstm_autoencoder"} <= set(recall.index)
    assert list(recall.columns) == TYPES
    assert recall.loc["lstm_autoencoder"].between(0, 1).all()
    assert set(out["deep"]) == {"autoencoder", "lstm_autoencoder"}
    for settings in out["deep"].values():
        assert 0 <= settings["fpr"] <= 1


def test_the_lstm_run_records_epochs_and_whether_it_converged():
    out = dt.run_seed(seed=1, rows=1500, max_epochs=2)
    lstm = out["deep"]["lstm_autoencoder"]["settings"]
    assert lstm["epochs_run"] <= 2 and lstm["converged"] is False
    assert lstm["max_epochs"] == 2


def test_the_same_seed_gives_the_same_matrix():
    a = dt.run_seed(seed=2, rows=1200, max_epochs=2)
    b = dt.run_seed(seed=2, rows=1200, max_epochs=2)
    assert a["recall"] == b["recall"]


def _frames():
    types = TYPES
    index = ["zscore", "iqr", "isolation_forest", "autoencoder", "lstm_autoencoder"]
    frames = []
    for seed in range(5):
        base = pd.DataFrame(0.2, index=index, columns=types)
        base.loc["lstm_autoencoder", "temporal_drift"] = 0.6
        base.loc["autoencoder", "multivariate_outlier"] = 0.5
        base.loc["isolation_forest", "multivariate_outlier"] = 0.5
        frames.append(base + seed * 0.001)
    return frames


def test_hypotheses_follow_the_preregistered_rules():
    deep = [
        {
            "autoencoder": {"settings": {"converged": True}},
            "lstm_autoencoder": {"settings": {"converged": True}},
        }
        for _ in range(5)
    ]
    h = dt.hypotheses(_frames(), deep)
    assert h["H1"]["supported"] is True
    assert h["H2"]["supported"] is True
    assert h["H3"]["supported"] is True
    assert h["H4"]["supported"] is True
    deep[0]["lstm_autoencoder"]["settings"]["converged"] = False
    deep[1]["lstm_autoencoder"]["settings"]["converged"] = False
    assert dt.hypotheses(_frames(), deep)["H3"]["supported"] is False


def test_mean_and_std_over_seeds():
    mean, std = dt.mean_std(_frames())
    assert np.isclose(mean.loc["zscore", "missing_value"], 0.202)
    assert std.loc["zscore", "missing_value"] > 0
