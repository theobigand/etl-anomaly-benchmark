"""One evidence envelope for the FAST, DEEP, FAULTS and REAL profiles.

An envelope records which source and environment produced a result, hashes the
raw artifacts behind it, and carries the result itself. ``validate`` never
trusts the stored status: it recomputes the status from the result and rejects
a PASS that the result does not support.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import check_mutation  # noqa: E402
import provenance  # noqa: E402
import verification_report  # noqa: E402
import verify_real  # noqa: E402

from verification import mutation_scope  # noqa: E402

SCHEMA_VERSION = 2
KINDS = ("fast", "deep", "faults", "real", "tools", "types", "reproduction")
STATUSES = ("PASS", "FAIL", "INCOMPLETE", "NOT_RUN")
OUTCOMES = check_mutation.OUTCOMES
# The datasets REAL must verify come from the gate itself, never from a report.
REQUIRED_DATASETS = verify_real.REQUIRED_DATASETS
PACKAGES = (
    "pytest",
    "pytest-cov",
    "mutmut",
    "numpy",
    "pandas",
    "scikit-learn",
    "pyod",
    "mypy",
    "pandas-stubs",
)
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_source(root: Path = ROOT) -> dict:
    """Revision, worktree state and recipe-2 fingerprint of the repository."""

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

    return {
        "revision": git("rev-parse", "HEAD"),
        "worktree_dirty": bool(git("status", "--porcelain")),
        "scientific_fingerprint": provenance.scientific_fingerprint(),
    }


def collect_environment() -> dict:
    packages: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }


def collect_execution(env=None) -> dict:
    """Where this process runs: locally, or on which kind of CI runner."""
    env = os.environ if env is None else env
    return {
        "ci": env.get("GITHUB_ACTIONS") == "true",
        "run_id": env.get("GITHUB_RUN_ID"),
        "runner_environment": env.get("RUNNER_ENVIRONMENT"),
        "runner_name": env.get("RUNNER_NAME"),
    }


def _envelope(kind, status, result, artifacts, root, source, environment, execution=None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "status": status,
        "captured_at": datetime.now(UTC).isoformat(),
        "source": copy.deepcopy(source) if source is not None else collect_source(),
        "environment": (
            copy.deepcopy(environment) if environment is not None else collect_environment()
        ),
        "execution": copy.deepcopy(execution) if execution is not None else collect_execution(),
        "artifacts": {
            str(path.resolve().relative_to(root.resolve())): _sha256(path)
            for path in artifacts
            if path.is_file()
        },
        "result": result,
    }


# --- status rules: the single definition used by builders and by validate ---


def _fast_status(result: dict) -> str:
    tests, line, branch = result["tests"], result["coverage"]["line"], result["coverage"]["branch"]
    clean = tests["total"] > 0 and tests["failures"] == tests["errors"] == tests["skipped"] == 0
    full = all(m["coverable"] > 0 and m["covered"] == m["coverable"] for m in (line, branch))
    return "PASS" if clean and full else "FAIL"


def _deep_status(result: dict) -> str:
    try:
        status, _ = check_mutation.classify(result["stats"])
    except ValueError:
        return "INCOMPLETE"
    if not result["scope"] or not result.get("scope_files"):
        return "INCOMPLETE"
    return status if isinstance(result.get("mutated_files"), list) else "INCOMPLETE"


def _faults_status(result: dict) -> str:
    faults = result["faults"]
    if {item["defect"] for item in faults} != set(result["expected"]) or not result["expected"]:
        return "INCOMPLETE"
    if len(faults) != len(result["expected"]):
        return "INCOMPLETE"
    ok = result["control_passed"] and all(item["detected"] for item in faults)
    return "PASS" if ok else "FAIL"


def _real_status(result: dict) -> str:
    required, datasets = result["required"], result["datasets"]
    if not required or sorted(required) != sorted(REQUIRED_DATASETS):
        return "FAIL"
    if sorted(item["dataset"] for item in datasets) != sorted(required):
        return "FAIL"
    states = {item["status"] for item in datasets}
    if states == {"PASS"}:
        return "PASS"
    return "NOT_RUN" if states <= {"PASS", "NOT_RUN"} else "FAIL"


def _tools_status(result: dict) -> str:
    line, branch = result["coverage"]["line"], result["coverage"]["branch"]
    full = all(m["coverable"] > 0 and m["covered"] == m["coverable"] for m in (line, branch))
    return "PASS" if full else "FAIL"


def _types_status(result: dict) -> str:
    if result["state"] == "INCOMPLETE":
        return "INCOMPLETE"
    return "PASS" if result["state"] == "PASS" and not result["problems"] else "FAIL"


# the levels a reproduction must have passed; ``version_sensitivity`` is a measurement
REPRODUCTION_LEVELS = ("archive", "same_environment", "locked_environment")


def _reproduction_status(result: dict) -> str:
    states = {name: result["levels"].get(name) for name in REPRODUCTION_LEVELS}
    if "FAIL" in states.values():
        return "FAIL"
    return "PASS" if set(states.values()) == {"PASS"} else "INCOMPLETE"


_RULES = {
    "fast": _fast_status,
    "deep": _deep_status,
    "faults": _faults_status,
    "real": _real_status,
    "tools": _tools_status,
    "types": _types_status,
    "reproduction": _reproduction_status,
}


# --- builders ---


def build_fast(
    coverage: Path, junit: Path, *, root: Path = ROOT, source=None, environment=None, execution=None
):
    raw = verification_report.build_report(coverage, junit)
    result = {"tests": raw["tests"], "coverage": raw["coverage"]}
    return _envelope(
        "fast", _fast_status(result), result, [coverage, junit], root, source, environment
    )


def build_deep(
    stats: Path, results: Path | None = None, *, root: Path = ROOT, scope=None, source=None,
    environment=None, execution=None,
):  # fmt: skip
    """Wrap the mutation counts; ``results`` lists the mutants (``mutmut results --all``)."""
    scope = mutation_scope.configured_patterns(ROOT / "pyproject.toml") if scope is None else scope
    result = {
        "scope": scope,
        "scope_files": mutation_scope.resolve(scope, root),
        "mutated_files": None,
        "threshold": check_mutation.THRESHOLD,
    }
    artifacts = [stats]
    if results is not None:
        artifacts.append(results)
        try:
            result["mutated_files"] = mutation_scope.mutated_files(results.read_text(), root)
        except OSError as exc:
            result["reason"] = str(exc)
    try:
        counts = json.loads(stats.read_text())
        check_mutation.classify(counts)
        result["stats"] = counts
    except (OSError, ValueError) as exc:
        result["stats"] = {}
        result["reason"] = str(exc)
        return _envelope(
            "deep", "INCOMPLETE", result, artifacts, root, source, environment, execution
        )
    status = _deep_status(result)
    result["score"] = 100.0 * counts["killed"] / counts["total"]
    return _envelope("deep", status, result, artifacts, root, source, environment, execution)


def build_faults(
    matrix: Path, expected, *, root: Path = ROOT, source=None, environment=None, execution=None
):
    result = {"expected": sorted(expected), "faults": [], "control_passed": False}
    try:
        rows = json.loads(matrix.read_text())
        if not isinstance(rows, list):
            raise ValueError("fault matrix is not a list")
        result["faults"] = [
            {"defect": row["defect"], "detected": row["caught_by_expected_test"] is True}
            for row in rows
        ]
        result["control_passed"] = bool(rows) and all(row["control_passed"] is True for row in rows)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["reason"] = str(exc)
        return _envelope(
            "faults", "INCOMPLETE", result, [matrix], root, source, environment, execution
        )
    return _envelope(
        "faults", _faults_status(result), result, [matrix], root, source, environment, execution
    )


def build_real(report: Path, *, root: Path = ROOT, source=None, environment=None, execution=None):
    try:
        raw = json.loads(report.read_text())
        result = {
            "required": list(REQUIRED_DATASETS),
            "datasets": [
                {key: item[key] for key in ("dataset", "status", "sha256") if key in item}
                for item in raw["datasets"]
            ],
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"required": [], "datasets": [], "reason": str(exc)}
        return _envelope(
            "real", "INCOMPLETE", result, [report], root, source, environment, execution
        )
    return _envelope(
        "real", _real_status(result), result, [report], root, source, environment, execution
    )


def build_tools(
    coverage: Path, *, root: Path = ROOT, source=None, environment=None, execution=None
):
    """Line and branch coverage of the verifier code (``make verify-tools``)."""
    result: dict[str, Any]
    try:
        totals = json.loads(coverage.read_text())["totals"]
        result = {
            "coverage": {
                "line": {"covered": totals["covered_lines"], "coverable": totals["num_statements"]},
                "branch": {
                    "covered": totals["covered_branches"],
                    "coverable": totals["num_branches"],
                },
            }
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"coverage": {}, "reason": str(exc)}
        return _envelope(
            "tools", "INCOMPLETE", result, [coverage], root, source, environment, execution
        )
    return _envelope(
        "tools", _tools_status(result), result, [coverage], root, source, environment, execution
    )


def build_types(report: Path, *, root: Path = ROOT, source=None, environment=None, execution=None):
    """The typing gate's report (``check_types.py --output``)."""
    try:
        raw = json.loads(report.read_text())
        result = {
            "state": raw["status"],
            "errors": raw.get("errors"),
            "baseline_entries": raw.get("baseline_entries"),
            "problems": list(raw["problems"]),
            "mypy": raw.get("mypy"),
            "pandas-stubs": raw.get("pandas-stubs"),
        }
        if "reason" in raw:
            result["reason"] = raw["reason"]
        status = _types_status(result)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result, status = {"state": "INCOMPLETE", "problems": [], "reason": str(exc)}, "INCOMPLETE"
    return _envelope("types", status, result, [report], root, source, environment, execution)


