"""Exact commands, boundaries, messages and report fields of the reproduction check."""

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from verification import evidence_schema, lock_environment, reproduce


def _csv(path, f1, std, detect=None):
    frame = pd.DataFrame({"f1_mean": [f1], "f1_std": [std]}, index=pd.Index(["a"], name="detector"))
    if detect is not None:
        frame["detect_s_mean"] = [detect]
    frame.to_csv(path)
    return path


def test_a_difference_exactly_as_large_as_the_reference_spread_is_still_statistical(tmp_path):
    new, old = _csv(tmp_path / "n.csv", 0.75, 0.0), _csv(tmp_path / "o.csv", 0.5, 0.25)
    assert reproduce.compare(new, old)["kind"] == "STATISTICAL"
    wider = _csv(tmp_path / "w.csv", 0.8125, 0.0)
    assert reproduce.compare(wider, old)["kind"] == "DIFFERENT"
    exact = reproduce.compare(_csv(tmp_path / "e.csv", 0.5, 0.25), old)
    assert exact["kind"] == "NUMERICAL" and exact["max_abs_diff"] == 0.0


def test_the_timing_spread_is_relative_and_missing_spread_counts_as_zero(tmp_path):
    new = _csv(tmp_path / "n.csv", 0.5, 0.25, detect=3.0)
    old = _csv(tmp_path / "o.csv", 0.5, 0.25, detect=2.0)
    assert reproduce.compare(new, old)["timing_max_rel_diff"] == pytest.approx(0.5)
    nan_old = pd.DataFrame({"f1_mean": [0.5], "f1_std": [None]}, index=pd.Index(["a"], name="d"))
    nan_old.to_csv(tmp_path / "nan.csv")
    off = _csv(tmp_path / "off.csv", 0.5001, 0.25)
    assert reproduce.compare(off, tmp_path / "nan.csv")["kind"] == "DIFFERENT"


def test_the_replay_command_names_the_results_folder_and_every_archived_seed():
    out = Path("out")
    command = reproduce.command_for("cardio", "py", out)
    assert command[:5] == [
        "py",
        "experiments/run_benchmark.py",
        "--dataset",
        "cardio",
        "--results-dir",
    ]
    assert command[5] == str(out) and command[6] == "--seeds"
    synthetic = reproduce.command_for("synthetic", "py", out)
    assert synthetic[-2:] == ["--figure", str(out / "heatmap_replay.png")]
    assert synthetic[synthetic.index("--rows") - 1] != "--figure"


def test_an_unavailable_or_changed_dataset_is_named_with_short_digests(tmp_path):
    archived = tmp_path / "arch"
    archived.mkdir()
    (tmp_path / "data").mkdir()
    data = tmp_path / "data" / "cardio.csv"
    data.write_bytes(b"x")
    record = {"dataset": {"sha256": "ab" * 32}}
    (archived / "run_benchmark_cardio.json").write_text(json.dumps(record))
    found = hashlib.sha256(b"x").hexdigest()
    message = reproduce.check_input("cardio", tmp_path, archived)
    assert (
        message
        == f"dataset data/cardio.csv differs from the archived run ({found[:12]} != {'ab' * 6})"
    )
    data.unlink()
    assert (
        reproduce.check_input("cardio", tmp_path, archived)
        == "dataset data/cardio.csv is not available on this machine"
    )
    assert reproduce.check_input("synthetic", tmp_path, archived) is None
    data.write_bytes(b"x")
    record["dataset"]["sha256"] = found
    (archived / "run_benchmark_cardio.json").write_text(json.dumps(record))
    assert reproduce.check_input("cardio", tmp_path, archived) is None


def _files(tmp_path, name, table, splits):
    directory = tmp_path / name
    directory.mkdir()
    return {
        "table": _csv(directory / "t.csv", 0.5, 0.25),
        "splits": None if splits is None else _write(directory / "s.gz", splits),
    }


def _write(path, content):
    path.write_bytes(content)
    return path


