"""The synthetic sequence stream behaves as pre-registered, and the comparison keeps its alignment."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lstm_pilot as lp  # noqa: E402

from etl_benchmark.datasets import ANOMALY_COLUMN  # noqa: E402


def test_the_synthetic_anomalies_stay_inside_the_marginal_range_but_break_continuity():
    frame = lp.synthetic_sequence_stream(n=6000, rate=0.02, seed=1)
    x = frame[[c for c in frame.columns if c.startswith("f")]].to_numpy()
    label = frame[ANOMALY_COLUMN].to_numpy().astype(bool)
    assert 0.01 < label.mean() < 0.03
    assert np.abs(x[label]).max() <= np.abs(x).max()
    step = np.abs(np.diff(x, axis=0, prepend=x[:1])).mean(axis=1)
    assert step[label].mean() > 2 * step[~label].mean()


def test_the_comparison_scores_the_same_test_rows_with_both_models():
    frame = lp.synthetic_sequence_stream(n=1500, rate=0.03, seed=2)
    n = len(frame)
    cols = [c for c in frame.columns if c.startswith("f")]
    train, val, test = (
        frame.iloc[: n * 6 // 10],
        frame.iloc[n * 6 // 10 : n * 8 // 10],
        frame.iloc[n * 8 // 10 :],
    )
    out = lp.compare(train, val, test, cols, seed=1, fit_rows=400, window=4, hidden=8, max_epochs=2)
    assert (
        len(out["y"])
        == len(out["autoencoder"]["scores"])
        == len(out["lstm"]["scores"])
        == len(test)
    )
    assert out["lstm"]["settings"]["epochs_run"] <= 2 and out["lstm"]["settings"]["device"] == "cpu"
