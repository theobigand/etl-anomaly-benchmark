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
from datetime import date
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
    governance = policy.get("governance")
    if governance is not None and (
        not isinstance(governance, dict)
        or set(governance) != {"review_mode", "owner"}
        or governance["review_mode"] != REVIEW_MODE
        or not _text(governance["owner"])
    ):
        raise ValueError("invalid governance declaration")
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


def _summary(records: list[dict], eligible: int, threshold: int, equivalent: int = 0) -> dict:
    """Raw counts plus the score over the eligible mutants after accepted equivalents."""
    counts = Counter(record["outcome"] for record in records)
    adjusted = eligible - equivalent
    incomplete = len(records) != eligible or not adjusted or any(counts[s] for s in INCOMPLETE)
    killed = counts["killed"]
    status = (
        "INCOMPLETE" if incomplete else ("PASS" if killed * 100 >= threshold * adjusted else "FAIL")
    )
    return {
        "eligible": eligible,
        **{outcome: counts[outcome] for outcome in OUTCOMES},
        "threshold": threshold,
        "raw_score": 100.0 * killed / eligible if eligible else None,
        "equivalent_accepted": equivalent,
        "adjusted_eligible": adjusted,
        "score": 100.0 * killed / adjusted if adjusted > 0 else None,
        "status": status,
        "exclusions": [],
    }


def _aggregate_status(statuses: list[str]) -> str:
    if "FAIL" in statuses:
        return "FAIL"
    if "INCOMPLETE" in statuses:
        return "INCOMPLETE"
    return "PASS"


EQUIVALENCE_VERSION = 2
REVIEW_MODE = "sole_author_owner_review"
VERDICTS = ("accepted", "rejected", "inconclusive", "proposed")
_EQUIVALENCE_TEXT = (
    "id", "path", "function", "diff", "original_behavior", "mutated_behavior", "risk", "reason",
    "source_sha256", "catalog_sha256", "author",
)  # fmt: skip
_EQUIVALENCE_KEYS = {
    *_EQUIVALENCE_TEXT, "evidence", "verdict", "approver", "decision_date", "policy_version",
    "environment", "assessments",
}  # fmt: skip


