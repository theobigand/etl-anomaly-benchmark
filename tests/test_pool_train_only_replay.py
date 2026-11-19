import numpy as np
import pandas as pd

from research.pool_preprocessing import prepare_frozen
from research.pool_train_only_replay import grouped_split


def _frame(rows=400, seed=0):
    rng = np.random.default_rng(seed)
    base = pd.DataFrame({"a": rng.integers(0, 40, rows), "b": rng.integers(0, 3, rows)})
    labels = (rng.random(rows) < 0.2).astype(int)
    return base.astype("string"), labels


def test_split_covers_every_row_once_and_keeps_identical_rows_together():
    frame, labels = _frame()
    parts = grouped_split(frame, labels, seed=1)
    positions = sorted(p for rows in parts.values() for p in rows)
    assert positions == list(range(len(frame)))
    owner = {p: name for name, rows in parts.items() for p in rows}
    for _, group in frame.groupby(["a", "b"]):
        assert len({owner[p] for p in group.index}) == 1


def test_split_is_deterministic_and_accepted_by_train_only_preparation():
    frame, labels = _frame()
    first, second = grouped_split(frame, labels, seed=2), grouped_split(frame, labels, seed=2)
    assert first == second
    assert grouped_split(frame, labels, seed=3) != first
    prepare_frozen(frame, first)  # raises if identical rows cross partitions


def test_every_partition_contains_anomalies():
    frame, labels = _frame()
    parts = grouped_split(frame, labels, seed=4)
    assert set(parts) == {"train", "validation", "test"}
    assert all(labels[parts[name]].any() for name in parts)
