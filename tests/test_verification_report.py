import json
import sys
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