def test_equal_members_with_other_bytes_are_the_same_partitions_and_damaged_archives_are_not(
    tmp_path,
):
    a = _write(tmp_path / "a.gz", gzip.compress(b'["x", "y"]', mtime=1))
    b = _write(tmp_path / "b.gz", gzip.compress(b'["x", "y"]', mtime=2))
    assert reproduce._same_partitions(a, a) == (True, True)
    assert reproduce._same_partitions(a, b) == (True, False)
    other = _write(tmp_path / "c.gz", gzip.compress(b'["x"]'))
    assert reproduce._same_partitions(a, other) == (False, False)
    broken = _write(tmp_path / "d.gz", b"not gzip")
    assert reproduce._same_partitions(a, broken) == (False, False)
    assert reproduce._same_partitions(broken, a) == (False, False)


def test_a_level_reports_the_artifact_fields_for_each_split_situation(tmp_path):
    none_ref = reproduce._level(_files(tmp_path, "a", 1, b"s"), _files(tmp_path, "b", 1, None))
    assert none_ref["status"] == "PASS" and none_ref["artifact_identical"] is None
    assert none_ref["artifact_bytes_identical"] is None
    missing = reproduce._level(_files(tmp_path, "c", 1, None), _files(tmp_path, "d", 1, b"s"))
    assert missing["status"] == "FAIL"
    assert missing["artifact_identical"] is False and missing["artifact_bytes_identical"] is False
    same = reproduce._level(_files(tmp_path, "e", 1, b"s"), _files(tmp_path, "f", 1, b"s"))
    assert same["status"] == "PASS" and same["artifact_identical"] is True
    assert same["artifact_bytes_identical"] is True and same["kind"] == "NUMERICAL"


def test_a_statistical_agreement_passes_and_a_different_table_fails_even_with_same_splits(tmp_path):
    ref = _files(tmp_path, "r", 1, b"s")
    near = {"table": _csv(tmp_path / "n.csv", 0.6, 0.0), "splits": ref["splits"]}
    assert reproduce._level(near, ref)["status"] == "PASS"
    far = {"table": _csv(tmp_path / "f.csv", 0.9, 0.0), "splits": ref["splits"]}
    assert reproduce._level(far, ref)["status"] == "FAIL"


def test_the_outcome_names_each_unmet_level_and_the_worst_one_wins():
    assert reproduce.judge({"archive": {"status": "PASS"}}) == ("PASS", [])
    assert reproduce.judge({"version_sensitivity": {"status": "MEASURED"}}) == (
        "INCOMPLETE",
        ["no mandatory level was requested"],
    )
    report = {
        "archive": {"status": "FAIL", "kind": "DIFFERENT"},
        "same_environment": {"status": "NOT_RUN", "reason": "no data"},
        "locked_environment": {"status": "FAIL"},
    }
    assert reproduce.judge(report) == (
        "FAIL",
        [
            "archive is FAIL: DIFFERENT",
            "same_environment is NOT_RUN: no data",
            "locked_environment is FAIL",
        ],
    )
    assert reproduce.judge({"archive": {"status": "NOT_RUN", "reason": "r"}}) == (
        "INCOMPLETE",
        ["archive is NOT_RUN: r"],
    )
    assert (
        reproduce.judge({"archive": {"status": "PASS"}, "same_environment": {"status": "PASS"}})[0]
        == "PASS"
    )


def test_each_dataset_has_its_own_default_report_name():
    results = reproduce.ROOT / "experiments" / "results"
    assert reproduce.default_output("cardio") == results / "reproducibility.json"
    assert (
        reproduce.default_output("water_quality") == results / "reproducibility_water_quality.json"
    )


def _spy(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, **kw: calls.append((command, kw)))
    return calls


def test_a_conda_environment_is_created_from_the_explicit_lock_then_completed_with_pip(
    tmp_path, monkeypatch
):
    lock = tmp_path / "lock.txt"
    monkeypatch.setattr(
        reproduce, "lock_strategy", lambda: {"strategy": "conda-explicit", "path": lock}
    )
    calls = _spy(monkeypatch)
    prefix = tmp_path / "env"
    python = reproduce.build_environment(prefix, ["pkg==1"])
    assert python == str(prefix / "bin" / "python")
    expected = {"check": True, "capture_output": True, "text": True, "timeout": 1800}
    assert [c for c, _ in calls] == [
        ["conda", "create", "-y", "-p", str(prefix), "--file", str(lock)],
        [
            python,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "-q",
            "-r",
            str(reproduce.LOCK / "pip-freeze.txt"),
        ],
        [python, "-m", "pip", "install", "--no-deps", "-q", "pkg==1"],
    ]
    assert all(kw == expected for _, kw in calls)


