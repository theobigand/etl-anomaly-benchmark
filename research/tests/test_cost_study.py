"""Pure logic of the cost study: memory units, sweep termination, growth exponent, workers."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cost_study as cs  # noqa: E402


def test_the_data_are_reproducible_and_have_the_requested_shape():
    a, b = cs.make_data(500, 8), cs.make_data(500, 8)
    assert a.shape == (500, 8) and np.array_equal(a, b)
    assert not np.array_equal(a, cs.make_data(500, 8, seed=1))


def test_repetitions_shrink_for_large_inputs():
    assert cs.reps_for(30_000) == 5 and cs.reps_for(100_000) == 3


@pytest.mark.parametrize(
    ("platform", "raw", "expected"), [("darwin", 2048, 2048), ("linux", 2048, 2048 * 1024)]
)
def test_peak_memory_is_reported_in_bytes_on_both_platforms(monkeypatch, platform, raw, expected):
    monkeypatch.setattr(cs.sys, "platform", platform)
    monkeypatch.setattr(cs.resource, "getrusage", lambda who: type("U", (), {"ru_maxrss": raw})())
    assert cs.peak_rss_bytes() == expected


def test_a_run_made_under_heavy_load_is_flagged_not_dropped():
    assert cs.is_contended(8.0, 1.0, cores=10) is True
    assert cs.is_contended(1.0, 2.0, cores=10) is False


def _fake(timeouts_at):
    calls = []

    def measure(method, n, d, rep):
        calls.append((method, n, rep))
        if n >= timeouts_at:
            return {"status": "TIMEOUT", "method": method, "n": n, "rep": rep}
        return {"status": "OK", "method": method, "n": n, "rep": rep, "detect_s": n / 1000.0}

    return measure, calls


def test_a_method_that_times_out_is_not_tried_on_larger_sizes_and_the_skip_is_recorded():
    measure, calls = _fake(timeouts_at=10_000)
    records = cs.sweep(["slow"], [1000, 3000, 10_000, 30_000, 100_000], 8, measure)
    sizes_tried = {n for _m, n, _r in calls}
    assert sizes_tried == {1000, 3000, 10_000}
    skipped = [r for r in records if r["status"] == "SKIPPED"]
    assert {r["n"] for r in skipped} == {30_000, 100_000}
    assert all("TIMEOUT at 10000" in r["reason"] for r in skipped)
    assert len([r for r in records if r["n"] == 3000 and r["status"] == "OK"]) == 5


def test_a_failure_stops_only_that_method():
    def measure(method, n, d, rep):
        status = "FAIL" if method == "bad" and n >= 3000 else "OK"
        return {"status": status, "method": method, "n": n, "rep": rep, "detect_s": 1.0}

    records = cs.sweep(["bad", "good"], [1000, 3000, 10_000], 8, measure)
    assert {r["n"] for r in records if r["method"] == "good" and r["status"] == "OK"} == {
        1000,
        3000,
        10_000,
    }
    assert any(
        r["method"] == "bad" and r["status"] == "SKIPPED" and r["n"] == 10_000 for r in records
    )


def test_the_summary_gives_quartiles_and_an_empirical_growth_exponent():
    records = [
        {
            "status": "OK",
            "method": "m",
            "n": n,
            "detect_s": (n / 1000) ** 1.5 * f,
            "rss_delta_bytes": 10 * n,
        }
        for n in (1000, 3000, 10_000, 30_000)
        for f in (0.9, 1.0, 1.1)
    ]
    summary = cs.summarize(records)["m"]
    assert summary["growth_exponent"] == pytest.approx(1.5, abs=0.05)
    point = summary["points"]["10000"]
    assert point["detect_s_median"] == pytest.approx(10**1.5, rel=0.01)
    assert point["detect_s_q1"] < point["detect_s_median"] < point["detect_s_q3"]
    assert summary["largest_measured"] == 30_000


def test_one_point_gives_no_exponent_and_failures_are_counted():
    records = [
        {"status": "OK", "method": "m", "n": 1000, "detect_s": 1.0, "rss_delta_bytes": 1},
        {"status": "TIMEOUT", "method": "m", "n": 3000},
        {"status": "SKIPPED", "method": "m", "n": 10_000, "reason": "x"},
    ]
    summary = cs.summarize(records)["m"]
    assert summary["growth_exponent"] is None
    assert summary["failures"] == {"TIMEOUT": 1, "SKIPPED": 1}


def test_a_worker_measures_the_stages_and_memory_of_a_small_run():
    out = cs.run_detection("zscore", cs.make_data(400, 4))
    assert out["status"] == "OK"
    for key in (
        "fit_s",
        "predict_s",
        "score_s",
        "detect_s",
        "rss_before_bytes",
        "rss_peak_bytes",
        "rss_delta_bytes",
    ):
        assert out[key] >= 0
    assert out["detect_s"] == pytest.approx(out["fit_s"] + out["predict_s"] + out["score_s"])
    assert out["rss_peak_bytes"] >= out["rss_before_bytes"]


def test_the_lstm_worker_reports_its_training_budget():
    out = cs.run_detection("lstm_autoencoder", cs.make_data(600, 4), lstm_epochs=1, fit_rows=300)
    assert out["status"] == "OK" and out["epochs_run"] == 1 and out["fit_rows"] == 300


def test_an_unknown_method_is_a_failure_with_a_reason():
    out = cs.run_detection("nope", cs.make_data(100, 3))
    assert out["status"] == "FAIL" and "unknown method" in out["reason"]


def test_a_subprocess_that_exceeds_the_budget_is_recorded_as_a_timeout(monkeypatch, tmp_path):
    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(cs.subprocess, "run", slow)
    record = cs.measure_in_subprocess("zscore", 1000, 8, 0, workdir=tmp_path, timeout=1)
    assert record["status"] == "TIMEOUT" and record["n"] == 1000 and "load_before" in record


def test_a_crashed_worker_is_recorded_as_a_failure(monkeypatch, tmp_path):
    done = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom\n")
    monkeypatch.setattr(cs.subprocess, "run", lambda *a, **k: done)
    record = cs.measure_in_subprocess("zscore", 1000, 8, 0, workdir=tmp_path, timeout=5)
    assert record["status"] == "FAIL" and "boom" in record["reason"]


def test_the_etl_stages_are_timed_separately(tmp_path):
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(rng.normal(size=(300, 3)), columns=["a", "b", "c"])
    frame["Class"] = (rng.random(300) < 0.1).astype(int)
    csv = tmp_path / "toy.csv"
    frame.to_csv(csv, index=False)
    out = cs.run_etl(csv, "zscore", tmp_path / "out")
    assert out["status"] == "OK"
    assert set(out["stages_s"]) == {"extract", "transform", "detect", "load"}
    assert all(v >= 0 for v in out["stages_s"].values())
    assert out["rows_in"] == 300 and out["rss_peak_bytes"] > 0
    assert (tmp_path / "out" / "pipeline_clean.csv").is_file()
