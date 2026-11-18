"""Exact refusals, wiring and CLI contract of the frozen-partition consumer."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from research import pool_train_only as module
from research.pool_train_only import evaluate_frozen, main

FOLDS = {"train": list(range(8)), "validation": [8, 9], "test": [10, 11]}


def _frame():
    return pd.DataFrame(
        {
            "x": np.arange(12, dtype=float),
            "kind": [f"{i:02d}" if i % 2 else "ab" for i in range(12)],
        }
    )


def _labels():
    return np.array([0, 1] * 6)


def _refusal(*args, **kwargs):
    with pytest.raises(ValueError) as caught:
        evaluate_frozen(*args, **kwargs)
    return str(caught.value)


@pytest.mark.parametrize("methods", [[], ["zscore", "zscore"], ["not_a_detector"]])
def test_detector_selection_refusals_state_the_exact_reason(methods):
    message = _refusal(_frame(), _labels(), FOLDS, seed=1, methods=methods)
    assert message == "detectors must be explicit, unique row-level registry names"


@pytest.mark.parametrize("seed", [-1, 2**32, True, 1.5, "1"])
def test_seed_refusals_state_the_exact_reason(seed):
    message = _refusal(_frame(), _labels(), FOLDS, seed=seed, methods=["zscore"])
    assert message == "seed must be a nonnegative 32-bit integer"


@pytest.mark.parametrize("seed", [0, 1, 2**32 - 1])
def test_seed_boundaries_are_accepted_and_recorded(seed):
    result = evaluate_frozen(_frame(), _labels(), FOLDS, seed=seed, methods=["zscore"])
    assert result["seed"] == seed and result["errors"] == []


@pytest.mark.parametrize(
    "labels",
    [
        np.arange(12).reshape(12, 1) % 2,
        np.array([0, 1] * 5),
        np.array([0, 1] * 5 + [0, 2]),
        np.ones((2, 12)),
    ],
)
def test_label_refusals_state_the_exact_reason(labels):
    message = _refusal(_frame(), labels, FOLDS, seed=1, methods=["zscore"])
    assert message == "labels must be an aligned binary vector"


def test_each_label_defect_alone_is_refused():
    wrong_length = np.array([0, 1] * 6 + [0])
    assert _refusal(_frame(), wrong_length, FOLDS, seed=1, methods=["zscore"]) == (
        "labels must be an aligned binary vector"
    )
    non_binary = np.array([0, 1] * 5 + [1, 2])
    assert _refusal(_frame(), non_binary, FOLDS, seed=1, methods=["zscore"]) == (
        "labels must be an aligned binary vector"
    )


@pytest.mark.parametrize("name", ["train", "validation", "test"])
def test_every_partition_must_contain_both_classes(name):
    labels = _labels().copy()
    labels[FOLDS[name]] = 0
    message = _refusal(_frame(), labels, FOLDS, seed=1, methods=["zscore"])
    assert message == "both classes are required in every frozen partition"


def test_the_result_records_seed_prevalence_partitions_and_calibration():
    result = evaluate_frozen(_frame(), _labels(), FOLDS, seed=7, methods=["zscore"])
    assert result["seed"] == 7 and result["protocol"] == "pool-train-only-v1"
    assert result["prevalence"] == {"train": 0.5, "validation": 0.5, "test": 0.5}
    assert result["partitions"] == FOLDS and result["exploratory"] is True
    assert result["calibration"] == {"policy": "train_prevalence", "value": 0.5}
    assert result["runs"]["zscore"]["fit_rows"] == 8
    assert set(result["runs"]["zscore"]) == {"metrics", "scores", "flags", "fit_rows"}


def test_calibration_and_fit_inputs_reach_the_detector_exactly(monkeypatch):
    calls = {}
    real_capped, real_build, real_detect = module.capped, module.build, module.detect

    def capped(train, method, seed):
        calls["capped"] = (len(train), method, seed)
        return real_capped(train, method, seed)

    def build(method, contamination, seed):
        calls["build"] = (method, contamination, seed)
        return real_build(method, contamination, seed)

    def detect(test, detector, fit_df=None):
        calls["detect"] = (len(test), fit_df is not None and len(fit_df))
        return real_detect(test, detector, fit_df=fit_df)

    monkeypatch.setattr(module, "capped", capped)
    monkeypatch.setattr(module, "build", build)
    monkeypatch.setattr(module, "detect", detect)
    labels = np.array([0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1])
    evaluate_frozen(_frame(), labels, FOLDS, seed=9, methods=["zscore"])
    assert calls["capped"] == (8, "zscore", 9)
    assert calls["build"] == ("zscore", 0.25, 9)
    assert calls["detect"] == (2, 8)


def test_a_skipped_detector_does_not_stop_the_remaining_ones(monkeypatch):
    monkeypatch.setattr(module, "skipped_detectors", lambda rows: {"knn"})
    result = evaluate_frozen(_frame(), _labels(), FOLDS, seed=1, methods=["knn", "zscore"])
    assert result["skipped"] == ["knn"] and list(result["runs"]) == ["zscore"]


def _inputs(tmp_path, **manifest):
    data = tmp_path / "raw.csv"
    _frame().assign(anomaly=_labels()).to_csv(data, index=False)
    content = {
        "schema_version": 1,
        "row_count": 12,
        "seed": 42,
        "input_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "partitions": FOLDS,
        **manifest,
    }
    path = tmp_path / "partitions.json"
    path.write_text(json.dumps(content))
    return data, path


def _args(data, partitions, output, *extra):
    return [
        "--csv",
        str(data),
        "--partitions",
        str(partitions),
        "--label-column",
        "anomaly",
        "--output",
        str(output),
        "--detectors",
        "zscore",
        *extra,
    ]


def test_the_cli_writes_the_result_and_a_record_beside_it_and_keeps_text_columns_as_text(tmp_path):
    data, partitions = _inputs(tmp_path)
    output = tmp_path / "run.json"
    assert main(_args(data, partitions, output)) == 0
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "partitions.json",
        "raw.csv",
        "run.json",
        "run.record.json",
    ]
    fit = json.loads(output.read_text())["preprocessing"]
    assert fit["categorical_columns"] == ["kind"] and "01" in fit["categories"][0]


@pytest.mark.parametrize(
    "missing", ["--csv", "--partitions", "--label-column", "--output", "--detectors"]
)
def test_every_cli_argument_is_required(tmp_path, missing, capsys):
    data, partitions = _inputs(tmp_path)
    arguments = _args(data, partitions, tmp_path / "run.json")
    index = arguments.index(missing)
    width = 2 if missing != "--detectors" else 2
    del arguments[index : index + width]
    with pytest.raises(SystemExit) as caught:
        main(arguments)
    assert caught.value.code == 2
    assert missing in capsys.readouterr().err


def test_the_cli_help_describes_the_consumer(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "Explicit exploratory consumer of source-bound, frozen pool partitions" in (
        capsys.readouterr().out
    )


@pytest.mark.parametrize("existing", ["run.json", "run.record.json"])
def test_either_existing_output_or_record_refuses_with_the_exact_reason(tmp_path, existing):
    data, partitions = _inputs(tmp_path)
    (tmp_path / existing).write_text("kept")
    with pytest.raises(FileExistsError) as caught:
        main(_args(data, partitions, tmp_path / "run.json"))
    assert str(caught.value) == "choose unused output and record paths"
    assert (tmp_path / existing).read_text() == "kept"


@pytest.mark.parametrize(
    "change",
    [{"schema_version": 2}, {"input_sha256": "0" * 64}],
)
def test_either_manifest_binding_failure_alone_is_refused(tmp_path, change):
    data, partitions = _inputs(tmp_path, **change)
    with pytest.raises(ValueError) as caught:
        main(_args(data, partitions, tmp_path / "run.json"))
    assert str(caught.value) == "partition manifest version or source hash differs"


def test_a_manifest_row_count_that_differs_is_refused_with_the_exact_reason(tmp_path):
    data, partitions = _inputs(tmp_path, row_count=13)
    with pytest.raises(ValueError) as caught:
        main(_args(data, partitions, tmp_path / "run.json"))
    assert str(caught.value) == "partition manifest row count differs"


def test_duplicate_csv_column_names_are_refused_with_the_exact_reason(tmp_path):
    data, partitions = _inputs(tmp_path)
    data.write_text("x,x,anomaly\n" + "\n".join(f"{i},{i},{i % 2}" for i in range(12)) + "\n")
    partitions.write_text(
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
    with pytest.raises(ValueError) as caught:
        main(_args(data, partitions, tmp_path / "run.json"))
    assert str(caught.value) == "duplicate CSV column names are not accepted"


def test_the_output_is_canonical_json_in_a_created_directory_and_the_record_is_bound(tmp_path):
    data, partitions = _inputs(tmp_path)
    output = tmp_path / "nested" / "deeper" / "run.json"
    assert main(_args(data, partitions, output)) == 0
    text = output.read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    record = json.loads(output.with_suffix(".record.json").read_text())
    assert record["experiment"] == "pool-train-only-v1"
    assert record["seeds"] == [42] and record["outputs"] == ["run.json"]
    assert record["dataset"]["sha256"] == hashlib.sha256(data.read_bytes()).hexdigest()
    assert "raw.csv" in json.dumps(record["dataset"])
    settings = record["settings"]
    assert settings["protocol"] == "pool-train-only-v1" and settings["exploratory"] is True
    assert settings["label_column"] == "anomaly" and settings["detectors"] == ["zscore"]
    assert settings["partition_sha256"] == hashlib.sha256(partitions.read_bytes()).hexdigest()
    assert sorted(settings["research_sha256"]) == sorted(module.RESEARCH_SOURCES)
    from importlib.metadata import version

    assert settings["torch"] == version("torch")


def test_a_non_finite_result_is_never_written(tmp_path, monkeypatch):
    data, partitions = _inputs(tmp_path)
    monkeypatch.setattr(
        module,
        "evaluate_frozen",
        lambda *a, **k: {"runs": {"z": 1}, "errors": [], "x": float("nan")},
    )
    output = tmp_path / "run.json"
    with pytest.raises(ValueError):
        main(_args(data, partitions, output))
    assert not output.exists()


def test_a_run_without_results_or_with_errors_returns_failure(tmp_path, monkeypatch):
    data, partitions = _inputs(tmp_path)
    monkeypatch.setattr(module, "evaluate_frozen", lambda *a, **k: {"runs": {}, "errors": []})
    assert main(_args(data, partitions, tmp_path / "a.json")) == 1
    monkeypatch.setattr(
        module, "evaluate_frozen", lambda *a, **k: {"runs": {"z": 1}, "errors": ["e"]}
    )
    assert main(_args(data, partitions, tmp_path / "b.json")) == 1
    monkeypatch.setattr(module, "evaluate_frozen", lambda *a, **k: {"runs": {"z": 1}, "errors": []})
    assert main(_args(data, partitions, tmp_path / "c.json")) == 0


def test_every_feature_is_read_as_text_the_label_as_a_number_and_the_record_names_the_file(
    tmp_path, monkeypatch
):
    data, partitions = _inputs(tmp_path)
    frame = pd.read_csv(data)
    frame["code"] = [f"{i:02d}" for i in range(len(frame))]
    frame.to_csv(data, index=False)
    manifest = json.loads(partitions.read_text())
    manifest["input_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    partitions.write_text(json.dumps(manifest))
    seen = {}

    def spy(features, labels, folds, seed, methods):
        seen.update(features=features.copy(), labels=labels, seed=seed)
        return {"errors": [], "runs": {"zscore": {}}}

    monkeypatch.setattr(module, "evaluate_frozen", spy)
    assert main(_args(data, partitions, tmp_path / "run.json")) == 0
    assert all(not pd.api.types.is_numeric_dtype(dtype) for dtype in seen["features"].dtypes)
    assert seen["features"]["code"].tolist()[:3] == ["00", "01", "02"]
    assert seen["labels"].dtype.kind in "iu" and "anomaly" not in seen["features"]
    record = json.loads((tmp_path / "run.record.json").read_text())
    assert record["dataset"]["identity"] == "raw.csv"
