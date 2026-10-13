import json
from pathlib import Path

import numpy as np
import pandas as pd

from etl_benchmark.pipeline import detect
from verification.scaling import run_case


class CountingDetector:
    name = "counting"

    def fit(self, frame):
        self.fit_rows = len(frame)
        return self

    def predict(self, frame):
        self.predict_rows = len(frame)
        return pd.Series(False, index=frame.index)

    def score(self, frame):
        self.score_rows = len(frame)
        return pd.Series(np.zeros(len(frame)), index=frame.index)


def test_detector_timing_fields_measure_each_stage(monkeypatch):
    times = iter([1.0, 2.5, 4.0, 7.0])
    monkeypatch.setattr("etl_benchmark.pipeline.time.perf_counter", lambda: next(times))
    detector = CountingDetector()
    frame = pd.DataFrame({"value": [1.0, 2.0, 3.0]})
    result = detect(frame, detector, fit_df=frame.iloc[:2])
    assert (detector.fit_rows, detector.predict_rows, detector.score_rows) == (2, 3, 3)
    assert (result.fit_s, result.predict_s, result.score_s, result.detect_s) == (1.5, 1.5, 3.0, 6.0)


def test_scaling_case_records_workload_cap_and_nonnegative_costs():
    row = run_case(lambda: CountingDetector(), n_rows=30, n_features=4, fit_cap=12, seed=4)
    assert row["status"] == "PASS"
    assert row["eval_rows"] == 30
    assert row["fit_rows"] == 12
    assert row["n_features"] == 4
    assert row["fit_s"] >= 0
    assert row["predict_s"] >= 0
    assert row["score_s"] >= 0
    assert row["detect_s"] == row["fit_s"] + row["predict_s"] + row["score_s"]
    assert row["peak_python_bytes"] >= 0


def test_scaling_case_records_failure_instead_of_omitting_method():
    def broken():
        raise MemoryError("not enough memory")

    row = run_case(broken, n_rows=30, n_features=4, fit_cap=None, seed=4)
    assert row["status"] == "FAIL"
    assert row["reason"] == "MemoryError: not enough memory"
    assert row["eval_rows"] == row["fit_rows"] == 30


def test_archived_scaling_run_declares_workloads_and_all_methods():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / "verification/evidence/scaling.json").read_text())
    assert record["sizes"] == [100, 300, 900]
    assert record["methods"] == ["isolation_forest", "lof", "ocsvm"]
    assert record["repeats"] == 3
    assert len(record["results"]) == 27
    assert all(row["status"] == "PASS" for row in record["results"])
    assert all(row["fit_rows"] == row["eval_rows"] for row in record["results"])
    assert record["data_loading"].startswith("generated in memory")
    assert record["memory_measure"].startswith("tracemalloc")
