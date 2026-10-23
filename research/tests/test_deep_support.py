"""Cap and seed of the neural detectors (protocol full_registry.md)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deep_support as ds  # noqa: E402


def _frame(n):
    return pd.DataFrame({"a": np.arange(float(n)), "b": np.arange(float(n)) ** 2})


def test_a_neural_detector_is_fitted_on_a_seeded_sample_of_at_most_the_cap():
    train = _frame(500)
    first = ds.capped(train, "vae", seed=3, cap=100)
    again = ds.capped(train, "vae", seed=3, cap=100)
    other = ds.capped(train, "vae", seed=4, cap=100)
    assert len(first) == 100 and first.equals(again) and not first.index.equals(other.index)


def test_every_other_detector_and_a_small_train_set_keep_all_rows():
    train = _frame(500)
    assert ds.capped(train, "isolation_forest", seed=3, cap=100) is train
    assert ds.capped(train, "vae", seed=3, cap=500) is train


def test_a_neural_detector_gets_the_seed_of_the_repetition_and_a_classical_one_does_not():
    assert ds.build("vae", 0.05, seed=7).random_state == 7
    assert not hasattr(ds.build("ecod", 0.05, seed=7), "random_state")
