"""Exact fields, call arguments and memory units of the pool ETL measurements."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from test_pool_etl import _adbench

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_etl as pe  # noqa: E402


def test_peak_memory_is_in_bytes_on_every_platform(monkeypatch):
    class Usage:
        ru_maxrss = 2048

    monkeypatch.setattr(pe.resource, "getrusage", lambda who: Usage)
    monkeypatch.setattr(pe.sys, "platform", "darwin")
    assert pe.peak_rss_bytes() == 2048
    monkeypatch.setattr(pe.sys, "platform", "linux")
    assert pe.peak_rss_bytes() == 2048 * 1024
    assert isinstance(pe.peak_rss_bytes(), int)


def test_an_adbench_csv_is_named_after_the_dataset_id_and_holds_integer_labels(tmp_path):
    job = _adbench(tmp_path)
    csv, label, _ = pe.prepare_csv(job, tmp_path)
    assert csv == tmp_path / "adbench_toy.csv"
    frame = pd.read_csv(csv)
    assert frame["label"].dtype.kind == "i" and frame.columns[0] == "f0"
    assert len(frame) == 300


def test_a_uci_target_missing_from_the_table_is_not_reported_as_a_label(tmp_path):
    frame = pd.DataFrame({"v": range(10), "w": range(10)})
    path = tmp_path / "2.csv"
    frame.to_csv(path, index=False)
    meta = {"target_col": ["absent"], "variables": []}
    job = {"id": "uci:2", "source": "uci", "meta": meta, "path": str(path), "name": "t"}
    assert pe.prepare_csv(job, tmp_path) == (path, None, [])
    no_target = {**job, "meta": {"target_col": [], "variables": []}}
    assert pe.prepare_csv(no_target, tmp_path) == (path, None, [])


def test_the_pipeline_is_called_with_a_five_percent_detector_and_the_label_column(
    tmp_path, monkeypatch
):
    import etl_benchmark.pipeline as pipeline
    import etl_benchmark.registry as registry

    seen = {}
    real_detect, real_get = pipeline.detect, registry.get_detector

    def get(method, contamination):
        seen["detector"] = (method, contamination)
        return real_get(method, contamination)

    def detect(features, detector, label_column=None):
        seen["label"] = label_column
        seen["columns"] = list(features.columns)
        return real_detect(features, detector, label_column=label_column)

    monkeypatch.setattr(registry, "get_detector", get)
    monkeypatch.setattr(pipeline, "detect", detect)
    out = pe.run_etl(_adbench(tmp_path), "zscore")
    assert out["status"] == "OK"
    assert seen["detector"] == ("zscore", 0.05)
    assert seen["label"] == "label"
    assert out["name"] == "toy" and out["id"] == "adbench:toy"
    assert out["columns"] == 5
    total = sum(out["stages_s"].values())
    assert out["detect_stage_share"] == pytest.approx(out["stages_s"]["detect"] / total)


def test_a_failure_record_names_the_dataset_the_method_and_the_exception(tmp_path):
    job = _adbench(tmp_path)
    Path(job["path"]).unlink()
    out = pe.run_etl(job, "zscore")
    assert set(out) == {"id", "method", "status", "reason"}
    assert out["id"] == "adbench:toy" and out["method"] == "zscore"


def test_the_flagged_rows_and_clean_rows_are_written_and_the_split_covers_the_table(
    tmp_path, monkeypatch
):
    written = []
    import etl_benchmark.load as load

    monkeypatch.setattr(
        load, "write_csv", lambda frame, path: written.append((path.name, len(frame)))
    )
    out = pe.run_etl(_adbench(tmp_path), "zscore")
    names = [name for name, _ in written]
    assert names == ["pipeline_clean.csv", "pipeline_anomalies.csv"]
    assert sum(rows for _, rows in written) == out["rows_after_transform"]


def test_the_command_runs_each_job_with_each_method_in_fresh_workers_and_saves_the_records(
    tmp_path, monkeypatch, capsys
):
    jobs = [{"id": "uci:1", "name": "a"}, {"id": "adbench:b", "name": "b"}]
    seen = {}
    monkeypatch.setattr(pe.pt, "jobs", lambda registry, pool, adbench: seen.update(
        paths=(registry, pool, adbench)) or jobs)  # fmt: skip

    class Pool:
        def __init__(self, max_workers, max_tasks_per_child):
            seen["pool"] = (max_workers, max_tasks_per_child)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def map(self, function, items):
            seen["items"] = list(items)
            return [
                {"id": job["id"], "method": method, "status": "OK"} for job, method in seen["items"]
            ]

    monkeypatch.setattr(pe, "ProcessPoolExecutor", Pool)
    output = tmp_path / "new" / "dir"
    assert pe.main(["--output", str(output), "--workers", "3", "--only", "uci:1"]) == 0
    assert seen["pool"] == (3, 1)
    assert [(j["id"], m) for j, m in seen["items"]] == [
        ("uci:1", "zscore"),
        ("uci:1", "isolation_forest"),
    ]
    assert seen["paths"] == (
        pe.ROOT / "verification" / "evidence" / "dataset_registry",
        pe.ROOT / "data" / "pool",
        pe.ROOT / "data" / "adbench",
    )
    records = [{"id": "uci:1", "method": m, "status": "OK"} for m in ("zscore", "isolation_forest")]
    text = (output / "pool_etl.json").read_text()
    assert text == json.dumps(records, indent=1, sort_keys=True) + "\n"
    assert capsys.readouterr().out.splitlines() == ["uci:1 zscore OK", "uci:1 isolation_forest OK"]


def test_the_default_worker_count_and_all_jobs_when_no_filter_is_given(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(pe.pt, "jobs", lambda *a: [{"id": "x", "name": "x"}])

    class Pool:
        def __init__(self, max_workers, max_tasks_per_child):
            seen["workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def map(self, function, items):
            seen["count"] = len(list(items))
            return []

    monkeypatch.setattr(pe, "ProcessPoolExecutor", Pool)
    assert pe.main(["--output", str(tmp_path)]) == 0
    assert seen == {"workers": 2, "count": 2}
    with pytest.raises(SystemExit) as stop:
        pe.main([])
    assert stop.value.code == 2


def test_one_item_runs_its_job_with_its_method(monkeypatch):
    monkeypatch.setattr(pe, "run_etl", lambda job, method: {"job": job, "method": method})
    assert pe._one(({"id": "x"}, "zscore")) == {"job": {"id": "x"}, "method": "zscore"}
