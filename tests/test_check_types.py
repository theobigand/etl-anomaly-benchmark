"""The typing gate parses mypy output, forbids new errors and shrinks only."""

import stat
import sys
from pathlib import Path

from verification import check_types

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    "src/a.py:10: error: Bad thing  [attr-defined]\n"
    "src/a.py:20: note: ignored note\n"
    "src/a.py:30: error: Bad thing  [attr-defined]\n"
    "verification/t.py:3: error: Worse thing  [misc]\n"
    "Success: nothing\n"
)


def test_parse_keeps_one_key_per_message_without_line_numbers():
    assert check_types.parse(OUTPUT) == {
        "src/a.py: Bad thing  [attr-defined]",
        "verification/t.py: Worse thing  [misc]",
    }


def test_known_errors_pass_but_a_new_one_fails():
    baseline = {"src/a.py: Bad thing  [attr-defined]"}
    assert check_types.judge({"src/a.py: Bad thing  [attr-defined]"}, baseline) == []
    problems = check_types.judge({"src/a.py: Bad thing  [attr-defined]", "src/b.py: New"}, baseline)
    assert problems == ["new typing error: src/b.py: New"]


def test_a_fixed_error_must_leave_the_baseline():
    problems = check_types.judge(set(), {"src/a.py: Old"})
    assert problems == ["baseline entry no longer occurs: src/a.py: Old"]


def test_errors_in_the_verifier_code_cannot_be_baselined():
    key = "verification/t.py: Worse thing  [misc]"
    problems = check_types.judge({key}, {key})
    assert problems == [f"error in verification/ cannot be baselined: {key}"]


def _fake_mypy(tmp_path, body, code=1):
    path = tmp_path / "mypy"
    path.write_text(f"#!/bin/sh\ncat <<'EOF'\n{body}EOF\nexit {code}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_command_passes_on_the_baseline_and_fails_on_a_regression(tmp_path, capsys):
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("src/a.py: Bad thing  [attr-defined]\n")
    clean = _fake_mypy(tmp_path, "src/a.py:1: error: Bad thing  [attr-defined]\n")
    assert check_types.main(["--mypy", clean, "--baseline", str(baseline)]) == 0
    assert "typing: PASS (1 known errors in the baseline)" in capsys.readouterr().out
    worse = _fake_mypy(
        tmp_path, "src/a.py:1: error: Bad thing  [attr-defined]\nsrc/b.py:1: error: New\n"
    )
    assert check_types.main(["--mypy", worse, "--baseline", str(baseline)]) == 1
    assert "typing: new typing error: src/b.py: New" in capsys.readouterr().out


def test_a_mypy_crash_or_missing_baseline_is_incomplete_not_a_pass(tmp_path, capsys):
    crash = tmp_path / "crash"
    crash.write_text("#!/bin/sh\necho broken >&2\nexit 2\n")
    crash.chmod(crash.stat().st_mode | stat.S_IEXEC)
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("")
    assert check_types.main(["--mypy", str(crash), "--baseline", str(baseline)]) == 1
    assert "typing: INCOMPLETE (mypy did not run: broken)" in capsys.readouterr().out
    ok = _fake_mypy(tmp_path, "", code=0)
    assert check_types.main(["--mypy", ok, "--baseline", str(tmp_path / "none.txt")]) == 1
    assert "INCOMPLETE" in capsys.readouterr().out


def test_the_committed_baseline_has_no_verifier_entries_and_no_line_numbers():
    lines = (ROOT / "verification" / "typing_baseline.txt").read_text().splitlines()
    assert lines == sorted(lines) and len(lines) == len(set(lines))
    assert not any(line.startswith("verification/") for line in lines)
    assert not any(line.split(":")[1].strip().isdigit() for line in lines)


def test_the_module_prints_usage():
    import subprocess

    done = subprocess.run(
        [sys.executable, "-m", "verification.check_types", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and "usage:" in done.stdout


def test_the_real_mypy_command_line_carries_the_project_scope(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"], seen["env"] = command, kwargs["env"]
        import subprocess

        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(check_types.subprocess, "run", fake_run)
    assert check_types.run_mypy(["mypy"]) == ""
    assert seen["command"][-3:] == ["src/etl_benchmark", "experiments", "verification"]
    assert seen["env"]["MYPYPATH"].split(":") == ["src", "experiments", "."]


def test_write_baseline_records_scientific_errors_only_and_sorts_them(tmp_path, capsys):
    baseline = tmp_path / "baseline.txt"
    out = "src/b.py:2: error: Two\nsrc/a.py:9: error: One\nsrc/a.py:3: error: One\n"
    mypy = _fake_mypy(tmp_path, out)
    assert check_types.main(["--mypy", mypy, "--baseline", str(baseline), "--write-baseline"]) == 0
    assert baseline.read_text() == "src/a.py: One\nsrc/b.py: Two\n"
    assert "wrote 2 entries" in capsys.readouterr().out
    assert check_types.main(["--mypy", mypy, "--baseline", str(baseline)]) == 0


def test_write_baseline_refuses_verifier_errors_and_leaves_the_file_alone(tmp_path, capsys):
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("src/a.py: Old\n")
    mypy = _fake_mypy(tmp_path, "verification/t.py:1: error: Bad\n")
    assert check_types.main(["--mypy", mypy, "--baseline", str(baseline), "--write-baseline"]) == 1
    assert baseline.read_text() == "src/a.py: Old\n"
    assert "cannot be baselined: verification/t.py: Bad" in capsys.readouterr().out


def test_write_baseline_reports_a_mypy_crash_as_incomplete(tmp_path, capsys):
    crash = tmp_path / "crash"
    crash.write_text("#!/bin/sh\nexit 2\n")
    crash.chmod(crash.stat().st_mode | stat.S_IEXEC)
    baseline = tmp_path / "baseline.txt"
    args = ["--mypy", str(crash), "--baseline", str(baseline), "--write-baseline"]
    assert check_types.main(args) == 1
    assert "INCOMPLETE" in capsys.readouterr().out and not baseline.exists()


def test_the_command_writes_a_machine_readable_report(tmp_path):
    import json

    baseline = tmp_path / "baseline.txt"
    baseline.write_text("src/a.py: Bad thing  [attr-defined]\n")
    report = tmp_path / "types.json"
    worse = _fake_mypy(
        tmp_path, "src/a.py:1: error: Bad thing  [attr-defined]\nsrc/b.py:1: error: New\n"
    )
    assert (
        check_types.main(["--mypy", worse, "--baseline", str(baseline), "--output", str(report)])
        == 1
    )
    written = json.loads(report.read_text())
    assert (
        written["status"] == "FAIL" and written["errors"] == 2 and written["baseline_entries"] == 1
    )
    assert written["problems"] == ["new typing error: src/b.py: New"]
    clean = _fake_mypy(tmp_path, "src/a.py:1: error: Bad thing  [attr-defined]\n")
    assert (
        check_types.main(["--mypy", clean, "--baseline", str(baseline), "--output", str(report)])
        == 0
    )
    written = json.loads(report.read_text())
    assert written["status"] == "PASS" and written["problems"] == []


def test_the_report_marks_an_unrunnable_check_incomplete(tmp_path):
    import json

    report = tmp_path / "types.json"
    ok = _fake_mypy(tmp_path, "", code=0)
    missing = str(tmp_path / "none.txt")
    assert check_types.main(["--mypy", ok, "--baseline", missing, "--output", str(report)]) == 1
    written = json.loads(report.read_text())
    assert written["status"] == "INCOMPLETE" and written["reason"]
