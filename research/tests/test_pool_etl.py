"""The pipeline on a pool dataset: stages, files and memory are recorded (pool_extension.md)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_etl as pe  # noqa: E402


def _adbench(tmp_path, rows=300):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(rows, 4))
    y = np.zeros(rows, dtype=int)
    y[:20] = 1
    x[:20] += 6
    path = tmp_path / "toy.npz"
    np.savez(path, X=x, y=y)
    return {"id": "adbench:toy", "name": "toy", "source": "adbench", "path": str(path)}


def test_an_adbench_array_becomes_a_csv_with_its_label_kept_out_of_the_features(tmp_path):
    csv, label, skip = pe.prepare_csv(_adbench(tmp_path), tmp_path)
    frame = pd.read_csv(csv)
    assert list(frame.columns) == ["f0", "f1", "f2", "f3", "label"]
    assert label == "label" and skip == []


def test_a_uci_table_keeps_its_file_and_names_its_target_and_id_columns(tmp_path):
    frame = pd.DataFrame({"id": range(50), "v": np.arange(50.0), "w": np.arange(50.0) ** 2, "y": 0})
    path = tmp_path / "1.csv"
    frame.to_csv(path, index=False)
    meta = {
        "target_col": ["y"],
        "variables": [{"name": "id", "role": "ID"}, {"name": "y", "role": "Target"}],
    }
    job = {"id": "uci:1", "source": "uci", "meta": meta, "path": str(path), "name": "t"}
    csv, label, skip = pe.prepare_csv(job, tmp_path)
    assert csv == path and label == "y" and skip == ["id", "y"]


def test_the_four_stages_are_timed_and_the_run_reports_rows_memory_and_the_flagged_share(tmp_path):
    out = pe.run_etl(_adbench(tmp_path), "isolation_forest")
    assert out["status"] == "OK" and out["method"] == "isolation_forest"
    assert set(out["stages_s"]) == {"extract", "transform", "detect", "load"}
    assert all(v > 0 for v in out["stages_s"].values())
    assert 0 < out["detect_stage_share"] < 1
    assert out["rows_in"] == 300 and out["rows_after_transform"] <= 300
    assert out["rss_peak_bytes"] >= out["rss_delta_bytes"] >= 0
    assert 0 < out["flagged_share"] < 0.5


def test_a_failing_dataset_is_recorded_with_its_reason(tmp_path):
    job = _adbench(tmp_path)
    Path(job["path"]).unlink()
    out = pe.run_etl(job, "zscore")
    assert out["status"] == "FAIL" and "FileNotFoundError" in out["reason"]


def test_an_adbench_carrier_has_string_column_names_so_the_rule_detectors_can_read_it(tmp_path):
    import pool_typed as pt

    rng = np.random.default_rng(0)
    x = rng.normal(size=(3200, 5))
    y = np.zeros(3200, dtype=int)
    y[:40] = 1
    path = tmp_path / "toy.npz"
    np.savez(path, X=x, y=y)
    job = {"id": "adbench:toy", "name": "toy", "source": "adbench", "path": str(path)}
    carrier, report = pt.load_carrier(job)
    assert all(isinstance(c, str) for c in carrier.columns) and report["normal_class_only"]
    assert len(carrier) == 3160 and len(report["columns"]) == 5
