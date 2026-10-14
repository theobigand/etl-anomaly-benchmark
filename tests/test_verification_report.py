import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import verification_report  # noqa: E402


def test_report_rejects_missing_and_empty_test_evidence(tmp_path):
    coverage = tmp_path / "coverage.json"
    junit = tmp_path / "junit.xml"
    with pytest.raises(ValueError, match="missing"):
        verification_report.build_report(coverage, junit)
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 1,
                    "num_statements": 2,
                    "covered_branches": 0,
                    "num_branches": 1,
                }
            }
        )
    )
    junit.write_text('<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
    with pytest.raises(ValueError, match="zero"):
        verification_report.build_report(coverage, junit)


def test_report_keeps_exact_denominators_and_failure_state(tmp_path):
    coverage = tmp_path / "coverage.json"
    junit = tmp_path / "junit.xml"
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 7,
                    "num_statements": 10,
                    "covered_branches": 3,
                    "num_branches": 5,
                },
                "files": {
                    "src/a.py": {
                        "summary": {
                            "covered_lines": 7,
                            "num_statements": 10,
                            "covered_branches": 3,
                            "num_branches": 5,
                        }
                    }
                },
            }
        )
    )
    junit.write_text('<testsuite tests="2" failures="1" errors="0" skipped="0"/>')
    report = verification_report.build_report(coverage, junit)
    assert report["status"] == "FAIL"
    assert report["tests"] == {"total": 2, "failures": 1, "errors": 0, "skipped": 0}
    assert report["coverage"]["line"] == {"covered": 7, "coverable": 10}
    assert report["coverage"]["branch"] == {"covered": 3, "coverable": 5}


def test_report_command_emits_pass_only_for_complete_evidence(tmp_path, monkeypatch):
    coverage = tmp_path / "coverage.json"
    junit = tmp_path / "junit.xml"
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verification_report",
            "--coverage",
            str(coverage),
            "--junit",
            str(junit),
            "--output",
            str(output),
        ],
    )
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 2,
                    "num_statements": 2,
                    "covered_branches": 1,
                    "num_branches": 1,
                }
            }
        )
    )
    junit.write_text('<testsuite tests="2" failures="0" errors="0" skipped="0"/>')
    assert verification_report.main() == 0
    assert json.loads(output.read_text())["status"] == "PASS"

    junit.write_text('<testsuite tests="2" failures="0" errors="0" skipped="1"/>')
    assert verification_report.main() == 1
    assert json.loads(output.read_text())["status"] == "FAIL"


def test_report_rejects_malformed_and_uninstrumented_evidence(tmp_path):
    coverage = tmp_path / "coverage.json"
    junit = tmp_path / "junit.xml"
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"/>')
    coverage.write_text("not json")
    with pytest.raises(ValueError, match="malformed"):
        verification_report.build_report(coverage, junit)
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 0,
                    "num_statements": 0,
                    "covered_branches": 0,
                    "num_branches": 0,
                }
            }
        )
    )
    with pytest.raises(ValueError, match="zero instrumented"):
        verification_report.build_report(coverage, junit)


def test_report_records_missing_git_and_package_metadata(tmp_path, monkeypatch):
    coverage = tmp_path / "coverage.json"
    junit = tmp_path / "junit.xml"
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 1,
                    "num_statements": 1,
                    "covered_branches": 1,
                    "num_branches": 1,
                }
            }
        )
    )
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"/>')

    def unavailable_git(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(verification_report.subprocess, "check_output", unavailable_git)
    original = verification_report.version

    def version_or_missing(name):
        if name == "pyod":
            raise PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(verification_report, "version", version_or_missing)
    report = verification_report.build_report(coverage, junit)
    assert report["status"] == "PASS"
    assert report["source_revision"] is None
    assert report["dirty"] is None
    assert report["packages"]["pyod"] is None


def test_report_command_main_guard_preserves_failure_exit(tmp_path):
    coverage = tmp_path / "coverage.json"
    junit = tmp_path / "junit.xml"
    output = tmp_path / "report.json"
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 0,
                    "num_statements": 1,
                    "covered_branches": 0,
                    "num_branches": 1,
                }
            }
        )
    )
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"/>')
    command = subprocess.run(
        [
            sys.executable,
            str(Path(verification_report.__file__)),
            "--coverage",
            str(coverage),
            "--junit",
            str(junit),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert command.returncode == 1
    assert json.loads(output.read_text())["status"] == "FAIL"
