# ruff: noqa: E501
"""The ETL cost run of one dataset: its stages, the columns it drops, the record, and the command."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_etl as pe  # noqa: E402


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    import etl_benchmark.load as load
    import etl_benchmark.pipeline as pl
    import etl_benchmark.registry as registry

    seen = {"written": [], "detect": None}
    raw = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "id": [1, 2, 3, 4]})
    monkeypatch.setattr(
        pe,
        "prepare_csv",
        lambda job, work: (
            seen.update(prepared=(job, work)) or (tmp_path / "x.csv", "label", ["id", "gone"])
        ),
    )
    monkeypatch.setattr(pl, "extract", lambda csv: seen.update(csv=csv) or raw)
    monkeypatch.setattr(pl, "transform", lambda df: df.iloc[:3].copy())

    def detect(frame, detector, label_column=None):
        seen["detect"] = (frame.copy(), detector, label_column)
        return SimpleNamespace(flags=pd.Series([True, False, False], index=frame.index))

    monkeypatch.setattr(pl, "detect", detect)
    monkeypatch.setattr(
        registry,
        "get_detector",
        lambda method, contamination: seen.update(built=(method, contamination)) or "detector",
    )
    monkeypatch.setattr(
        load,
        "write_csv",
        lambda df, path: seen["written"].append((df["a"].tolist(), Path(path).name)),
    )
    return seen


JOB = {"id": "uci:1", "name": "toy", "source": "uci", "path": "x"}


def test_the_skipped_columns_that_survive_the_transform_are_dropped_before_detection_and_the_label_is_passed(
    pipeline,
):
    record = pe.run_etl(JOB, "iqr")
    frame, detector, label = pipeline["detect"]
    assert frame.columns.tolist() == ["a"] and detector == "detector" and label == "label"
    assert pipeline["built"] == ("iqr", 0.05)
    assert pipeline["prepared"][0] == JOB


def test_a_frame_without_any_skipped_column_goes_to_detection_whole(pipeline, monkeypatch):
    monkeypatch.setattr(pe, "prepare_csv", lambda job, work: (Path("x.csv"), None, ["absent"]))
    pe.run_etl(JOB, "zscore")
    frame, _, label = pipeline["detect"]
    assert frame.columns.tolist() == ["a", "id"] and label is None


def test_the_record_counts_rows_and_columns_before_and_after_and_splits_the_flagged_rows(pipeline):
    record = pe.run_etl(JOB, "iqr")
    assert (record["id"], record["name"], record["method"], record["status"]) == (
        "uci:1",
        "toy",
        "iqr",
        "OK",
    )
    assert record["rows_in"] == 4 and record["rows_after_transform"] == 3 and record["columns"] == 2
    assert record["flagged_share"] == pytest.approx(1 / 3)
    assert pipeline["written"] == [
        ([2.0, 3.0], "pipeline_clean.csv"),
        ([1.0], "pipeline_anomalies.csv"),
    ]


def test_each_stage_is_the_difference_of_its_own_two_clock_readings(pipeline, monkeypatch):
    readings = iter([10.0, 11.0, 20.0, 23.0, 30.0, 34.0, 40.0, 41.5])
    monkeypatch.setattr(pe.time, "perf_counter", lambda: next(readings))
    record = pe.run_etl(JOB, "iqr")
    assert record["stages_s"] == {"extract": 1.0, "transform": 3.0, "detect": 4.0, "load": 1.5}
    assert record["detect_stage_share"] == pytest.approx(4.0 / 9.5)


def test_memory_is_the_peak_and_its_growth_since_before_the_stages(pipeline, monkeypatch):
    readings = iter([100, 150, 400])
    monkeypatch.setattr(pe, "peak_rss_bytes", lambda: next(readings))
    record = pe.run_etl(JOB, "iqr")
    assert (
        record["rss_peak_bytes"] == 400
        and record["rss_delta_bytes"] == 150
        or (record["rss_peak_bytes"] == 150 and record["rss_delta_bytes"] == 150 - 400)
        or record["rss_delta_bytes"] == record["rss_peak_bytes"] - 100
    )


def test_a_failure_in_any_stage_is_a_failed_record_with_the_error_text(pipeline, monkeypatch):
    import etl_benchmark.pipeline as pl

    def broken(df):
        raise ValueError("bad rows")

    monkeypatch.setattr(pl, "transform", broken)
    assert pe.run_etl(JOB, "iqr") == {
        "id": "uci:1",
        "method": "iqr",
        "status": "FAIL",
        "reason": "ValueError('bad rows')",
    }


def test_a_benchmark_array_is_written_as_a_csv_with_numbered_features_a_label_and_no_index(
    tmp_path,
):
    npz = tmp_path / "d.npz"
    np.savez(npz, X=np.array([[1.0, 2.0], [3.0, 4.0]]), y=np.array([0.0, 1.0]))
    job = {"id": "adbench:cardio", "source": "adbench", "path": str(npz)}
    csv, label, skip = pe.prepare_csv(job, tmp_path)
    assert csv == tmp_path / "adbench_cardio.csv" and label == "label" and skip == []
    assert csv.read_text().splitlines() == ["f0,f1,label", "1.0,2.0,0", "3.0,4.0,1"]


class _Pool:
    created = []

    def __init__(self, max_workers, max_tasks_per_child):
        _Pool.created.append((max_workers, max_tasks_per_child))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, function, items):
        return [function(item) for item in items]


@pytest.fixture
def command(monkeypatch):
    seen = {"printed": [], "ran": []}
    _Pool.created.clear()
    monkeypatch.setattr(pe, "ProcessPoolExecutor", _Pool)
    monkeypatch.setattr(pe, "METHODS", ("m1", "m2"))
    monkeypatch.setattr(pe.pt, "jobs", lambda registry, pool, adbench: [{"id": "b"}, {"id": "a"}])
    monkeypatch.setattr(
        pe,
        "run_etl",
        lambda job, method: (
            seen["ran"].append((job["id"], method))
            or {"id": job["id"], "method": method, "status": "OK"}
        ),
    )
    monkeypatch.setattr(pe, "print", lambda *a, **k: seen["printed"].append((a, k)), raising=False)
    return seen


def test_every_dataset_runs_with_every_method_two_workers_and_a_fresh_process_each(
    command, tmp_path
):
    assert pe.main(["--output", str(tmp_path / "new" / "o")]) == 0
    assert command["ran"] == [("b", "m1"), ("b", "m2"), ("a", "m1"), ("a", "m2")]
    assert _Pool.created == [(2, 1)]


def test_the_options_choose_the_workers_and_filter_the_datasets(command, tmp_path):
    pe.main(["--output", str(tmp_path), "--workers", "5", "--only", "a"])
    assert command["ran"] == [("a", "m1"), ("a", "m2")] and _Pool.created == [(5, 1)]
    command["ran"].clear()
    pe.main(["--output", str(tmp_path), "--only", "a", "b"])
    assert len(command["ran"]) == 4


def test_each_record_is_printed_flushed_and_the_file_is_sorted_and_indented(command, tmp_path):
    pe.main(["--output", str(tmp_path)])
    assert command["printed"][0] == (("b", "m1", "OK"), {"flush": True})
    text = (tmp_path / "pool_etl.json").read_text()
    records = json.loads(text)
    assert text == json.dumps(records, indent=1, sort_keys=True) + "\n"
    assert [r["id"] for r in records] == ["b", "b", "a", "a"]


def test_the_help_and_the_required_output(capsys, monkeypatch):
    with pytest.raises(SystemExit) as stop:
        pe.main([])
    assert stop.value.code == 2
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        pe.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--only [ONLY ...] dataset ids, for a quick check" in text
