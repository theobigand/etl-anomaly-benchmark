"""What each reproduction level runs, in which folder, and how one failing level is reported."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from verification import reproduce

LEVEL = {"status": "PASS", "kind": "NUMERICAL"}


def _spy_subprocess(monkeypatch, *, code=0, stderr="", create=True):
    seen = {}

    def run(command, **kwargs):
        seen["command"], seen["kwargs"] = command, kwargs
        results = Path(command[command.index("--results-dir") + 1])
        if create:
            (results / "benchmark_cardio_1.csv").write_text("x")
            (results / "split_ids_cardio_1.json.gz").write_text("x")
        return subprocess.CompletedProcess(command, code, stdout="", stderr=stderr)

    monkeypatch.setattr(reproduce.subprocess, "run", run)
    return seen


def test_a_replay_is_run_from_the_repository_with_the_source_path_and_its_own_folders(
    monkeypatch, tmp_path
):
    seen = _spy_subprocess(monkeypatch)
    results = tmp_path / "deep" / "first"
    out = reproduce.run_dataset("py", "cardio", results)
    assert results.is_dir()
    seeds = reproduce._archived_record("cardio")["seeds"]
    assert seen["command"] == [
        "py", "experiments/run_benchmark.py", "--dataset", "cardio",
        "--results-dir", str(results), "--seeds", *map(str, seeds),
    ]  # fmt: skip
    kwargs = seen["kwargs"]
    assert kwargs["cwd"] == reproduce.ROOT and kwargs["capture_output"] is True
    assert kwargs["text"] is True and kwargs["timeout"] == 7200 and kwargs["check"] is False
    assert kwargs["env"]["PYTHONPATH"] == str(reproduce.ROOT / "src")
    assert kwargs["env"]["PATH"] == os.environ["PATH"]
    assert out == {
        "table": results / "benchmark_cardio_1.csv",
        "splits": results / "split_ids_cardio_1.json.gz",
    }
    reproduce.run_dataset("py", "cardio", results)


def test_a_failed_replay_names_the_last_line_of_its_error(monkeypatch, tmp_path):
    _spy_subprocess(monkeypatch, code=2, stderr="first\nsecond\nlast\n")
    with pytest.raises(RuntimeError) as failed:
        reproduce.run_dataset("py", "cardio", tmp_path / "r")
    assert str(failed.value) == "benchmark failed: ['last']"


def test_a_replay_of_an_experiment_without_split_archive_has_no_splits(monkeypatch, tmp_path):

    def run(command, **kwargs):
        results = Path(command[command.index("--results-dir") + 1])
        name = reproduce.TARGETS["synthetic"]["table"].replace("*", "1")
        (results / name).write_text("x")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(reproduce.subprocess, "run", run)
    out = reproduce.run_dataset("py", "synthetic", tmp_path / "r")
    assert out["splits"] is None and out["table"].name == "synthetic_metrics_1.csv"


@pytest.fixture
def flow(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(reproduce, "check_input", lambda dataset: calls.append(("input", dataset)))

    def run_dataset(python, dataset, results):
        calls.append(("run", python, dataset, results))
        return {"table": results, "splits": None}

    def build_environment(prefix, extra=None):
        calls.append(("build", prefix, extra))
        return f"py-{prefix.name}"

    monkeypatch.setattr(reproduce, "run_dataset", run_dataset)
    monkeypatch.setattr(reproduce, "build_environment", build_environment)
    monkeypatch.setattr(reproduce, "_level", lambda candidate, reference: dict(LEVEL))
    return calls


def test_every_level_runs_in_its_own_folder_with_its_own_interpreter(flow, tmp_path):
    work = tmp_path / "w"
    report = reproduce.reproduce(list(reproduce.LEVELS), work, "pkg==1", "cardio")
    assert flow == [
        ("input", "cardio"),
        ("run", sys.executable, "cardio", work / "first"),
        ("run", sys.executable, "cardio", work / "second"),
        ("build", work / "locked", None),
        ("run", "py-locked", "cardio", work / "locked_run"),
        ("build", work / "changed", ["pkg==1"]),
        ("run", "py-changed", "cardio", work / "changed_run"),
    ]
    assert list(report) == list(reproduce.LEVELS)
    assert report["version_sensitivity"]["status"] == "MEASURED"
    assert report["version_sensitivity"]["changed"] == "pkg==1"
    assert {name: level["required"] for name, level in report.items()} == {
        "archive": True,
        "same_environment": True,
        "locked_environment": True,
        "version_sensitivity": False,
    }


def test_an_unavailable_input_runs_nothing_and_marks_each_level_required_or_not(
    monkeypatch, tmp_path
):
    seen = []
    monkeypatch.setattr(reproduce, "check_input", lambda dataset: seen.append(dataset) or "no data")
    monkeypatch.setattr(reproduce, "run_dataset", lambda *a: pytest.fail("nothing may run"))
    report = reproduce.reproduce(list(reproduce.LEVELS), tmp_path, "pkg==1", "water_quality")
    assert seen == ["water_quality"]
    assert report == {
        "archive": {"status": "NOT_RUN", "reason": "no data", "required": True},
        "same_environment": {"status": "NOT_RUN", "reason": "no data", "required": True},
        "locked_environment": {"status": "NOT_RUN", "reason": "no data", "required": True},
        "version_sensitivity": {"status": "NOT_RUN", "reason": "no data", "required": False},
    }


def test_a_failed_reference_run_fails_every_requested_level_with_its_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(reproduce, "check_input", lambda dataset: None)

    def boom(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(reproduce, "run_dataset", boom)
    report = reproduce.reproduce(["archive", "same_environment"], tmp_path, "p==1")
    assert report == {
        "archive": {"status": "FAIL", "reason": "the reference run failed: boom", "required": True},
        "same_environment": {
            "status": "FAIL",
            "reason": "the reference run failed: boom",
            "required": True,
        },
    }


def test_a_failing_later_level_is_reported_without_losing_the_earlier_ones(
    flow, monkeypatch, tmp_path
):
    def build(prefix, extra=None):
        raise RuntimeError("no lock")

    monkeypatch.setattr(reproduce, "build_environment", build)
    report = reproduce.reproduce(
        ["archive", "locked_environment", "version_sensitivity"], tmp_path, "p==1"
    )
    assert report["archive"]["status"] == "PASS"
    assert report["locked_environment"] == {
        "status": "NOT_RUN",
        "reason": "environment could not be rebuilt: no lock",
        "required": True,
    }
    assert report["version_sensitivity"] == {
        "status": "NOT_RUN",
        "reason": "changed environment failed: no lock",
        "required": False,
    }


def test_a_failing_second_run_is_a_failure_with_its_reason(flow, monkeypatch, tmp_path):
    real = reproduce.run_dataset

    def run(python, dataset, results):
        if results.name == "second":
            raise RuntimeError("second boom")
        return real(python, dataset, results)

    monkeypatch.setattr(reproduce, "run_dataset", run)
    report = reproduce.reproduce(["same_environment"], tmp_path, "p==1")
    assert report["same_environment"] == {
        "status": "FAIL",
        "reason": "the second run failed: second boom",
        "required": True,
    }


def test_the_report_file_is_made_in_a_new_folder_and_names_the_reason_of_a_level_without_a_kind(
    monkeypatch, tmp_path, capsys
):
    levels = {
        "archive": {"status": "PASS"},
        "same_environment": {"status": "NOT_RUN", "reason": "r"},
    }
    monkeypatch.setattr(reproduce, "reproduce", lambda *a: levels)
    monkeypatch.setattr(reproduce, "lock_strategy", lambda: None)
    seen = []
    monkeypatch.setattr(
        reproduce,
        "default_output",
        lambda dataset: seen.append(dataset) or tmp_path / "a" / "b" / "r.json",
    )
    assert reproduce.main(["--dataset", "water_quality"]) == 1
    assert seen == ["water_quality"]
    assert (tmp_path / "a" / "b" / "r.json").is_file()
    assert capsys.readouterr().out.splitlines()[:2] == [
        "archive: PASS ",
        "same_environment: NOT_RUN r",
    ]


def test_the_help_describes_the_reproduction_check(capsys):
    with pytest.raises(SystemExit):
        reproduce.main(["--help"])
    assert reproduce.__doc__.strip().splitlines()[0] in " ".join(capsys.readouterr().out.split())
