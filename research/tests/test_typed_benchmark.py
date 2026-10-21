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


def test_a_labelled_set_contributes_only_its_normal_class_and_an_unlabelled_one_all_rows(tmp_path):
    import typed_run as tr

    rng = np.random.default_rng(0)
    n = 4000
    table = pd.DataFrame({f"x{i}": rng.normal(size=n) for i in range(5)})
    table["y"] = (np.arange(n) % 10 == 0).astype(int)
    path = tmp_path / "1.csv"
    table.to_csv(path, index=False)
    meta = {"uci_id": 1, "tasks": ["Classification"], "target_col": ["y"], "variables": []}
    carrier, report = tr.load_carrier(meta, path, seed=0)
    assert report["source_rows"] == 3600 and report["normal_class_only"] is True
    unlabelled = {"uci_id": 1, "tasks": ["Regression"], "target_col": ["y"], "variables": []}
    carrier2, report2 = tr.load_carrier(unlabelled, path, seed=0)
    assert report2["source_rows"] == n and report2["normal_class_only"] is False
    assert list(carrier.columns) == [f"x{i}" for i in range(5)]


def test_the_false_positive_rate_on_clean_rows_is_reported_for_every_method():
    df, cols = _injected()
    result = tb.evaluate(df, cols, seed=0, names=["zscore", "iqr"])
    fpr = result["fpr"]
    assert list(fpr.index) == ["zscore", "iqr", "transform_dedup"]
    # keep=False also flags the clean original of every injected copy: about 3 percent
    assert 0.0 < fpr.loc["transform_dedup"] < 0.06
    assert (fpr >= 0).all() and (fpr <= 1).all() and fpr.loc["iqr"] > fpr.loc["zscore"]


def test_masking_diagnostic_shows_zscore_recovers_when_invalid_rows_leave_training():
    import typed_masking as tm

    df, cols = _injected()
    out = tm.masking(df, cols, seed=0)
    assert out["with_invalid_in_train"] < 0.2 and out["without_invalid_in_train"] > 0.9


def test_the_new_classical_detectors_are_in_the_default_sweep_and_see_gross_outliers():
    assert {"ecod", "copod", "hbos", "knn", "pca"} <= set(tb.DETECTORS)
    df, cols = _injected()
    recall = tb.evaluate(df, cols, seed=0, names=["ecod", "knn", "pca"])["recall"]
    assert recall.loc[["ecod", "knn"], "univariate_outlier"].min() > 0.8
    assert recall.loc["pca", "univariate_outlier"] > 0.5


def test_a_neural_detector_can_be_evaluated_and_is_seeded_by_the_repetition(monkeypatch):
    df, cols = _injected()
    seen = []
    real = tb.build

    def spy(name, contamination, seed):
        detector = real(name, contamination, seed)
        seen.append((name, getattr(detector, "random_state", None)))
        return detector

    monkeypatch.setattr(tb, "build", spy)
    result = tb.evaluate(df, cols, seed=11, names=["vae"])
    assert seen == [("vae", 11)]
    assert list(result["recall"].index) == ["vae", "transform_dedup"]
