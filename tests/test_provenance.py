import hashlib
import json
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pandas as pd
import pytest

from etl_benchmark.split import stratified_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import provenance  # noqa: E402


def test_record_binds_data_seed_protocol_and_outputs(tmp_path):
    dataset = tmp_path / "data.csv"
    dataset.write_text("x,label\n1,0\n2,1\n")
    output = tmp_path / "run.json"
    provenance.write_record(
        output,
        experiment="benchmark",
        seeds=[4, 5],
        dataset="toy",
        data_path=dataset,
        settings={"split": [0.7, 0.15, 0.15]},
        outputs=["metrics.csv"],
    )
    record = json.loads(output.read_text())
    assert record["seeds"] == [4, 5]
    assert record["dataset"]["sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert record["settings"]["split"] == [0.7, 0.15, 0.15]
    assert record["outputs"] == ["metrics.csv"]
    assert record["source_revision"]
    assert record["python"]


def test_split_archive_reconstructs_disjoint_exact_membership(tmp_path):
    frame = pd.DataFrame(
        {"row": range(100), "is_anomaly": [0] * 80 + [1] * 20}, index=range(1000, 1100)
    )
    path = tmp_path / "splits.json.gz"
    provenance.write_split_ids(path, frame, "is_anomaly", [3, 4], (0.7, 0.15, 0.15))
    archived = provenance.read_split_ids(path)
    assert archived["row_count"] == 100
    assert set(archived["seeds"]) == {"3", "4"}
    for seed in (3, 4):
        parts = archived["seeds"][str(seed)]
        assert sorted(parts["train"] + parts["validation"] + parts["test"]) == list(range(100))
        assert all(
            not set(parts[a]) & set(parts[b])
            for a, b in (("train", "test"), ("train", "validation"), ("validation", "test"))
        )
        expected = stratified_split(frame.assign(_split_row_id=range(100)), "is_anomaly", seed=seed)
        assert [parts[key] for key in ("train", "validation", "test")] == [
            p._split_row_id.tolist() for p in expected
        ]


def test_split_archive_records_fit_sample_inside_train(tmp_path):
    frame = pd.DataFrame({"is_anomaly": [0] * 80 + [1] * 20})
    path = tmp_path / "splits.json.gz"
    provenance.write_split_ids(path, frame, "is_anomaly", [3], (0.7, 0.15, 0.15), fit_sample=10)
    parts = provenance.read_split_ids(path)["seeds"]["3"]
    assert len(parts["fit"]) == 10
    assert set(parts["fit"]) <= set(parts["train"])


def test_split_archive_rejects_invalid_sample_and_reserved_marker(tmp_path):
    frame = pd.DataFrame({"is_anomaly": [0] * 80 + [1] * 20})
    path = tmp_path / "splits.json.gz"
    with pytest.raises(ValueError, match="fit_sample"):
        provenance.write_split_ids(path, frame, "is_anomaly", [3], (0.7, 0.15, 0.15), 0)
    with pytest.raises(ValueError, match="reserved split marker"):
        provenance.write_split_ids(
            path,
            frame.assign(_split_row_id=range(100)),
            "is_anomaly",
            [3],
            (0.7, 0.15, 0.15),
        )
    assert not path.exists()


def test_record_marks_unavailable_package_version_explicitly(tmp_path, monkeypatch):
    original = provenance.version

    def version_or_missing(name):
        if name == "pyod":
            raise PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(provenance, "version", version_or_missing)
    output = tmp_path / "run.json"
    provenance.write_record(
        output,
        experiment="toy",
        seeds=[1],
        dataset="toy",
        data_path=None,
        settings={},
        outputs=[],
    )
    record = json.loads(output.read_text())
    assert record["packages"]["pyod"] is None
    assert record["dataset"] == {"identity": "toy"}
