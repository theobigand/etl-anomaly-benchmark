"""Boundary conditions of the input and output stages, as they behave today.

Several of these characterize a limit rather than a feature: the test states
what happens so that a change in behavior is a conscious one.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import run_benchmark  # noqa: E402
import verify_real  # noqa: E402

from etl_benchmark.datasets import DatasetSpec  # noqa: E402
from etl_benchmark.load import write_csv  # noqa: E402
from etl_benchmark.metrics import compute_metrics  # noqa: E402
from etl_benchmark.pipeline import detect, transform  # noqa: E402
from etl_benchmark.quality import ZScoreDetector  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402


def _load(tmp_path, text):
    path = tmp_path / "data.csv"
    path.write_text(text)
    return DatasetSpec("toy", path, "Class", 1).load()


@pytest.mark.parametrize(
    "text",
    [
        "x,Class\n1,0\n2,1\n3,",  # export cut inside the last row
        "x,y,Class\n1,2,0\n3,4,1\n5,",  # cut before the label of a wider row
    ],
)
def test_an_export_cut_inside_a_row_is_refused_because_the_label_is_missing(tmp_path, text):
    with pytest.raises(ValueError, match="toy: label column contains missing values"):
        _load(tmp_path, text)


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("", pd.errors.EmptyDataError),
        ('x,Class\n"1,0\n2,1\n', pd.errors.ParserError),  # unterminated quote
        ("x,Class\n1,0\n2,1,9\n", pd.errors.ParserError),  # extra field
    ],
)
def test_corrupted_files_raise_the_reader_error_instead_of_returning_data(tmp_path, text, error):
    with pytest.raises(error):
        _load(tmp_path, text)


def test_a_file_truncated_at_a_row_boundary_is_not_detectable_by_reading_alone(tmp_path):
    # Dropped whole rows look like a smaller valid dataset: only the recorded
    # row count and checksum (REAL verification) can tell them apart.
    assert len(_load(tmp_path, "x,Class\n1,0\n2,1\n")) == 2


def test_a_header_only_file_loads_empty_but_cannot_enter_an_experiment(tmp_path):
    frame = _load(tmp_path, "x,Class\n")
    assert frame.empty
    with pytest.raises(ValueError):
        stratified_split(frame, "is_anomaly")
    record = verify_real.inspect_dataset(DatasetSpec("toy", tmp_path / "data.csv", "Class", 1))
    assert record["status"] == "FAIL"
    assert record["reason"] == "dataset must have rows, features and both label classes"


@pytest.mark.parametrize("label", ["inf", "2", "-1", "yes"])
def test_labels_other_than_zero_and_one_are_refused(tmp_path, label):
    with pytest.raises(ValueError, match="toy: label column must contain only 0 and 1"):
        _load(tmp_path, f"x,Class\n1,0\n2,{label}\n")


def test_a_nonfinite_feature_is_refused_by_the_detector_not_by_the_reader(tmp_path):
    frame = _load(tmp_path, "x,Class\n1,0\ninf,1\n3,0\n")
    features = frame.drop(columns=["Class", "is_anomaly"])
    with pytest.raises(ValueError):
        detect(features, ZScoreDetector())


def test_a_single_class_test_partition_is_refused_by_the_metrics():
    with pytest.raises(ValueError, match="both binary classes"):
        compute_metrics([0, 0, 0], [False] * 3, [0.1, 0.2, 0.3])


def test_tied_scores_give_chance_level_ranking_and_prevalence_average_precision():
    y = np.array([0, 0, 0, 0, 1, 1])
    metrics = compute_metrics(y, np.array([False] * 4 + [True] * 2), np.full(6, 0.5))
    assert metrics["roc_auc"] == 0.5
    assert metrics["pr_auc"] == pytest.approx(2 / 6)


def test_duplicate_removal_is_idempotent():
    frame = pd.DataFrame({"a": [1, 1, 2, 2, 3], "b": [0, 0, 1, 1, 0]})
    once = transform(frame)
    pd.testing.assert_frame_equal(transform(once), once)
    assert len(once) == 3


def test_writing_the_same_frame_twice_gives_identical_bytes(tmp_path):
    frame = pd.DataFrame({"a": [1.5, 2.5], "b": ["x", "y"]})
    first = write_csv(frame, tmp_path / "out" / "a.csv").read_bytes()
    second = write_csv(frame, tmp_path / "out" / "a.csv").read_bytes()
    assert first == second == b"a,b\n1.5,x\n2.5,y\n"


def test_detecting_twice_on_the_same_data_gives_the_same_flags_and_scores():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(rng.normal(size=(200, 3)), columns=["a", "b", "c"])
    first = detect(frame, ZScoreDetector())
    second = detect(frame, ZScoreDetector())
    pd.testing.assert_series_equal(first.flags, second.flags)
    pd.testing.assert_series_equal(first.scores, second.scores)


def test_one_evaluation_repeated_gives_the_same_table_apart_from_timing(tmp_path):
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(rng.normal(size=(300, 2)), columns=["V1", "V2"])
    frame["Class"] = [1] * 30 + [0] * 270
    frame.loc[frame.Class == 1, "V1"] += 4.0
    csv = tmp_path / "toy.csv"
    frame.to_csv(csv, index=False)
    spec = DatasetSpec("toy", csv, "Class", 1, detector_names=["zscore", "iqr"])
    data = spec.load()
    first = run_benchmark.evaluate(spec, data, 1, None).drop(columns="detect_s")
    second = run_benchmark.evaluate(spec, data, 1, None).drop(columns="detect_s")
    pd.testing.assert_frame_equal(first, second)


def test_writing_under_a_path_that_is_a_file_fails_without_creating_anything(tmp_path):
    blocker = tmp_path / "taken"
    blocker.write_text("x")
    with pytest.raises(OSError):
        write_csv(pd.DataFrame({"a": [1]}), blocker / "out.csv")
    assert blocker.read_text() == "x"


def test_an_interrupted_benchmark_run_leaves_no_provenance_record(tmp_path, monkeypatch):
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(rng.normal(size=(300, 2)), columns=["V1", "V2"])
    frame["Class"] = [1] * 30 + [0] * 270
    csv = tmp_path / "toy.csv"
    frame.to_csv(csv, index=False)
    out = tmp_path / "results"

    def interrupted(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(run_benchmark, "write_split_ids", interrupted)
    argv = ["run_benchmark", "--dataset", "cardio", "--csv", str(csv), "--detectors", "zscore"]
    monkeypatch.setattr(sys, "argv", [*argv, "--seeds", "1", "--results-dir", str(out)])
    # cardio's label column is "label"; point the spec at the toy file's own layout instead
    monkeypatch.setitem(
        run_benchmark.DATASETS, "cardio", DatasetSpec("cardio", csv, "Class", 1, ["zscore"])
    )
    with pytest.raises(OSError, match="disk full"):
        run_benchmark.main()
    names = sorted(path.name for path in out.iterdir())
    assert not any(name.startswith("run_benchmark_") for name in names)
