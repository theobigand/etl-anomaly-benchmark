"""Machine-readable verification evidence from pytest and coverage artifacts."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from xml.etree import ElementTree

_COUNTS = {
    "line": ("covered_lines", "num_statements"),
    "branch": ("covered_branches", "num_branches"),
}


def _metric(summary: dict, kind: str) -> dict[str, int]:
    covered, coverable = _COUNTS[kind]
    return {"covered": int(summary[covered]), "coverable": int(summary[coverable])}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def build_report(coverage_path: Path, junit_path: Path) -> dict:
    """Reject absent, malformed or empty artifacts rather than issuing a pass."""
    if not coverage_path.is_file() or not junit_path.is_file():
        raise ValueError("missing coverage or test evidence")
    try:
        coverage = json.loads(coverage_path.read_text())
        root = ElementTree.parse(junit_path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        tests = {
            key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
        line = _metric(coverage["totals"], "line")
        branch = _metric(coverage["totals"], "branch")
    except (OSError, ValueError, KeyError, ElementTree.ParseError) as exc:
        raise ValueError("malformed verification evidence") from exc
    if tests["tests"] <= 0:
        raise ValueError("zero tests executed")
    if line["coverable"] <= 0 or branch["coverable"] <= 0:
        raise ValueError("zero instrumented production lines or branches")
    status = (
        "PASS"
        if tests["failures"] == tests["errors"] == tests["skipped"] == 0
        and all(metric["covered"] == metric["coverable"] for metric in (line, branch))
        else "FAIL"
    )
    try:
        revision = _git("rev-parse", "HEAD")
        dirty = bool(_git("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    packages = {}
    for package in ("pytest", "pytest-cov", "numpy", "pandas", "scikit-learn", "pyod"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    return {
        "schema_version": 1,
        "status": status,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_revision": revision,
        "dirty": dirty,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "packages": packages,
        "tests": {
            "total": tests["tests"],
            "failures": tests["failures"],
            "errors": tests["errors"],
            "skipped": tests["skipped"],
        },
        "coverage": {
            "line": line,
            "branch": branch,
            "per_file": {
                name: {
                    "line": _metric(data["summary"], "line"),
                    "branch": _metric(data["summary"], "branch"),
                }
                for name, data in coverage.get("files", {}).items()
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.coverage, args.junit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"verification: {report['status']} ({report['tests']['total']} tests)")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
