"""Exact budgets, records, commands and summaries of the cost study measurements."""

import itertools
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cost_study as cs  # noqa: E402


@pytest.mark.parametrize(("n", "reps"), [(30_000, 5), (30_001, 3), (1_000, 5), (300_000, 3)])
def test_the_repetitions_change_just_above_thirty_thousand_rows(n, reps):
    assert cs.reps_for(n) == reps


@pytest.mark.parametrize(
    ("before", "after", "cores", "expected"),
    [(5.0, 1.0, 10, False), (1.0, 5.0, 10, False), (4.0, 1.0, 10, False), (5.01, 1.0, 10, True)],
)
def test_a_run_is_contended_only_above_half_the_cores(before, after, cores, expected):
    assert cs.is_contended(before, after, cores) is expected


def test_the_columns_of_a_frame_are_numbered_from_zero():
    frame = cs._frame(np.zeros((3, 4)))
    assert list(frame.columns) == ["f0", "f1", "f2", "f3"]


class _Scores:
    def __init__(self):
        self.compared = []

    def __gt__(self, other):
        self.compared.append(other)
        return True


def _stub_lstm(monkeypatch, scores=None):
    seen = {}

    class Model:
        threshold_ = 0.75

        def __init__(self, columns, time_column, **kwargs):
            seen.update(columns=columns, time_column=time_column, kwargs=kwargs)

        def fit(self, frame, validation, contamination):
            seen.update(frame=frame, validation=validation, contamination=contamination)

        def score(self, frame):
            seen["scored"] = frame
            return scores if scores is not None else _Scores()

        def settings(self):
            return {"epochs_run": 3}

    monkeypatch.setitem(sys.modules, "lstm_detector", types.SimpleNamespace(LSTMAutoencoder=Model))
    return seen


def test_the_lstm_run_builds_a_one_second_clock_from_the_epoch_and_trains_on_the_columns(
    monkeypatch,
):
    seen = _stub_lstm(monkeypatch)
    cs._lstm_run(np.zeros((30, 3)), epochs=4, fit_rows=17)
    assert seen["columns"] == ["f0", "f1", "f2"] and seen["time_column"] == "t"
    assert seen["kwargs"] == {"max_epochs": 4, "fit_rows": 17, "seed": 42}
    clock = seen["frame"]["t"]
    assert clock.iloc[0] == pd.Timestamp("1970-01-01", tz="UTC") and str(clock.dt.tz) == "UTC"
    assert set(clock.diff().dropna()) == {pd.Timedelta(seconds=1)}
    assert seen["contamination"] == 0.01


@pytest.mark.parametrize(("rows", "expected"), [(6000, 5000), (5001, 5000), (5000, 5000), (30, 30)])
def test_the_validation_part_is_at_most_five_thousand_rows(monkeypatch, rows, expected):
    seen = _stub_lstm(monkeypatch)
    cs._lstm_run(np.zeros((rows, 2)), epochs=1, fit_rows=10)
    assert len(seen["validation"]) == expected


def test_the_lstm_run_times_its_three_stages_and_compares_the_scores_with_the_threshold(
    monkeypatch,
):
    scores = _Scores()
    _stub_lstm(monkeypatch, scores)
    clock = iter([10.0, 12.0, 17.0, 20.0])
    monkeypatch.setattr(cs.time, "perf_counter", lambda: next(clock))
    out = cs._lstm_run(np.zeros((30, 3)), epochs=4, fit_rows=17)
    assert (out["epochs_run"], out["fit_rows"]) == (3, 17)
    assert scores.compared == [0.75]


def test_the_lstm_stage_durations_are_differences_of_successive_clock_readings(monkeypatch):
    _stub_lstm(monkeypatch)
    clock = iter([100.0, 101.0, 104.0, 112.0])
    monkeypatch.setattr(cs.time, "perf_counter", lambda: next(clock))
    out = cs._lstm_run(np.zeros((30, 3)), epochs=1, fit_rows=5)
    assert (out["fit_s"], out["score_s"], out["predict_s"]) == (1.0, 3.0, 8.0)


def _registry(monkeypatch, detect, calls):
    import etl_benchmark.pipeline as pipeline
    import etl_benchmark.registry as registry

    def get_detector(method, contamination):
        calls.append(("detector", method, contamination))
        return ("detector", method)

    monkeypatch.setattr(pipeline, "detect", detect)
    monkeypatch.setattr(registry, "get_detector", get_detector)