def build_reproduction(
    report: Path, *, root: Path = ROOT, source=None, environment=None, execution=None
):
    """The controlled reproduction report (``python -m verification.reproduce``)."""
    try:
        raw = json.loads(report.read_text())
        levels = {name: item["status"] for name, item in raw["levels"].items()}
        result = {
            "dataset": raw["dataset"],
            "levels": levels,
            "claimed_outcome": raw.get("outcome"),
        }
        status = _reproduction_status(result)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result, status = {"levels": {}, "reason": str(exc)}, "INCOMPLETE"
    return _envelope("reproduction", status, result, [report], root, source, environment, execution)


# --- validation ---


def _is_int(value) -> bool:
    return type(value) is int


def _check_envelope(doc: dict, problems: list[str]) -> None:
    if doc.get("schema_version") != SCHEMA_VERSION or type(doc.get("schema_version")) is not int:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    if doc.get("kind") not in KINDS:
        problems.append("kind must be one of " + ", ".join(KINDS))
    if doc.get("status") not in STATUSES:
        problems.append("status must be one of " + ", ".join(STATUSES))
    try:
        moment = datetime.fromisoformat(doc["captured_at"])
        if moment.utcoffset() is None:
            problems.append("captured_at has no timezone")
    except (KeyError, TypeError, ValueError):
        problems.append("captured_at must be an ISO-8601 timestamp")
    source = doc.get("source")
    if not isinstance(source, dict):
        problems.append("source must be a mapping")
    else:
        if not isinstance(source.get("revision"), str) or not _HEX40.fullmatch(source["revision"]):
            problems.append("source.revision must be a 40-character commit hash")
        if not isinstance(source.get("worktree_dirty"), bool):
            problems.append("source.worktree_dirty must be a boolean")
        fingerprint = source.get("scientific_fingerprint")
        if not isinstance(fingerprint, str) or not _HEX64.fullmatch(fingerprint):
            problems.append("source.scientific_fingerprint must be a sha256 hex digest")
    environment = doc.get("environment")
    if not isinstance(environment, dict):
        problems.append("environment must be a mapping")
    else:
        for key in ("python", "platform"):
            if not isinstance(environment.get(key), str):
                problems.append(f"environment.{key} must be a string")
        packages = environment.get("packages")
        if not isinstance(packages, dict) or any(
            not isinstance(v, str) and v is not None for v in packages.values()
        ):
            problems.append("environment.packages must map names to versions")
    if "execution" in doc:
        execution = doc["execution"]
        text = {"run_id", "runner_environment", "runner_name"}
        if (
            not isinstance(execution, dict)
            or set(execution) != {"ci", *text}
            or not isinstance(execution["ci"], bool)
            or any(not isinstance(execution[key], str | None) for key in text)
        ):
            problems.append(
                "execution must give ci (a boolean), run_id, runner_environment, runner_name"
            )
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, dict):
        problems.append("artifacts must be a mapping")
    elif any(not isinstance(v, str) or not _HEX64.fullmatch(v) for v in artifacts.values()):
        problems.append("artifacts must map paths to sha256 hex digests")
    if not isinstance(doc.get("result"), dict):
        problems.append("result must be a mapping")


