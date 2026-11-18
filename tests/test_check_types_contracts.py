"""How the typing gate builds its mypy command, writes its report and words its verdicts."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from verification import check_types as ct


class _Done:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_mypy_runs_from_the_repository_root_with_the_documented_options(monkeypatch):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return _Done(1, "out")

    monkeypatch.setattr(subprocess, "run", run)
    assert ct.run_mypy(["python", "-m", "mypy"]) == "out"
    assert seen["command"] == [
        "python", "-m", "mypy", "--python-executable", sys.executable,
        "--ignore-missing-imports", "--explicit-package-bases", "--no-error-summary",
        *ct.TARGETS,
    ]  # fmt: skip
    assert seen["cwd"] == ct.ROOT and seen["capture_output"] is True
    assert seen["text"] is True and seen["check"] is False
    assert seen["env"]["MYPYPATH"].split(":" if ":" in seen["env"]["MYPYPATH"] else ";") == [
        "src", "experiments", ".",
    ]  # fmt: skip


def test_a_mypy_crash_is_reported_with_its_message_not_as_a_result(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Done(2, "stdout text", "boom "))
    with pytest.raises(RuntimeError, match=r"^mypy did not run: boom$"):
        ct.run_mypy(["mypy"])
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Done(2, " only stdout ", ""))
    with pytest.raises(RuntimeError, match=r"^mypy did not run: only stdout$"):
        ct.run_mypy(["mypy"])


def test_only_errors_under_verification_are_never_baselined():
    found = {"verification/a.py: bad", "src/b.py: bad", "experiments/verification/c.py: bad"}
    problems = ct.judge(found, {"src/b.py: bad", "experiments/verification/c.py: bad"})
    assert problems == ["error in verification/ cannot be baselined: verification/a.py: bad"]
    assert ct.judge({"VERIFICATION/x.py: bad"}, {"VERIFICATION/x.py: bad"}) == []
    assert ct.judge({"src/new.py: bad"}, set()) == ["new typing error: src/new.py: bad"]
    assert ct.judge(set(), {"src/gone.py: bad"}) == [
        "baseline entry no longer occurs: src/gone.py: bad"
    ]


def test_the_report_is_sorted_two_space_indented_pinned_and_written_under_new_directories(tmp_path):
    target = tmp_path / "new" / "dir" / "report.json"
    ct._write_report(target, status="PASS", errors=0)
    text = target.read_text()
    document = {"status": "PASS", "errors": 0, **ct._pins()}
    assert text == json.dumps(document, indent=2, sort_keys=True) + "\n"
    ct._write_report(target, status="FAIL")
    assert json.loads(target.read_text())["status"] == "FAIL"
    ct._write_report(None, status="ignored")


def _gate(monkeypatch, tmp_path, output, baseline_text="src/a.py: old\n"):
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(baseline_text)
    monkeypatch.setattr(ct, "run_mypy", lambda mypy: output)
    return baseline


def test_a_passing_run_prints_pass_with_the_count_and_exit_zero(monkeypatch, tmp_path, capsys):
    baseline = _gate(monkeypatch, tmp_path, "src/a.py:3: error: old\n")
    report = tmp_path / "r.json"
    code = ct.main(["--baseline", str(baseline), "--output", str(report)])
    assert code == 0
    assert capsys.readouterr().out == "typing: PASS (1 known errors in the baseline)\n"
    saved = json.loads(report.read_text())
    assert saved["status"] == "PASS" and saved["errors"] == 1 and saved["baseline_entries"] == 1
    assert saved["problems"] == []


def test_a_failing_run_lists_each_problem_then_fail_and_exit_one(monkeypatch, tmp_path, capsys):
    baseline = _gate(monkeypatch, tmp_path, "src/new.py:1: error: fresh\n")
    assert ct.main(["--baseline", str(baseline)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "typing: new typing error: src/new.py: fresh",
        "typing: baseline entry no longer occurs: src/a.py: old",
        "typing: FAIL (1 known errors in the baseline)",
    ]


def test_a_run_that_cannot_complete_is_incomplete_in_the_report_and_on_screen(
    monkeypatch, tmp_path, capsys
):
    def crash(mypy):
        raise RuntimeError("no mypy")

    monkeypatch.setattr(ct, "run_mypy", crash)
    report = tmp_path / "r.json"
    assert ct.main(["--output", str(report), "--baseline", str(tmp_path / "b")]) == 1
    assert capsys.readouterr().out == "typing: INCOMPLETE (no mypy)\n"
    saved = json.loads(report.read_text())
    assert saved["status"] == "INCOMPLETE" and saved["reason"] == "no mypy"
    assert saved["problems"] == []


def test_the_mypy_command_defaults_to_mypy_and_the_baseline_to_the_repository_file(monkeypatch):
    seen = {}
    monkeypatch.setattr(ct, "run_mypy", lambda mypy: seen.setdefault("mypy", mypy) and "")
    monkeypatch.setattr(Path, "read_text", lambda self: seen.setdefault("baseline", self) and "")
    assert ct.main([]) == 0
    assert seen["mypy"] == ["mypy"] and seen["baseline"] == ct.BASELINE
    seen.clear()
    ct.main(["--mypy", "python", "mypy"])
    assert seen["mypy"] == ["python", "mypy"]


def test_the_help_text_names_each_option(capsys):
    with pytest.raises(SystemExit):
        ct.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    for phrase in (
        "Static typing gate",
        "mypy command",
        "write a machine-readable report here",
        "record the current errors of the scientific code (never those of verification/)",
    ):
        assert phrase in text


def test_a_baseline_with_a_verification_error_is_refused_and_a_clean_one_is_written(
    monkeypatch, tmp_path, capsys
):
    target = tmp_path / "base.txt"
    monkeypatch.setattr(ct, "run_mypy", lambda mypy: "verification/a.py:1: error: bad\n")
    assert ct.main(["--write-baseline", "--baseline", str(target)]) == 1
    assert "typing: error in verification/ cannot be baselined: verification/a.py: bad" in (
        capsys.readouterr().out
    )
    assert not target.exists()
    monkeypatch.setattr(ct, "run_mypy", lambda mypy: "src/b.py:2: error: x\nsrc/a.py:1: error: y\n")
    assert ct.main(["--write-baseline", "--baseline", str(target)]) == 0
    assert target.read_text() == "src/a.py: y\nsrc/b.py: x\n"
    assert capsys.readouterr().out == f"typing: wrote 2 entries to {target}\n"
