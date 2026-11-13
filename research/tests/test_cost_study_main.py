"""The cost study entry point: its workers, its wait for a quiet machine, its record."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cost_study as cs  # noqa: E402


def test_the_detection_worker_prints_one_json_line_for_the_array_it_loads(
    monkeypatch, tmp_path, capsys
):
    path = tmp_path / "x.npy"
    np.save(path, np.arange(6.0).reshape(3, 2))
    seen = {}

    def fake(method, array):
        seen.update(method=method, array=array)
        return {"status": "OK", "method": method}

    monkeypatch.setattr(cs, "run_detection", fake)
    assert cs._worker("zscore", str(path)) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "OK", "method": "zscore"}
    assert seen["method"] == "zscore" and seen["array"].shape == (3, 2)


def test_the_etl_worker_prints_one_json_line_for_the_csv_method_and_folder_it_gets(
    monkeypatch, tmp_path, capsys
):
    seen = {}

    def fake(csv, method, out):
        seen.update(csv=csv, method=method, out=out)
        return {"status": "OK"}

    monkeypatch.setattr(cs, "run_etl", fake)
    assert cs._etl_worker("a.csv", "iqr", str(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "OK"}
    assert seen == {"csv": Path("a.csv"), "method": "iqr", "out": tmp_path}


def _load(monkeypatch, values):
    seq = iter(values)
    monkeypatch.setattr(cs.os, "getloadavg", lambda: (next(seq), 0.0, 0.0))
    monkeypatch.setattr(cs.os, "cpu_count", lambda: 8)


def test_a_quiet_machine_is_measured_at_once_without_sleeping(monkeypatch):
    _load(monkeypatch, [4.0, 4.0])
    slept = []
    monkeypatch.setattr(cs.time, "sleep", slept.append)
    assert cs.wait_for_quiet() == 4.0
    assert slept == []


def test_a_busy_machine_is_waited_for_fifteen_seconds_at_a_time_until_it_is_quiet(monkeypatch):
    _load(monkeypatch, [4.1, 6.0, 3.0, 3.0])
    slept = []
    monkeypatch.setattr(cs.time, "sleep", slept.append)
    assert cs.wait_for_quiet() == 3.0
    assert slept == [15, 15]


def test_the_wait_ends_at_its_limit_and_reports_the_load_it_gave_up_on(monkeypatch):
    monkeypatch.setattr(cs.os, "getloadavg", lambda: (9.0, 0.0, 0.0))
    monkeypatch.setattr(cs.os, "cpu_count", lambda: 8)
    clock = iter([100.0, 100.0, 400.0, 701.0, 701.0])
    monkeypatch.setattr(cs.time, "time", lambda: next(clock))
    slept = []
    monkeypatch.setattr(cs.time, "sleep", slept.append)
    assert cs.wait_for_quiet(limit_s=600) == 9.0
    assert slept == [15, 15]


def test_the_default_wait_limit_is_ten_minutes(monkeypatch):
    monkeypatch.setattr(cs.os, "getloadavg", lambda: (9.0, 0.0, 0.0))
    monkeypatch.setattr(cs.os, "cpu_count", lambda: 8)
    clock = iter([0.0, 599.0, 601.0, 601.0])
    monkeypatch.setattr(cs.time, "time", lambda: next(clock))
    monkeypatch.setattr(cs.time, "sleep", lambda s: None)
    cs.wait_for_quiet()


class _Done:
    def __init__(self, code, out="", err=""):
        self.returncode, self.stdout, self.stderr = code, out, err


@pytest.fixture
def study(monkeypatch, tmp_path):
    csv = tmp_path / "card.csv"
    csv.write_text("a,b\n1,2\n")
    calls = {"measure": [], "etl": []}

    def measure(method, n, d, rep, *, workdir, timeout=cs.TIMEOUT_S):
        calls["measure"].append((method, n, d, rep, workdir.exists(), timeout))
        return {
            "status": "OK", "method": method, "n": n, "d": d, "rep": rep,
            "detect_s": float(n), "rss_delta_bytes": 10,
        }  # fmt: skip

    real_run = subprocess.run

    def run(command, **kwargs):
        if "--etl-worker" not in command:
            return real_run(command, **kwargs)
        calls["etl"].append((command, kwargs))
        return _Done(0, "noise\n" + json.dumps({"status": "OK", "method": command[-2]}) + "\n")

    monkeypatch.setattr(cs, "wait_for_quiet", lambda: 1.25)
    monkeypatch.setattr(cs, "measure_in_subprocess", measure)
    monkeypatch.setattr(cs.subprocess, "run", run)
    return csv, calls


def _main(csv, out, *extra):
    return cs.main(
        [
            "--output",
            str(out),
            "--sizes",
            "1000",
            "3000",
            "--methods",
            "zscore",
            "--csv",
            str(csv),
            *extra,
        ]
    )


def test_the_study_measures_every_size_then_the_wide_table_and_two_etl_methods_three_times(
    study, tmp_path, capsys
):
    csv, calls = study
    out = tmp_path / "out" / "cost_study.json"
    out.parent.mkdir()
    assert _main(csv, out) == 0
    assert capsys.readouterr().out == f"wrote {out}\n"
    narrow = [(n, d, rep) for _m, n, d, rep, _w, _t in calls["measure"] if d == cs.FEATURES]
    assert narrow == [(n, 8, rep) for n in (1000, 3000) for rep in range(5)]
    wide = [(n, d, rep) for _m, n, d, rep, _w, _t in calls["measure"] if d == cs.WIDE_FEATURES]
    assert wide == [(30_000, 29, rep) for rep in range(5)]
    assert all(exists and timeout == 300 for *_x, exists, timeout in calls["measure"])
    etl = [(c[-2], kw["timeout"]) for c, kw in calls["etl"]]
    assert etl == [("zscore", 600)] * 3 + [("isolation_forest", 600)] * 3
    command, kwargs = calls["etl"][0]
    assert command[:3] == [sys.executable, cs.__file__, "--etl-worker"]
    assert command[3] == str(csv)
    assert Path(command[5]).name == "etl_zscore_0" and Path(command[5]).is_dir()
    assert kwargs["capture_output"] is True and kwargs["text"] is True and kwargs["check"] is False


def test_the_record_holds_the_measurements_their_summaries_the_settings_and_the_provenance(
    study, tmp_path
):
    csv, _ = study
    out = tmp_path / "cost_study.json"
    _main(csv, out)
    text = out.read_text()
    result = json.loads(text)
    assert text == json.dumps(result, indent=2, sort_keys=True) + "\n"
    assert len(result["records"]) == 10 and len(result["wide_records"]) == 5
    assert [r["status"] for r in result["etl_records"]] == ["OK"] * 6
    assert result["etl_records"][0]["method"] == "zscore"
    assert result["summary"] == cs.summarize(result["records"])
    assert result["wide_summary"] == cs.summarize(result["wide_records"])
    assert result["settings"] == {
        "seed": 42, "sizes": [1000, 3000], "features": 8, "wide": [30_000, 29],
        "timeout_s": 300, "methods": ["zscore"], "lstm_epochs": 5, "lstm_fit_rows": 50_000,
        "load_at_start": 1.25,
    }  # fmt: skip
    provenance = result["provenance"]
    assert provenance["script_sha256"] == hashlib.sha256(Path(cs.__file__).read_bytes()).hexdigest()
    assert provenance["dataset_sha256"] == hashlib.sha256(csv.read_bytes()).hexdigest()
    assert provenance["protocol"] == "verification/cost_study.md"
    assert set(provenance["versions"]) == {"numpy", "pandas", "scikit-learn", "torch"}
    assert provenance["cpu_count"] is not None and provenance["python"]


def test_the_run_record_names_the_output_the_seed_and_the_dataset(study, tmp_path):
    csv, _ = study
    out = tmp_path / "cost_study.json"
    _main(csv, out)
    record = json.loads((tmp_path / "run_cost_study.json").read_text())
    assert record["experiment"] == "cost_study"
    assert record["seeds"] == [42]
    assert record["dataset"] == {"identity": "synthetic_gaussian+credit_card"}
    assert record["outputs"] == ["cost_study.json"]
    assert record["settings"]["script_sha256"] and record["settings"]["sizes"] == [1000, 3000]


def test_a_failed_etl_worker_is_recorded_with_its_method_and_the_end_of_its_error(
    study, tmp_path, monkeypatch
):
    csv, _ = study
    long_error = "e" * 500

    real_run = subprocess.run

    def run(command, **kwargs):
        if "--etl-worker" not in command:
            return real_run(command, **kwargs)
        return _Done(2, "", long_error)

    monkeypatch.setattr(cs.subprocess, "run", run)
    out = tmp_path / "cost_study.json"
    _main(csv, out)
    etl = json.loads(out.read_text())["etl_records"]
    assert etl[0] == {"status": "FAIL", "method": "zscore", "reason": "e" * 300}
    assert [r["method"] for r in etl] == ["zscore"] * 3 + ["isolation_forest"] * 3


def test_the_defaults_are_every_size_every_method_and_the_credit_card_file(monkeypatch, tmp_path):
    seen = {}

    def sweep(methods, sizes, d, measure):
        seen.setdefault("calls", []).append((list(methods), list(sizes), d))
        return []

    monkeypatch.setattr(cs, "wait_for_quiet", lambda: 0.0)
    monkeypatch.setattr(cs, "sweep", sweep)
    monkeypatch.setattr(cs.subprocess, "run", lambda *a, **k: _Done(1, "", ""))
    from etl_benchmark import config

    card = tmp_path / "default.csv"
    card.write_text("z\n")
    monkeypatch.setattr(config, "CREDIT_CARD_CSV", card)
    out = tmp_path / "o.json"
    assert cs.main(["--output", str(out)]) == 0
    assert seen["calls"] == [
        (list(cs.METHODS), list(cs.SIZES), cs.FEATURES),
        (list(cs.METHODS), [cs.WIDE_ROWS], cs.WIDE_FEATURES),
    ]
    assert (
        json.loads(out.read_text())["provenance"]["dataset_sha256"]
        == hashlib.sha256(card.read_bytes()).hexdigest()
    )


def test_the_default_output_is_the_experiments_results_folder():
    import argparse

    seen = {}
    original = argparse.ArgumentParser.parse_args

    def spy(self, args=None, namespace=None):
        parsed = original(self, args, namespace)
        seen["output"] = parsed.output
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = spy
    try:
        with pytest.raises(SystemExit):
            cs.main([])
    finally:
        argparse.ArgumentParser.parse_args = original
    assert seen["output"] == cs.ROOT / "experiments" / "results" / "cost_study.json"


def test_worker_options_run_the_worker_instead_of_the_study(monkeypatch, tmp_path):
    monkeypatch.setattr(cs, "_worker", lambda m, p: 7)
    monkeypatch.setattr(cs, "_etl_worker", lambda c, m, o: 9)
    monkeypatch.setattr(cs, "wait_for_quiet", lambda: pytest.fail("the study must not start"))
    assert cs.main(["--worker", "zscore", "x.npy"]) == 7
    assert cs.main(["--etl-worker", "a.csv", "iqr", "out"]) == 9
