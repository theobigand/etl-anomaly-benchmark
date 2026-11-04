"""Prospective risk-scoped arithmetic; execution provenance is checked separately.

Historical global mutation reports retain their original criterion. This module
does not certify a release or establish that cached execution is still admissible.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

VERSION = 2
THRESHOLDS = {"L1": 80, "L2": 90, "L3": 95, "L4": 98}
OUTCOMES = (
    "killed",
    "survived",
    "timeout",
    "suspicious",
    "error",
    "caught by type check",
    "not checked",
    "no tests",
    "skipped",
    "segfault",
    "check was interrupted by user",
)
INCOMPLETE = {
    "not checked",
    "no tests",
    "skipped",
    "segfault",
    "check was interrupted by user",
    "error",
}


def _canonical_name(name: str) -> PurePosixPath:
    if (
        not isinstance(name, str)
        or not name
        or "\\" in name
        or PurePosixPath(name).is_absolute()
        or any(part in (".", "..") for part in name.split("/"))
        or str(PurePosixPath(name)) != name
    ):
        raise ValueError("policy paths must be canonical relative paths")
    return PurePosixPath(name)


def _relative(name: str, root: Path) -> Path:
    path = root / _canonical_name(name)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError(f"policy path escapes or aliases the source tree: {name}")
    return path


def _validate_declarations(policy: dict) -> None:
    """Check recorded declarations; actual files and function bodies need a root."""
    if (
        not isinstance(policy, dict)
        or type(policy.get("version")) is not int
        or policy["version"] != VERSION
    ):
        raise ValueError("mutation risk policy version must be 2")
    thresholds = policy.get("thresholds")
    if thresholds != THRESHOLDS or any(type(value) is not int for value in thresholds.values()):
        raise ValueError("thresholds must be L1=80 L2=90 L3=95 L4=98")
    roots, units = policy.get("roots"), policy.get("units")
    if not isinstance(roots, list) or not roots or any(not isinstance(p, str) for p in roots):
        raise ValueError("policy roots must be a nonempty path list")
    if len(set(roots)) != len(roots) or not isinstance(units, dict) or not units:
        raise ValueError("policy roots must be unique and units must be nonempty")
    for base in roots:
        _canonical_name(base)
    for name, unit in units.items():
        path = _canonical_name(name)
        if not any(path.is_relative_to(base) for base in roots):
            raise ValueError(f"classification lies outside the policy roots: {name}")
        if (
            not isinstance(unit, dict)
            or not isinstance(unit.get("level"), str)
            or unit["level"] not in THRESHOLDS
        ):
            raise ValueError(f"invalid risk level for {name}")
        if not isinstance(unit.get("reason"), str) or not unit["reason"].strip():
            raise ValueError(f"classification for {name} requires a reason")
        if "no_mutants" in unit and (
            not isinstance(unit["no_mutants"], str) or not unit["no_mutants"].strip()
        ):
            raise ValueError(f"technical exclusion for {name} requires a reason")


def validate_policy(policy: dict, root: Path) -> None:
    """Require justified classifications for the actual production tree and bodies."""
    _validate_declarations(policy)
    roots, units = policy["roots"], policy["units"]
    discovered = set()
    for base in roots:
        directory = _relative(base, root)
        if not directory.is_dir():
            raise ValueError(f"policy root does not exist: {base}")
        for path in directory.rglob("*.py"):
            if "tests" in path.relative_to(directory).parts or "__pycache__" in path.parts:
                continue
            discovered.add(path.relative_to(root).as_posix())
    if discovered != set(units):
        raise ValueError(
            f"unclassified sources: {sorted(discovered - set(units))}; "
            f"stale classifications: {sorted(set(units) - discovered)}"
        )
    for name, unit in units.items():
        path = _relative(name, root)
        if "no_mutants" in unit:
            tree = ast.parse(path.read_text())
            if any(
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) for node in ast.walk(tree)
            ):
                raise ValueError(f"technical no-mutant declaration contains functions: {name}")


def policy_digest(policy: dict) -> str:
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _module(path: str) -> str:
    value = path.removeprefix("src/").removesuffix(".py")
    if value.endswith("/__init__"):
        value = value.removesuffix("/__init__")
    return value.replace("/", ".")


def _identity(key: str, path: str) -> None:
    if not isinstance(key, str) or not key.startswith(_module(path) + "."):
        raise ValueError("mutant identity does not belong to its source module")
    function, marker, index = key.rpartition("__mutmut_")
    if not marker or not function or not index.isdecimal() or int(index) <= 0:
        raise ValueError("invalid mutant identity")
    local = function.removeprefix(_module(path) + ".")
    if local.startswith("x_") and local.isidentifier():
        return
    owner = local.split("ǁ")
    if (
        len(owner) != 3
        or owner[0] != "x"
        or any(not part.isidentifier() for part in owner[1].split("."))
        or not owner[2].isidentifier()
    ):
        raise ValueError("invalid native mutant function identity")


def _summary(records: list[dict], eligible: int, threshold: int) -> dict:
    counts = Counter(record["outcome"] for record in records)
    incomplete = len(records) != eligible or not eligible or any(counts[s] for s in INCOMPLETE)
    killed = counts["killed"]
    status = (
        "INCOMPLETE" if incomplete else ("PASS" if killed * 100 >= threshold * eligible else "FAIL")
    )
    return {
        "eligible": eligible,
        **{outcome: counts[outcome] for outcome in OUTCOMES},
        "threshold": threshold,
        "score": 100.0 * killed / eligible if eligible else None,
        "status": status,
        "exclusions": [],
    }


def _aggregate_status(statuses: list[str]) -> str:
    if "FAIL" in statuses:
        return "FAIL"
    if "INCOMPLETE" in statuses:
        return "INCOMPLETE"
    return "PASS"


def evaluate(policy: dict, root: Path, catalog: dict, records: list[dict]) -> dict:
    """Reconcile outcomes with a complete catalog and enforce every module boundary.

    A caller must additionally bind the catalog and execution to current source,
    tests, tool and dependencies. A newly computed digest does not revalidate old
    execution. Missing observations remain incomplete, never removed from counts.
    """
    validate_policy(policy, root)
    sources = {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in policy["units"]
    }
    return evaluate_snapshot(policy, sources, catalog, records)


def evaluate_snapshot(policy: dict, sources: dict, catalog: dict, records: list[dict]) -> dict:
    """Recompute recorded arithmetic, without proving live scope or execution.

    Snapshot declarations cannot establish technical exclusions or absence of
    unclassified files. Current certification must additionally call ``evaluate``
    against its actual root and validate native execution/artifact bindings.
    """
    _validate_declarations(policy)
    if (
        not isinstance(sources, dict)
        or set(sources) != set(policy["units"])
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in sources.values()
        )
    ):
        raise ValueError("recorded sources must map every classified unit to its SHA-256")
    if not isinstance(catalog, dict) or not isinstance(records, list):
        raise ValueError("catalog must be a mapping and records a list")
    units = policy["units"]
    if set(catalog) - set(units):
        raise ValueError("catalog contains unclassified modules")
    expected = {}
    for path, keys in catalog.items():
        if not isinstance(keys, list):
            raise ValueError("catalog identities must be lists")
        for key in keys:
            _identity(key, path)
            if key in expected or "no_mutants" in units[path]:
                raise ValueError("duplicate or technically excluded mutant identity")
            expected[key] = path
    observed = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"id", "path", "outcome"}:
            raise ValueError("invalid mutant record shape")
        key, path = record["id"], record["path"]
        if not isinstance(key, str) or key in observed or key not in expected:
            raise ValueError("duplicate or unknown mutant record")
        if path != expected[key] or record["outcome"] not in OUTCOMES:
            raise ValueError("mutant path or outcome differs from catalog")
        observed.add(key)
    modules = {}
    for path, unit in sorted(units.items()):
        selected = [record for record in records if record["path"] == path]
        modules[path] = {
            "level": unit["level"],
            "reason": unit["reason"],
            **_summary(selected, len(catalog.get(path, [])), THRESHOLDS[unit["level"]]),
        }
        if "no_mutants" in unit:
            modules[path]["status"] = "NO_MUTANTS_TECHNICAL"
            modules[path]["exclusions"] = [unit["no_mutants"]]
    levels = {}
    for level, threshold in THRESHOLDS.items():
        paths = [path for path, unit in units.items() if unit["level"] == level]
        selected = [record for record in records if record["path"] in paths]
        eligible = sum(len(catalog.get(path, [])) for path in paths)
        scoped = [modules[path]["status"] for path in paths if "no_mutants" not in units[path]]
        summary = _summary(selected, eligible, threshold)
        summary["status"] = _aggregate_status(scoped) if scoped else "NOT_APPLICABLE"
        levels[level] = summary
    required = [
        unit["status"] for unit in modules.values() if unit["status"] != "NO_MUTANTS_TECHNICAL"
    ]
    total = _summary(records, len(expected), 0)
    status = _aggregate_status(required) if required else "INCOMPLETE"
    total.pop("threshold")
    total["status"] = status
    return {
        "policy_version": VERSION,
        "policy_sha256": policy_digest(policy),
        "sources": dict(sources),
        "modules": modules,
        "levels": levels,
        "total": total,
        "status": status,
    }