def test_a_detector_is_warmed_up_then_timed_with_the_same_one_percent_contamination(monkeypatch):
    calls = []

    def detect(frame, detector, **kwargs):
        calls.append(("detect", len(frame)))
        return types.SimpleNamespace(fit_s=1.0, predict_s=2.0, score_s=4.0)

    _registry(monkeypatch, detect, calls)
    readings = iter([100, 250])
    monkeypatch.setattr(cs, "peak_rss_bytes", lambda: next(readings))
    out = cs.run_detection("zscore", np.zeros((500, 2)))
    assert calls == [
        ("detector", "zscore", 0.01),
        ("detect", cs.WARMUP_ROWS),
        ("detector", "zscore", 0.01),
        ("detect", 500),
    ]
    assert out == {
        "status": "OK",
        "fit_s": 1.0,
        "predict_s": 2.0,
        "score_s": 4.0,
        "detect_s": 7.0,
        "rss_before_bytes": 100,
        "rss_peak_bytes": 250,
        "rss_delta_bytes": 150,
    }


def test_the_lstm_is_warmed_up_with_one_epoch_on_the_warm_up_rows(monkeypatch):
    runs = []
    monkeypatch.setattr(
        cs,
        "_lstm_run",
        lambda array, epochs, rows: (
            runs.append((len(array), epochs, rows))
            or {"fit_s": 1.0, "predict_s": 1.0, "score_s": 1.0}
        ),
    )
    cs.run_detection("lstm_autoencoder", np.zeros((500, 2)), lstm_epochs=7, fit_rows=99)
    assert runs == [(cs.WARMUP_ROWS, 1, cs.WARMUP_ROWS), (500, 7, 99)]


def test_a_detector_that_raises_is_a_failure_named_by_its_exception_type_and_message(monkeypatch):
    def detect(frame, detector, **kwargs):
        raise ValueError("boom")

    _registry(monkeypatch, detect, [])
    assert cs.run_detection("zscore", np.zeros((300, 2))) == {
        "status": "FAIL",
        "reason": "ValueError: boom",
    }


