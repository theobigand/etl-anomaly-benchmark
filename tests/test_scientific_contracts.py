"""Small counterexamples for the evaluation protocol."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

import run_synthetic_benchmark as synthetic_benchmark  # noqa: E402

from etl_benchmark.registry import clip_contamination  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES, make_synthetic  # noqa: E402


def test_synthetic_groups_never_cross_partitions():
    frame = make_synthetic(n_rows=1200, seed=7)
    parts = synthetic_benchmark._split_synthetic(frame, seed=7)
    ids = [set(part.customer_id) for part in parts]
    assert all(not ids[i] & ids[j] for i in range(3) for j in range(i + 1, 3))
    assert sorted(pd.concat(parts).customer_id) == sorted(frame.customer_id)
    assert all(set(ANOMALY_TYPES) <= set(part.anomaly_type) for part in parts)


@pytest.mark.parametrize(
    ("n_rows", "rate", "severity"),
    [(89, 0.03, 1.0), (200, -0.01, 1.0), (200, 0.2, 1.0), (200, 0.03, 0.0)],
)
def test_synthetic_rejects_infeasible_settings(n_rows, rate, severity):
    with pytest.raises(ValueError):
        make_synthetic(n_rows=n_rows, anomaly_rate=rate, severity=severity)


def test_zero_anomaly_rate_produces_clean_population():
    frame = make_synthetic(n_rows=200, anomaly_rate=0, seed=2)
    assert len(frame) == 200
    assert not frame.anomaly.any()
    assert set(frame.anomaly_type) == {"clean"}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01])
def test_contamination_rejects_invalid_prevalence(value):
    with pytest.raises(ValueError):
        clip_contamination(value)


def test_per_type_rejects_misaligned_indices():
    flags = pd.Series([True, False], index=[10, 11])
    kinds = pd.Series(["clean", "duplicate"], index=[11, 12])
    with pytest.raises(ValueError, match="index"):
        synthetic_benchmark._per_type(flags, kinds)


def test_per_type_golden_denominators():
    kinds = pd.Series(["clean", "clean", "duplicate", "duplicate", "invalid_format"])
    flags = pd.Series([True, False, True, False, True])
    recall, precision = synthetic_benchmark._per_type(flags, kinds)
    assert recall["duplicate"] == 0.5
    assert precision["duplicate"] == 0.5  # one true positive, one flagged clean
    assert recall["invalid_format"] == 1.0
    assert precision["invalid_format"] == 0.5
    assert np.isnan(recall["temporal_drift"])
    assert np.isnan(precision["temporal_drift"])