def catalog_digest(keys: list[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(keys), separators=(",", ":")).encode()).hexdigest()


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def accepted_equivalents(
    document: dict | None,
    units: dict,
    sources: dict,
    catalog: dict,
    records: list[dict],
    governance: dict | None = None,
    environment: dict | None = None,
) -> dict[str, set[str]]:
    """Validate owner-reviewed equivalence records; return accepted mutant ids per module.

    Review model ``sole_author_owner_review``: this is an individual thesis whose only
    authorized approver is the repository owner declared in the policy, who may approve a
    claim they or an assistant proposed. It is not independent peer review and the approver
    identity is recorded text, not an authenticated signature. Only a record with the verdict
    ``accepted`` and the owner's recorded decision excludes a mutant; ``proposed``,
    ``rejected`` and ``inconclusive`` records are validated and ignored; their mutant may
    survive or later be killed by better tests and is counted by its actual outcome. Every
    record must name a mutant of the current catalog and match the current source and module
    catalog digests, risk level and policy version. An accepted record must additionally name
    a surviving mutant and match the dependency versions of the campaign environment, so a
    killed accepted mutant needs its review record reconciled. Any mismatch rejects the evidence.
    """
    if document is None:
        return {}
    if (
        not isinstance(governance, dict)
        or governance.get("review_mode") != REVIEW_MODE
        or not _text(governance.get("owner"))
    ):
        raise ValueError("the policy does not declare the sole-author owner review mode")
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "review_mode", "owner", "records"}
        or document["version"] != EQUIVALENCE_VERSION
        or not isinstance(document["records"], list)
    ):
        raise ValueError("equivalence document must be version 2 with a record list")
    if document["review_mode"] != REVIEW_MODE or document["owner"] != governance["owner"]:
        raise ValueError("equivalence document does not match the declared review mode and owner")
    outcome = {record["id"]: record["outcome"] for record in records}
    owner = {key: path for path, keys in catalog.items() for key in keys}
    accepted: dict[str, set[str]] = {}
    seen = set()
    for item in document["records"]:
        if not isinstance(item, dict) or set(item) != _EQUIVALENCE_KEYS:
            raise ValueError("invalid equivalence record shape")
        if any(not _text(item[name]) for name in _EQUIVALENCE_TEXT):
            raise ValueError("equivalence record fields must be nonempty text")
        evidence = item["evidence"]
        if not isinstance(evidence, list) or not evidence or any(not _text(e) for e in evidence):
            raise ValueError("equivalence record needs supporting evidence")
        assessments = item["assessments"]
        if not isinstance(assessments, list) or any(
            not isinstance(a, dict)
            or set(a) != {"assessor", "verdict", "note"}
            or not _text(a["assessor"])
            or a["verdict"] not in ("ACCEPT", "REJECT", "INCONCLUSIVE")
            or not _text(a["note"])
            for a in assessments
        ):
            raise ValueError("invalid equivalence assessments")
        key, path = item["id"], item["path"]
        if key in seen or key not in owner or owner[key] != path:
            raise ValueError("duplicate or unknown equivalence identity")
        seen.add(key)
        if item["verdict"] not in VERDICTS:
            raise ValueError("invalid equivalence verdict")
        decided = item["verdict"] != "proposed"
        if decided:
            if item["approver"] != governance["owner"]:
                raise ValueError("an equivalence decision must be recorded by the declared owner")
            try:
                date.fromisoformat(item["decision_date"])
            except (TypeError, ValueError) as error:
                raise ValueError("equivalence decision date must be ISO 8601") from error
        elif item["approver"] != "" or item["decision_date"] != "":
            raise ValueError("a proposed equivalence must not carry an approver or decision date")
        if item["verdict"] == "accepted" and outcome.get(key) != "survived":
            raise ValueError("only a surviving mutant can be accepted as equivalent")
        if item["policy_version"] != VERSION or item["risk"] != units[path]["level"]:
            raise ValueError("equivalence record does not match the policy version or risk level")
        if item["source_sha256"] != sources[path] or item["catalog_sha256"] != catalog_digest(
            catalog[path]
        ):
            raise ValueError("equivalence record is stale for the current source or catalog")
        recorded = item["environment"]
        if (
            not isinstance(recorded, dict)
            or not recorded
            or any(not _text(name) or not _text(version) for name, version in recorded.items())
        ):
            raise ValueError("equivalence record must state the dependency versions it relies on")
        if item["verdict"] == "accepted":
            if not isinstance(environment, dict) or any(
                environment.get(name) != version for name, version in recorded.items()
            ):
                raise ValueError("equivalence record is incompatible with the campaign environment")
            accepted.setdefault(path, set()).add(key)
    return accepted


def evaluate(
    policy: dict,
    root: Path,
    catalog: dict,
    records: list[dict],
    equivalence: dict | None = None,
    environment: dict | None = None,
) -> dict:
    """Reconcile outcomes with a complete catalog and enforce every module boundary.

    A caller must additionally bind the catalog and execution to current source,
    tests, tool and dependencies. A newly computed digest does not revalidate old
    execution. Missing observations remain incomplete, never removed from counts.
    """
    validate_policy(policy, root)
    sources = {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in policy["units"]
    }
    return evaluate_snapshot(policy, sources, catalog, records, equivalence, environment)


def evaluate_snapshot(
    policy: dict,
    sources: dict,
    catalog: dict,
    records: list[dict],
    equivalence: dict | None = None,
    environment: dict | None = None,
) -> dict:
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
    waived = accepted_equivalents(
        equivalence, units, sources, catalog, records, policy.get("governance"), environment
    )
    modules = {}
    for path, unit in sorted(units.items()):
        selected = [record for record in records if record["path"] == path]
        modules[path] = {
            "level": unit["level"],
            "reason": unit["reason"],
            **_summary(
                selected,
                len(catalog.get(path, [])),
                THRESHOLDS[unit["level"]],
                len(waived.get(path, ())),
            ),
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
        summary = _summary(
            selected, eligible, threshold, sum(len(waived.get(path, ())) for path in paths)
        )
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
        "equivalence_version": EQUIVALENCE_VERSION,
        "review_mode": REVIEW_MODE,
        "accepted_equivalents": {path: sorted(keys) for path, keys in sorted(waived.items())},
        "modules": modules,
        "levels": levels,
        "total": total,
        "status": status,
    }