def test_the_pipeline_stages_are_timed_in_order_and_the_flagged_rows_are_split_off(
    monkeypatch, tmp_path
):
    import etl_benchmark.load as load
    import etl_benchmark.pipeline as pipeline
    import etl_benchmark.registry as registry

    frame = pd.DataFrame({"a": [1, 2, 3, 4]})
    flags = np.array([True, False, False, True])
    written, seen = [], {}
    monkeypatch.setattr(pipeline, "extract", lambda csv: frame)
    monkeypatch.setattr(pipeline, "transform", lambda df: df.iloc[:3].copy())

    def detect(df, detector, **kwargs):
        seen["kwargs"] = kwargs
        return types.SimpleNamespace(flags=flags[:3])

    def get_detector(method, contamination):
        seen["detector"] = (method, contamination)
        return "d"

    monkeypatch.setattr(pipeline, "detect", detect)
    monkeypatch.setattr(registry, "get_detector", get_detector)
    monkeypatch.setattr(
        load, "write_csv", lambda df, path: written.append((df["a"].tolist(), path))
    )
    clock = iter([0.0, 1.0, 1.0, 3.0, 3.0, 7.0, 7.0, 15.0])
    monkeypatch.setattr(cs.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(cs, "peak_rss_bytes", lambda: 4096)
    out = cs.run_etl(Path("in.csv"), "iqr", tmp_path)
    assert seen == {"kwargs": {"label_column": "Class"}, "detector": ("iqr", 0.0017)}
    assert written == [
        ([2, 3], tmp_path / "pipeline_clean.csv"),
        ([1], tmp_path / "pipeline_anomalies.csv"),
    ]
    assert out == {
        "status": "OK",
        "method": "iqr",
        "rows_in": 4,
        "rows_after_transform": 3,
        "stages_s": {"extract": 1.0, "transform": 2.0, "detect": 4.0, "load": 8.0},
        "detect_stage_share": 4.0 / 15.0,
        "rss_peak_bytes": 4096,
    }


def _run_recorder(monkeypatch, done):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        if isinstance(done, Exception):
            raise done
        return done

    monkeypatch.setattr(cs.subprocess, "run", run)
    return seen


def test_the_data_file_is_made_once_and_the_worker_is_run_with_the_given_budget(
    monkeypatch, tmp_path
):
    ok = subprocess.CompletedProcess([], 0, stdout='noise\n{"status": "OK"}\n', stderr="")
    seen = _run_recorder(monkeypatch, ok)
    cs.measure_in_subprocess("lof", 1000, 3, 2, workdir=tmp_path, timeout=9)
    path = tmp_path / "data_1000_3.npy"
    assert np.array_equal(np.load(path), cs.make_data(1000, 3))
    assert seen["command"] == [sys.executable, cs.__file__, "--worker", "lof", str(path)]
    assert seen["kwargs"] == {"capture_output": True, "text": True, "timeout": 9, "check": False}
    np.save(path, np.arange(3.0))
    cs.measure_in_subprocess("lof", 1000, 3, 2, workdir=tmp_path)
    assert np.array_equal(np.load(path), np.arange(3.0))
    assert seen["kwargs"]["timeout"] == cs.TIMEOUT_S


def test_a_good_run_keeps_its_identity_the_last_line_of_its_output_and_the_load(
    monkeypatch, tmp_path
):
    done = subprocess.CompletedProcess(
        [], 0, stdout='{"status": "no"}\nwarning\n{"status": "OK", "detect_s": 1.5}\n', stderr=""
    )
    _run_recorder(monkeypatch, done)
    loads = iter([(1.5, 9.0, 9.0), (2.5, 9.0, 9.0)])
    monkeypatch.setattr(cs.os, "getloadavg", lambda: next(loads))
    monkeypatch.setattr(cs.os, "cpu_count", lambda: 4)
    record = cs.measure_in_subprocess("lof", 1000, 3, 2, workdir=tmp_path)
    assert record == {
        "method": "lof",
        "n": 1000,
        "d": 3,
        "rep": 2,
        "load_before": 1.5,
        "status": "OK",
        "detect_s": 1.5,
        "load_after": 2.5,
        "contended": True,
    }


@pytest.mark.parametrize(
    ("cores", "load", "contended"), [(4, 1.0, False), (None, 0.8, True), (None, 0.4, False)]
)
def test_the_contention_uses_the_real_core_count_and_one_core_when_it_is_unknown(
    monkeypatch, tmp_path, cores, load, contended
):
    ok = subprocess.CompletedProcess([], 0, stdout='{"status": "OK"}\n', stderr="")
    _run_recorder(monkeypatch, ok)
    monkeypatch.setattr(cs.os, "getloadavg", lambda: (load, 9.0, 9.0))
    monkeypatch.setattr(cs.os, "cpu_count", lambda: cores)
    record = cs.measure_in_subprocess("lof", 1000, 3, 0, workdir=tmp_path)
    assert record["contended"] is contended
    assert record["load_before"] == record["load_after"] == load


def test_a_timeout_names_its_budget(monkeypatch, tmp_path):
    _run_recorder(monkeypatch, subprocess.TimeoutExpired(cmd="x", timeout=5))
    record = cs.measure_in_subprocess("lof", 1000, 3, 0, workdir=tmp_path, timeout=5)
    assert record["status"] == "TIMEOUT" and record["reason"] == "more than 5 s"


@pytest.mark.parametrize(
    ("code", "out", "err", "reason"),
    [
        (1, "x\n", "bad\n", "bad"),
        (0, "", "bad", "bad"),
        (0, "  \n", "", "no output"),
        (2, "", "", "no output"),
        (1, "x", "e" * 400, "e" * 300),
        (1, "x", "e" * 299 + "f", "e" * 299 + "f"),
    ],
)
def test_a_worker_that_fails_or_prints_nothing_is_a_failure_with_the_end_of_its_error(
    monkeypatch, tmp_path, code, out, err, reason
):
    _run_recorder(monkeypatch, subprocess.CompletedProcess([], code, stdout=out, stderr=err))
    record = cs.measure_in_subprocess("lof", 1000, 3, 0, workdir=tmp_path)
    assert record["status"] == "FAIL" and record["reason"] == reason


def test_a_worker_with_output_and_a_zero_exit_is_not_a_failure(monkeypatch, tmp_path):
    ok = subprocess.CompletedProcess([], 0, stdout='{"status": "OK"}', stderr="warn")
    _run_recorder(monkeypatch, ok)
    assert cs.measure_in_subprocess("lof", 1000, 3, 0, workdir=tmp_path)["status"] == "OK"


def test_a_skipped_size_keeps_its_method_size_features_and_reason():
    def measure(method, n, d, rep):
        return {"status": "FAIL", "method": method, "n": n}

    records = cs.sweep(["m"], [10, 20], 8, measure, reps=lambda n: 1)
    assert records[1] == {
        "status": "SKIPPED",
        "method": "m",
        "n": 20,
        "d": 8,
        "reason": "FAIL at 10",
    }


def test_the_summary_counts_each_kind_of_failure_and_gives_exact_quartiles():
    ok = [
        {"status": "OK", "method": "m", "n": 10, "detect_s": t, "rss_delta_bytes": 7}
        for t in (1.0, 2.0, 3.0, 4.0, 5.0)
    ]
    bad = [{"status": "TIMEOUT", "method": "m", "n": 20}] * 2
    summary = cs.summarize(ok + bad)["m"]
    assert summary["failures"] == {"TIMEOUT": 2}
    assert summary["points"]["10"] == {
        "runs": 5,
        "detect_s_median": 3.0,
        "detect_s_q1": 2.0,
        "detect_s_q3": 4.0,
        "detect_s_min": 1.0,
        "detect_s_max": 5.0,
        "rss_delta_bytes_median": 7.0,
    }


def test_two_sizes_are_enough_for_an_exponent_and_a_zero_median_gives_none():
    def rec(n, t):
        return {"status": "OK", "method": "m", "n": n, "detect_s": t, "rss_delta_bytes": 1}

    assert cs.summarize([rec(10, 1.0), rec(100, 100.0)])["m"]["growth_exponent"] == pytest.approx(
        2.0
    )
    assert cs.summarize([rec(10, 0.0), rec(100, 1.0)])["m"]["growth_exponent"] is None


def test_a_method_with_only_failures_has_no_largest_size():
    summary = cs.summarize([{"status": "TIMEOUT", "method": "m", "n": 10}])["m"]
    assert summary["largest_measured"] is None and summary["points"] == {}


def test_a_busy_machine_with_unknown_cores_is_waited_for_and_the_limit_is_exclusive(monkeypatch):
    monkeypatch.setattr(cs.os, "cpu_count", lambda: None)
    loads = iter([0.9, 0.2, 0.2])
    monkeypatch.setattr(cs.os, "getloadavg", lambda: (next(loads), 0.0, 0.0))
    slept = []
    monkeypatch.setattr(cs.time, "sleep", slept.append)
    assert cs.wait_for_quiet() == 0.2 and slept == [15]
    monkeypatch.setattr(cs.os, "getloadavg", lambda: (9.0, 0.0, 0.0))
    clock = itertools.chain([0.0, 600.0], itertools.repeat(600.0))
    monkeypatch.setattr(cs.time, "time", lambda: next(clock))
    slept.clear()
    cs.wait_for_quiet(limit_s=600)
    assert slept == []


def test_the_command_line_names_its_worker_arguments(capsys):
    with pytest.raises(SystemExit):
        cs.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--worker METHOD NPY" in text and "--etl-worker CSV METHOD OUT" in text


def test_the_study_directory_the_etl_output_and_the_record_files_are_named_as_documented(
    monkeypatch, tmp_path
):
    csv = tmp_path / "card.csv"
    csv.write_text("a\n1\n")
    commands = []

    def measure(method, n, d, rep, *, workdir, timeout=cs.TIMEOUT_S):
        return {
            "status": "OK", "method": method, "n": np.int64(n), "d": d, "rep": rep,
            "detect_s": 1.0, "rss_delta_bytes": np.int64(5),
        }  # fmt: skip

    real_run = subprocess.run

    def run(command, **kwargs):
        if "--etl-worker" not in command:
            return real_run(command, **kwargs)
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='x\ny\n{"status": "OK"}\n', stderr="")

    monkeypatch.setattr(cs, "wait_for_quiet", lambda: 0.0)
    monkeypatch.setattr(cs, "measure_in_subprocess", measure)
    monkeypatch.setattr(cs.subprocess, "run", run)
    out = tmp_path / "result" / "cost_study.json"
    out.parent.mkdir()
    assert (
        cs.main(["--output", str(out), "--sizes", "10", "--methods", "zscore", "--csv", str(csv)])
        == 0
    )
    assert Path(commands[0][5]).parent.name.startswith("cost_study_")
    assert sorted(p.name for p in out.parent.iterdir()) == [
        "cost_study.json",
        "run_cost_study.json",
    ]
    result = json.loads(out.read_text())
    assert {r["status"] for r in result["etl_records"]} == {"OK"}
    assert result["records"][0]["n"] == 10.0
    provenance = result["provenance"]
    assert provenance["platform"] and provenance["machine"]
