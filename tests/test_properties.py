"""Bounded generative checks of accounting and split invariants."""

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from etl_benchmark.split import stratified_split
from etl_benchmark.synthetic import ANOMALY_TYPES, make_synthetic

pytestmark = pytest.mark.property


@settings(max_examples=15, deadline=None)
@given(n=st.integers(min_value=120, max_value=700), seed=st.integers(min_value=0, max_value=1000))
def test_synthetic_population_accounting(n, seed):
    frame = make_synthetic(n_rows=n, seed=seed)
    k = max(round(0.03 * n), 15)
    counts = frame.anomaly_type.value_counts()
    assert len(frame) == n + k
    assert counts["clean"] == n - 5 * k
    assert all(counts[kind] == k for kind in ANOMALY_TYPES)
    assert frame.anomaly.equals(frame.anomaly_type.ne("clean"))
    assert frame.customer_id.nunique() == n


@settings(max_examples=20, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10000))
def test_split_is_a_seeded_partition_with_balanced_labels(seed):
    frame = pd.DataFrame({"row_id": np.arange(200), "label": [0] * 160 + [1] * 40})
    parts = stratified_split(frame, "label", seed=seed)
    assert sorted(pd.concat(parts).row_id) == list(range(200))
    assert all(abs(part.label.mean() - 0.2) < 0.04 for part in parts)
    assert all(part.index.equals(pd.RangeIndex(len(part))) for part in parts)
