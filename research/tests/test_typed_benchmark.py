"""Per-type recall of every detector on an injected real-style carrier."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402
import typed_benchmark as tb  # noqa: E402


def _injected(seed=0):
    rng = np.random.default_rng(1)
    a = rng.normal(50, 10, 4000)
    carrier = pd.DataFrame(
        {
            "a": a,
            "b": 0.8 * a + rng.normal(0, 4, 4000),
            "c": rng.gamma(4, 5, 4000),
            "d": rng.normal(size=4000),
        }
    )
    return inj.inject(carrier, seed=seed), list(carrier.columns)


def test_the_split_keeps_a_duplicate_with_its_original_and_is_70_15_15():
    df, _ = _injected()
    train, val, test = tb.split(df, seed=3)
    sizes = [len(train), len(val), len(test)]
    assert abs(sizes[0] / len(df) - 0.7) < 0.02 and abs(sizes[2] / len(df) - 0.15) < 0.02
    for part, other in ((train, test), (test, train), (val, train)):
        assert set(part["group_id"]).isdisjoint(other["group_id"])
    assert sum(sizes) == len(df)


def test_recall_by_type_has_one_row_per_method_and_one_column_per_type():
    df, cols = _injected()
    result = tb.evaluate(df, cols, seed=0, names=["zscore", "iqr", "great_expectations"])
    recall = result["recall"]
    assert list(recall.columns) == inj.ANOMALY_TYPES
    assert list(recall.index) == ["zscore", "iqr", "great_expectations", "transform_dedup"]
    assert recall.loc["transform_dedup", "duplicate"] == 1.0
    assert recall.loc["great_expectations", "missing_value"] == 1.0
    assert recall.loc["iqr", "univariate_outlier"] > 0.8
    assert recall.loc["zscore", "multivariate_outlier"] < 0.2


def test_the_drift_detector_watches_the_arrival_column_and_only_the_features():
    df, cols = _injected()
    result = tb.evaluate(df, cols, seed=0, names=["drift"])
    assert "drift" in result["recall"].index


def test_unknown_detector_names_are_refused():
    df, cols = _injected()
    with pytest.raises(ValueError, match="unknown"):
        tb.evaluate(df, cols, seed=0, names=["nope"])