def test_a_linux_virtual_environment_installs_the_hashed_lock_and_extra_pins(tmp_path, monkeypatch):
    lock = tmp_path / "lock.txt"
    monkeypatch.setattr(
        reproduce, "lock_strategy", lambda: {"strategy": "pip-hashes", "path": lock}
    )
    major, minor = (int(p) for p in lock_environment.LINUX_PYTHON.split("."))
    monkeypatch.setattr(reproduce.sys, "version_info", (major, minor, 0))
    calls = _spy(monkeypatch)
    prefix = tmp_path / "env"
    python = reproduce.build_environment(prefix)
    assert [c for c, _ in calls] == [
        [sys.executable, "-m", "venv", str(prefix)],
        [python, "-m", "pip", "install", "--no-deps", "-q", "--require-hashes", "-r", str(lock)],
    ]
    assert all(kw["check"] is True and kw["timeout"] == 1800 for _, kw in calls)
    wrong = (major, minor + 1, 0)
    monkeypatch.setattr(reproduce.sys, "version_info", wrong)
    with pytest.raises(RuntimeError) as refused:
        reproduce.build_environment(prefix)
    assert str(refused.value) == f"the Linux lock is for Python {lock_environment.LINUX_PYTHON}"


def test_a_platform_without_a_recorded_lock_cannot_rebuild(monkeypatch):
    monkeypatch.setattr(reproduce, "lock_strategy", lambda: None)
    monkeypatch.setattr(reproduce.platform, "system", lambda: "Plan9")
    monkeypatch.setattr(reproduce.platform, "machine", lambda: "z80")
    with pytest.raises(RuntimeError) as refused:
        reproduce.build_environment(Path("x"))
    assert str(refused.value) == "no recorded lock for Plan9 z80"


