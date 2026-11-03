"""Frozen-fold preparation must never fit on evaluation values or labels."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import normalise

ROOT = Path(__file__).resolve().parents[1]
FOLDS = {"train": list(range(8)), "validation": [8, 9], "test": [10, 11]}


def _frame():
    return pd.DataFrame(
        {
            "x": np.arange(12, dtype=float),
            "category": ["a", "b"] * 4 + ["a", "b", "c", "d"],
            "holes": [0.0, np.nan, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
            "constant": [1.0] * 8 + [2.0, 3.0, 4.0, 5.0],
            "missing": [np.nan] * 5 + [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
        }
    )


def _prepare(frame, folds=FOLDS):
    from research.pool_preprocessing import prepare_frozen

    return prepare_frozen(frame, folds)


def test_legacy_schema_counterexample_is_retained_as_a_negative_control():
    frame = pd.DataFrame({"x": range(6), "category": ["a", "b", "a", "b", "c", "d"]})
    changed = frame.copy()
    changed.loc[[4, 5], "category"] = ["a", "b"]
    first, _, _ = normalise.clean(frame, [0, 1, 0, 1, 0, 1])
    again, _, _ = normalise.clean(changed, [0, 1, 0, 1, 0, 1])
    assert first.shape == (6, 5) and again.shape == (6, 3)


def test_evaluation_values_cannot_change_fitted_schema_or_training_matrix():
    frame = _frame()
    changed = frame.copy()
    changed.loc[8:, "category"] = ["new1", "new2", "new3", "new4"]
    changed.loc[8:, "x"] = [1e6, -1e6, 2e6, -2e6]
    changed.loc[8:, "holes"] = np.nan
    changed.loc[8:, "constant"] = 1.0
    changed.loc[8:, "missing"] = np.nan
    first, again = _prepare(frame), _prepare(changed)
    assert first["fit"] == again["fit"]
    pd.testing.assert_frame_equal(first["train"], again["train"])
    assert first["fit"]["numeric_columns"] == ["x", "holes"]
    assert first["fit"]["categorical_columns"] == ["category"]
    assert first["fit"]["dropped"] == {
        "missing": ["missing"],
        "constant": ["constant"],
        "cardinality": [],
    }
    assert first["fit"]["medians"] == [3.5, 4.5]
    assert first["fit"]["categories"] == [["a", "b"]]


def test_transformation_uses_training_statistics_and_supplied_order():
    folds = {**FOLDS, "train": list(reversed(FOLDS["train"])), "test": [11, 10]}
    got = _prepare(_frame(), folds)
    assert got["train"].index.tolist() == folds["train"]
    assert got["test"].index.tolist() == [11, 10]
    assert got["train"].shape == (8, 4)
    np.testing.assert_allclose(got["train"].mean(), 0.0, atol=1e-15)
    np.testing.assert_allclose(got["train"].std(ddof=0), 1.0)
    assert got["test"].iloc[0, 0] == pytest.approx((11 - 3.5) / np.std(np.arange(8)))
    np.testing.assert_allclose(got["test"].iloc[:, 2:], -1.0)
    assert got["fit"]["output_columns"] == ["f0", "f1", "f2", "f3"]


def test_category_missingness_is_distinct_and_future_cardinality_is_not_used():
    frame = _frame()
    frame.loc[0, "category"] = np.nan
    got = _prepare(frame)
    assert got["fit"]["categories"] == [["a", "b", None]]
    assert np.isfinite(got["test"]).all().all()
    frame["category"] = [f"c{i}" for i in range(len(frame))]
    assert _prepare(frame)["fit"]["categorical_columns"] == ["category"]


def test_high_cardinality_uses_training_values_and_retains_numeric_columns():
    frame = pd.DataFrame({"x": range(26), "category": [f"c{i}" for i in range(26)]})
    folds = {"train": list(range(22)), "validation": [22, 23], "test": [24, 25]}
    got = _prepare(frame, folds)
    assert got["fit"]["dropped"]["cardinality"] == ["category"]
    assert got["train"].shape == (22, 1)


def test_string_numeric_inference_uses_only_training_rows_and_bool_is_categorical():
    frame = _frame().astype({"x": str})
    frame["flag"] = [True, False] * 6
    got = _prepare(frame)
    assert "x" in got["fit"]["numeric_columns"]
    assert "flag" in got["fit"]["categorical_columns"]
    frame.loc[11, "x"] = "not numeric"
    with pytest.raises(ValueError):
        _prepare(frame)


@pytest.mark.parametrize("column", ["x", "category"])
def test_one_kind_of_feature_can_be_used_on_its_own(column):
    frame = _frame()[[column]]
    if column == "category":
        frame.loc[8:, column] = ["v", "w", "u", "z"]
    got = _prepare(frame)
    assert np.isfinite(got["train"]).all().all()
    assert got["test"].shape[0] == 2


@pytest.mark.parametrize(
    "folds",
    [
        {"train": [0], "test": [1]},
        {**FOLDS, "other": []},
        {**FOLDS, "train": []},
        {**FOLDS, "train": tuple(range(8))},
        {**FOLDS, "train": [0, 0, 1, 2, 3, 4, 5, 6, 7]},
        {**FOLDS, "test": [9, 10, 11]},
        {**FOLDS, "test": [10]},
        {**FOLDS, "test": [10, 12]},
        {**FOLDS, "test": [-1, 10, 11]},
        {**FOLDS, "test": [10.0, 11.0]},
        {**FOLDS, "test": [True, 11]},
    ],
)
def test_invalid_assignments_are_rejected_without_making_new_partitions(folds):
    with pytest.raises(ValueError, match="partition"):
        _prepare(_frame(), folds)


def test_cross_partition_duplicate_features_are_rejected_without_reading_labels():
    frame = _frame()
    frame.loc[11] = frame.loc[0]
    with pytest.raises(ValueError, match="duplicate"):
        _prepare(frame)


def test_duplicate_features_within_a_partition_keep_the_original_row_population():
    frame = _frame()
    frame.loc[1] = frame.loc[0]
    got = _prepare(frame)
    assert got["train"].shape[0] == 8
    np.testing.assert_allclose(got["train"].iloc[0], got["train"].iloc[1])


@pytest.mark.parametrize("kind", ["empty", "duplicate", "nonstring", "constant", "infinite"])
def test_unusable_feature_schemas_are_rejected(kind):
    frame = _frame()
    if kind == "empty":
        frame = frame.iloc[:, :0]
    elif kind == "duplicate":
        frame.columns = ["x"] * len(frame.columns)
    elif kind == "nonstring":
        frame.columns = range(len(frame.columns))
    elif kind == "constant":
        frame = pd.DataFrame({"only": [1.0] * 8 + [2.0, 3.0, 4.0, 5.0]})
    else:
        frame.loc[0, "x"] = np.inf
    with pytest.raises(ValueError):
        _prepare(frame)


def test_evaluation_labels_change_only_metrics_not_fitting_scores_or_decisions():
    from research.pool_train_only import evaluate_frozen

    frame = pd.concat(
        [_frame(), _frame().iloc[-4:].assign(x=range(12, 16), holes=range(12, 16))],
        ignore_index=True,
    )
    folds = {"train": list(range(8)), "validation": list(range(8, 12)), "test": list(range(12, 16))}
    y = np.array([0, 1] * 4 + [0, 0, 0, 1] * 2)
    changed = y.copy()
    changed[8:] = 1 - changed[8:]
    a = evaluate_frozen(frame, y, folds, seed=42, methods=["zscore", "isolation_forest"])
    b = evaluate_frozen(frame, changed, folds, seed=42, methods=["zscore", "isolation_forest"])
    assert a["protocol"] == "pool-train-only-v1" and a["exploratory"] is True
    assert a["preprocessing"] == b["preprocessing"]
    assert a["partitions"] == b["partitions"] == folds
    assert a["calibration"] == b["calibration"] == {"policy": "train_prevalence", "value": 0.5}
    for name in a["runs"]:
        assert a["runs"][name]["scores"] == b["runs"][name]["scores"]
        assert a["runs"][name]["flags"] == b["runs"][name]["flags"]
    assert a["runs"]["zscore"]["metrics"] != b["runs"]["zscore"]["metrics"]
    assert a["errors"] == a["skipped"] == []


@pytest.mark.parametrize("labels", [[0] * 12, [0] * 11, [[0, 1]] * 6, [0, 0.5] * 6])
def test_malformed_or_undefined_labels_do_not_produce_an_ap_result(labels):
    from research.pool_train_only import evaluate_frozen

    with pytest.raises(ValueError):
        evaluate_frozen(_frame(), labels, FOLDS, seed=42, methods=["zscore"])


@pytest.mark.parametrize("methods", [[], ["nope"], ["drift"], ["zscore", "zscore"]])
def test_only_explicit_unique_row_level_detectors_are_accepted(methods):
    from research.pool_train_only import evaluate_frozen

    with pytest.raises(ValueError, match="detector"):
        evaluate_frozen(_frame(), np.arange(12) % 2, FOLDS, seed=42, methods=methods)


def _inputs(tmp_path):
    data = tmp_path / "raw.csv"
    _frame().assign(anomaly=np.arange(12) % 2).to_csv(data, index=False)
    manifest = tmp_path / "partitions.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "row_count": 12,
                "seed": 42,
                "input_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
                "partitions": FOLDS,
            }
        )
    )
    return data, manifest


def _cli(data, manifest, output, *extra):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "research.pool_train_only",
            "--csv",
            str(data),
            "--partitions",
            str(manifest),
            "--label-column",
            "anomaly",
            "--output",
            str(output),
            "--detectors",
            "zscore",
            *extra,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_binds_raw_scores_partitions_sources_and_versions_without_overwriting(tmp_path):
    data, manifest = _inputs(tmp_path)
    output = tmp_path / "run.json"
    done = _cli(data, manifest, output)
    assert done.returncode == 0, done.stderr
    result = json.loads(output.read_text())
    record = json.loads(output.with_suffix(".record.json").read_text())
    assert result["partitions"] == FOLDS
    assert len(result["runs"]["zscore"]["scores"]) == 2
    assert "anomaly" not in result["preprocessing"]["input_columns"]
    assert record["dataset"]["sha256"] == hashlib.sha256(data.read_bytes()).hexdigest()
    assert record["output_sha256"][output.name] == hashlib.sha256(output.read_bytes()).hexdigest()
    settings = record["settings"]
    assert settings["protocol"] == "pool-train-only-v1"
    assert settings["label_column"] == "anomaly"
    assert settings["partition_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert (
        settings["research_sha256"]["research/pool_preprocessing.py"]
        == hashlib.sha256((ROOT / "research/pool_preprocessing.py").read_bytes()).hexdigest()
    )
    assert record["packages"]["scikit-learn"]
    old = output.read_bytes()
    assert _cli(data, manifest, output).returncode != 0
    assert output.read_bytes() == old


@pytest.mark.parametrize("failure", ["hash", "row_count", "version", "seed", "label", "record"])
def test_cli_refuses_unbound_or_unusable_input_and_existing_records(tmp_path, failure):
    data, manifest = _inputs(tmp_path)
    output = tmp_path / "run.json"
    content = json.loads(manifest.read_text())
    if failure == "hash":
        content["input_sha256"] = "0" * 64
    elif failure == "row_count":
        content["row_count"] = 13
    elif failure == "version":
        content["schema_version"] = 2
    elif failure == "seed":
        content["seed"] = -1
    elif failure == "label":
        pd.read_csv(data).drop(columns="anomaly").to_csv(data, index=False)
        content["input_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    else:
        output.with_suffix(".record.json").write_text("existing record")
    manifest.write_text(json.dumps(content))
    assert _cli(data, manifest, output).returncode != 0
    assert not output.exists()


@pytest.mark.parametrize("seed", [-1, 2**32, True, 1.0])
def test_invalid_seeds_are_rejected(seed):
    from research.pool_train_only import evaluate_frozen

    with pytest.raises(ValueError, match="seed"):
        evaluate_frozen(_frame(), np.arange(12) % 2, FOLDS, seed=seed, methods=["zscore"])


def test_numeric_overflow_in_evaluation_is_refused_instead_of_persisted():
    frame = _frame()
    frame["x"] *= 1e-100
    frame.loc[10, "x"] = 1e308
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError, match="transformed"):
        _prepare(frame)


def test_real_detector_failure_is_recorded_and_other_detectors_still_run():
    from research.pool_train_only import evaluate_frozen

    folds = {"train": [0, 1, 2, 3], "validation": [4, 5, 6, 7], "test": [8, 9, 10, 11]}
    got = evaluate_frozen(_frame(), np.arange(12) % 2, folds, seed=42, methods=["zscore", "knn"])
    assert list(got["runs"]) == ["zscore"]
    assert len(got["errors"]) == 1 and got["errors"][0]["detector"] == "knn"
    assert "ValueError" in got["errors"][0]["error"]


def test_declared_size_skip_is_recorded_without_fitting_the_skipped_detector(monkeypatch):
    from research.pool_train_only import evaluate_frozen

    monkeypatch.setattr(normalise, "KNN_MAX_TRAIN", 4)
    got = evaluate_frozen(_frame(), np.arange(12) % 2, FOLDS, seed=42, methods=["knn"])
    assert got["skipped"] == ["knn"] and got["runs"] == {} and got["errors"] == []


def test_failed_cli_run_keeps_failure_evidence_but_returns_failure(tmp_path):
    data, manifest = _inputs(tmp_path)
    content = json.loads(manifest.read_text())
    content["partitions"] = {
        "train": [0, 1, 2, 3],
        "validation": [4, 5, 6, 7],
        "test": [8, 9, 10, 11],
    }
    manifest.write_text(json.dumps(content))
    output = tmp_path / "failed.json"
    done = _cli(data, manifest, output, "--detectors", "zscore", "knn")
    assert done.returncode == 1, done.stderr
    assert json.loads(output.read_text())["errors"][0]["detector"] == "knn"
    assert output.with_suffix(".record.json").exists()


def test_missing_optional_package_is_recorded_explicitly():
    from research.pool_train_only import _optional_version

    assert _optional_version("etl-benchmark-package-that-does-not-exist") is None


def test_legacy_conflicting_label_filter_changes_reference_rows_before_splitting():
    frame = pd.DataFrame({"x": [0, 1, 2, 3, 0, 4], "category": ["a", "b"] * 3})
    first_labels = np.array([0, 1, 0, 1, 0, 1])
    changed = first_labels.copy()
    changed[4] = 1
    before, _, report = normalise.clean(frame, first_labels)
    after, _, changed_report = normalise.clean(frame, changed)
    assert len(before) == 5 and len(after) == 4
    assert report["conflicting_rows_removed"] == 0
    assert changed_report["conflicting_rows_removed"] == 2
    assert 0 in before[:, 0] and 0 not in after[:, 0]


def test_cli_with_every_detector_skipped_returns_failure_and_preserves_the_skip(
    tmp_path, monkeypatch
):
    from research.pool_train_only import main

    data, manifest = _inputs(tmp_path)
    output = tmp_path / "skipped.json"
    monkeypatch.setattr(normalise, "KNN_MAX_TRAIN", 4)
    status = main(
        [
            "--csv",
            str(data),
            "--partitions",
            str(manifest),
            "--label-column",
            "anomaly",
            "--output",
            str(output),
            "--detectors",
            "knn",
        ]
    )
    assert status == 1
    result = json.loads(output.read_text())
    assert result["runs"] == {} and result["skipped"] == ["knn"]
    assert output.with_suffix(".record.json").exists()


def test_duplicate_csv_target_headers_are_refused_before_parser_renaming(tmp_path):
    data, manifest = _inputs(tmp_path)
    table = pd.read_csv(data)
    table["x"] = np.arange(len(table)) % 2
    table.to_csv(data, index=False)
    text = data.read_text()
    data.write_text(text.replace("x,category", "anomaly,category", 1))
    content = json.loads(manifest.read_text())
    content["input_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(content))
    output = tmp_path / "duplicate.json"
    result = _cli(data, manifest, output)
    assert result.returncode != 0
    assert "duplicate" in result.stderr.lower()
    assert not output.exists()
