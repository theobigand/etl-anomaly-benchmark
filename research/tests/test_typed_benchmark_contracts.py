"""Stratum choice, per-type scoring and argument routing of the typed benchmark."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402
import typed_benchmark as tb  # noqa: E402
from test_typed_benchmark import _injected  # noqa: E402

from etl_benchmark.quality import TemporalDriftDetector  # noqa: E402


def test_the_drift_detector_is_built_on_the_arrival_column_and_other_names_use_the_shared_builder(
    monkeypatch,
):
    drift = tb._build("drift", 0.1, ["a", "b"], 3)
    assert isinstance(drift, TemporalDriftDetector)
    assert drift.time_column == "t" and drift._user_columns == ["a", "b"]
    seen = []
    monkeypatch.setattr(tb, "build", lambda *args: seen.append(args) or "model")
    assert tb._build("zscore", 0.1, ["a"], 3) == "model"
    assert seen == [("zscore", 0.1, 3)]


def test_a_group_holding_a_duplicate_is_stratified_as_a_duplicate_and_others_by_their_first_type(
    monkeypatch,
):
    df = pd.DataFrame(
        {
            "group_id": [9, 9, 4, 4, 7, 7, 2],
            "anomaly_type": ["clean", "duplicate", "clean", "clean", "missing_value", "clean", "x"],
        }
    )
    seen = {}

    def spy(groups, column, ratios, seed):
        seen.update(groups=groups.copy(), column=column, ratios=ratios, seed=seed)
        return [groups.iloc[:2], groups.iloc[2:3], groups.iloc[3:]]

    monkeypatch.setattr(tb, "stratified_split", spy)
    parts = tb.split(df, 11)
    assert seen["groups"]["group_id"].tolist() == [9, 4, 7, 2]
    assert seen["groups"]["stratum"].tolist() == ["duplicate", "clean", "missing_value", "x"]
    assert seen["column"] == "stratum" and seen["seed"] == 11
    assert tuple(seen["ratios"]) == tuple(tb.config.SPLIT_RATIOS)
    assert [p["group_id"].tolist() for p in parts] == [[9, 9, 4, 4], [7, 7], [2]]
    for part in parts:
        assert list(part.columns) == ["group_id", "anomaly_type"]
        assert part.index.tolist() == list(range(len(part)))


def test_recall_and_precision_are_scored_against_the_clean_rows_only():
    types = pd.Series(["clean", "clean", "clean", "missing_value", "missing_value", "duplicate"])
    flags = pd.Series([True, False, False, True, False, True])
    recall, precision = tb._per_type(flags, types)
    assert set(recall) == set(precision) == set(inj.ANOMALY_TYPES)
    assert recall["missing_value"] == 0.5 and precision["missing_value"] == pytest.approx(0.5)
    assert recall["duplicate"] == 1.0 and precision["duplicate"] == pytest.approx(0.5)


def test_a_type_absent_from_the_test_rows_gives_missing_values_and_later_types_are_still_scored():
    first = inj.ANOMALY_TYPES[0]
    present = inj.ANOMALY_TYPES[1]
    types = pd.Series(["clean", "clean", present])
    flags = pd.Series([False, True, True])
    recall, precision = tb._per_type(flags, types)
    assert np.isnan(recall[first]) and np.isnan(precision[first])
    assert recall[present] == 1.0 and precision[present] == pytest.approx(0.5)
    assert isinstance(precision[present], float)


def test_a_type_that_is_never_flagged_has_zero_precision_not_an_error():
    types = pd.Series(["clean", "clean", "missing_value"])
    flags = pd.Series([False, False, False])
    recall, precision = tb._per_type(flags, types)
    assert recall["missing_value"] == 0.0 and precision["missing_value"] == 0.0


def test_unknown_names_are_listed_in_the_refusal():
    df, cols = _injected()
    with pytest.raises(ValueError, match=r"^unknown detector names: \['nope'\]$"):
        tb.evaluate(df, cols, seed=0, names=["nope"])


def test_the_evaluation_routes_the_seed_columns_and_fit_rows_to_the_right_places(monkeypatch):
    df, cols = _injected()
    calls = {"build": [], "capped": [], "split": []}
    real_split, real_capped, real_build = tb.split, tb.capped, tb._build
    monkeypatch.setattr(
        tb, "split", lambda frame, seed: calls["split"].append(seed) or real_split(frame, seed)
    )
    monkeypatch.setattr(
        tb,
        "capped",
        lambda frame, name, seed: (
            calls["capped"].append((name, seed)) or real_capped(frame, name, seed)
        ),
    )
    monkeypatch.setattr(
        tb,
        "_build",
        lambda name, contamination, columns, seed: (
            calls["build"].append((name, columns, seed))
            or real_build(name, contamination, columns, seed)
        ),
    )
    result = tb.evaluate(df, cols, seed=5, names=["zscore"])
    assert calls["split"] == [5]
    assert calls["capped"] == [("zscore", 5)]
    assert calls["build"] == [("zscore", cols, 5)]
    assert set(result) == {"recall", "precision", "fpr"}
    assert result["fpr"].name == "fpr"
    assert list(result["precision"].index) == ["zscore", "transform_dedup"]