def test_the_lock_strategy_names_its_file_and_digest_for_conda_and_for_linux(tmp_path, monkeypatch):
    monkeypatch.setattr(reproduce, "LOCK", tmp_path)
    monkeypatch.setattr(reproduce.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(reproduce.platform, "machine", lambda: "arm64")
    assert reproduce.lock_strategy() is None
    conda = tmp_path / "conda-darwin-arm64.explicit.txt"
    conda.write_bytes(b"lock")
    found = reproduce.lock_strategy()
    assert found == {
        "strategy": "conda-explicit",
        "file": "verification/environment/conda-darwin-arm64.explicit.txt",
        "sha256": hashlib.sha256(b"lock").hexdigest(),
        "path": conda,
    }
    conda.unlink()
    monkeypatch.setattr(reproduce.platform, "system", lambda: "Linux")
    monkeypatch.setattr(reproduce.platform, "machine", lambda: "x86_64")
    (tmp_path / lock_environment.LINUX_LOCK).write_bytes(b"pip")
    linux = reproduce.lock_strategy()
    assert linux["strategy"] == "pip-hashes" and linux["file"].endswith(lock_environment.LINUX_LOCK)
    assert linux["sha256"] == hashlib.sha256(b"pip").hexdigest()


def _stub_main(monkeypatch, tmp_path, outcome_levels=None):
    seen = {}
    levels = outcome_levels or {"archive": {"status": "PASS", "kind": "NUMERICAL"}}
    monkeypatch.setattr(
        reproduce,
        "reproduce",
        lambda lv, wd, pin, ds: seen.update(args=(lv, wd, pin, ds)) or levels,
    )
    monkeypatch.setattr(evidence_schema, "collect_source", lambda: {"revision": "r"})
    monkeypatch.setattr(evidence_schema, "collect_environment", lambda: {"python": "p"})
    monkeypatch.setattr(
        reproduce,
        "lock_strategy",
        lambda: {"strategy": "s", "file": "f", "sha256": "h", "path": Path("x")},
    )
    return seen


def test_the_report_records_what_was_replayed_against_which_archived_run(
    tmp_path, monkeypatch, capsys
):
    seen = _stub_main(monkeypatch, tmp_path)
    out = tmp_path / "new" / "r.json"
    assert reproduce.main(["--output", str(out), "--workdir", str(tmp_path / "w")]) == 0
    assert seen["args"] == (
        ["archive", "same_environment"],
        tmp_path / "w",
        "scikit-learn==1.8.0",
        "cardio",
    )
    text = out.read_text()
    document = json.loads(text)
    assert text == json.dumps(document, indent=2, sort_keys=True) + "\n"
    record = reproduce._archived_record("cardio")
    assert (
        document["schema_version"] == 1
        and document["outcome"] == "PASS"
        and document["reasons"] == []
    )
    assert document["dataset"] == "cardio" and document["seeds"] == record["seeds"]
    assert document["lock"] == {"strategy": "s", "file": "f", "sha256": "h"}
    assert document["source"] == {"revision": "r"} and document["environment"] == {"python": "p"}
    assert document["tolerance"] == reproduce.TOLERANCE and document["levels"] == {
        "archive": {"status": "PASS", "kind": "NUMERICAL"}
    }
    archived = document["archived_run"]
    assert archived["file"] == "verification/evidence/run_benchmark_cardio.json"
    assert archived["source_revision"] == record["source_revision"]
    assert archived["dataset_sha256"] == record["dataset"].get("sha256")
    splits = reproduce.ARCHIVED / "split_ids_cardio.json.gz"
    assert archived["split_ids_sha256"] == hashlib.sha256(splits.read_bytes()).hexdigest()
    assert capsys.readouterr().out == "archive: PASS NUMERICAL\noutcome: PASS\n"
    assert document["captured_at"].endswith("+00:00")


def test_a_run_without_a_recorded_lock_and_a_failing_level_are_reported_and_exit_one(
    tmp_path, monkeypatch, capsys
):
    levels = {
        "archive": {"status": "FAIL", "kind": "DIFFERENT"},
        "same_environment": {"status": "NOT_RUN", "reason": "r"},
    }
    _stub_main(monkeypatch, tmp_path, levels)
    monkeypatch.setattr(reproduce, "lock_strategy", lambda: None)
    out = tmp_path / "r.json"
    assert reproduce.main(["--dataset", "synthetic", "--output", str(out)]) == 1
    document = json.loads(out.read_text())
    assert (
        document["lock"] == {"strategy": "none"}
        and document["archived_run"]["split_ids_sha256"] is None
    )
    assert capsys.readouterr().out.splitlines() == [
        "archive: FAIL DIFFERENT",
        "same_environment: NOT_RUN r",
        "outcome: FAIL",
        "  - archive is FAIL: DIFFERENT",
        "  - same_environment is NOT_RUN: r",
    ]


def test_the_options_choose_dataset_levels_and_pin_and_the_workdir_defaults_to_a_temp_folder(
    tmp_path, monkeypatch
):
    seen = _stub_main(monkeypatch, tmp_path)
    made = []
    monkeypatch.setattr(
        reproduce.tempfile, "mkdtemp", lambda prefix: made.append(prefix) or str(tmp_path / "t")
    )
    argv = [
        "--dataset",
        "water_quality",
        "--levels",
        "archive",
        "locked_environment",
        "--sensitivity-pin",
        "x==1",
    ]
    assert reproduce.main([*argv, "--output", str(tmp_path / "o.json")]) == 0
    assert seen["args"] == (
        ["archive", "locked_environment"],
        tmp_path / "t",
        "x==1",
        "water_quality",
    )
    assert made == ["repro-"]
    with pytest.raises(SystemExit) as stop:
        reproduce.main(["--dataset", "nope"])
    assert stop.value.code == 2
    with pytest.raises(SystemExit) as stop:
        reproduce.main(["--levels", "other"])
    assert stop.value.code == 2