def _check_result(doc: dict, problems: list[str]) -> None:
    kind, status, result = doc["kind"], doc["status"], doc["result"]
    try:
        expected = _RULES[kind](result)
        if kind == "deep" and result["stats"]:
            for key in ("total", *OUTCOMES):
                if not _is_int(result["stats"].get(key)):
                    raise ValueError(f"stats.{key} must be an integer")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        problems.append(f"result is malformed for kind {kind}: {exc!r}")
        return
    if status == "PASS" and expected != "PASS":
        problems.append(f"status PASS is not supported by the result (it gives {expected})")
    if status == "PASS" and not doc["artifacts"]:
        problems.append("a PASS must list the artifacts it was derived from")
    if status == "PASS" and kind == "deep" and not result["scope"]:
        problems.append("deep result has an empty mutation scope")


def validate(doc, root: Path | None = None) -> list[str]:
    """Return every reason the document is not valid evidence (empty when valid)."""
    if not isinstance(doc, dict):
        return ["evidence must be a JSON object"]
    problems: list[str] = []
    _check_envelope(doc, problems)
    if problems:
        return problems
    _check_result(doc, problems)
    if root is not None:
        for relative, expected in doc["artifacts"].items():
            path = root / relative
            if not path.is_file():
                problems.append(f"artifact {relative} is missing")
            elif _sha256(path) != expected:
                problems.append(f"artifact {relative} hash differs from the recorded one")
    return problems


def fault_names() -> list[str]:
    """Names of the deliberate defects the FAULTS profile must detect."""
    sys.path.insert(0, str(ROOT))
    from tests.test_fault_matrix import FAULTS

    return [fault.name for fault in FAULTS]


def _write(doc: dict, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"{doc['kind']} evidence: {doc['status']}")
    return 0 if doc["status"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="validate one evidence file")
    check.add_argument("path", type=Path)
    check.add_argument("--root", type=Path, default=None, help="verify artifact hashes here")
    for name, inputs in (
        ("fast", ("coverage", "junit")),
        ("deep", ("stats", "results")),
        ("faults", ("matrix",)),
        ("real", ("report",)),
        ("tools", ("coverage",)),
        ("types", ("report",)),
        ("reproduction", ("report",)),
    ):
        build = sub.add_parser(name, help=f"wrap the raw {name} results in an envelope")
        for item in inputs:
            build.add_argument(f"--{item}", type=Path, required=True)
        build.add_argument("--output", type=Path, required=True)
        build.add_argument(
            "--root", type=Path, default=ROOT, help="artifact paths are relative to it"
        )
    args = parser.parse_args(argv)
    if args.command != "validate":
        try:
            if args.command == "fast":
                doc = build_fast(args.coverage, args.junit, root=args.root)
            elif args.command == "deep":
                doc = build_deep(args.stats, args.results, root=args.root)
            elif args.command == "faults":
                doc = build_faults(args.matrix, fault_names(), root=args.root)
            elif args.command == "tools":
                doc = build_tools(args.coverage, root=args.root)
            elif args.command == "types":
                doc = build_types(args.report, root=args.root)
            elif args.command == "reproduction":
                doc = build_reproduction(args.report, root=args.root)
            else:
                doc = build_real(args.report, root=args.root)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"INVALID: {exc}")
            return 1
        return _write(doc, args.output)
    try:
        doc = json.loads(args.path.read_text())
    except (OSError, ValueError) as exc:
        print(f"INVALID: cannot read {args.path}: {exc}")
        return 1
    problems = validate(doc, root=args.root)
    for problem in problems:
        print(f"INVALID: {problem}")
    if not problems:
        print(f"valid {doc['kind']} evidence: {doc['status']}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
