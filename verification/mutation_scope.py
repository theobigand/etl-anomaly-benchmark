"""Independent inventory of the code the mutation campaign must cover.

``pyproject.toml`` decides what mutmut mutates. A configuration that quietly
drops a module can keep a high score, so the eligible files are discovered here
from the tree (``mutation_scope.json`` names the roots and every justified
exclusion) and compared with the configured patterns and, in the DEEP
evidence, with the files that really received mutants.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "verification" / "mutation_scope.json"
VERSION = 1


def load(path: Path = CONFIG) -> dict:
    config = json.loads(path.read_text())
    if config.get("version") != VERSION:
        raise ValueError(f"mutation scope version must be {VERSION}")
    return config


def configured_patterns(pyproject: Path = ROOT / "pyproject.toml") -> list[str]:
    return list(tomllib.loads(pyproject.read_text())["tool"]["mutmut"]["only_mutate"])


def _python_files(root: Path, base: str) -> list[str]:
    return sorted(
        str(path.relative_to(root))
        for path in (root / base).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def inventory(root: Path, config: dict) -> list[str]:
    """Every eligible file below the roots: the tree minus the justified exclusions."""
    found: set[str] = set()
    for base in config["roots"]:
        found.update(_python_files(root, base))
    return sorted(found - set(config["exclusions"]))


def resolve(patterns: list[str], root: Path) -> list[str]:
    """Files matched by the mutmut patterns."""
    files: set[str] = set()
    for pattern in patterns:
        files.update(str(path.relative_to(root)) for path in root.glob(pattern) if path.is_file())
    return sorted(files)


def check(patterns: list[str], root: Path, config: dict) -> list[str]:
    """Reasons the configured scope is not the eligible inventory (empty when equal)."""
    problems: list[str] = []
    for name, reason in sorted(config["exclusions"].items()):
        if not str(reason).strip():
            problems.append(f"exclusion {name} has no reason")
        if not (root / name).is_file():
            problems.append(f"exclusion {name} does not exist")
    wanted = set(inventory(root, config))
    scope = set(resolve(patterns, root))
    for name in sorted(wanted - scope):
        problems.append(f"{name} is eligible but not mutated")
    for name in sorted(scope & set(config["exclusions"])):
        problems.append(f"{name} is mutated although it is excluded")
    for name in sorted(scope - wanted - set(config["exclusions"])):
        problems.append(f"{name} is mutated but is outside the eligible roots")
    for pattern in patterns:
        if not any(root.glob(pattern)):
            problems.append(f"pattern {pattern} matches no file")
    return problems


def mutated_files(results: str, root: Path, bases: tuple[str, ...] = ("src", ".")) -> list[str]:
    """Source files that received at least one mutant, from ``mutmut results --all``."""
    found: set[str] = set()
    for line in results.splitlines():
        name, sep, _ = line.strip().partition(": ")
        if not sep or ".x" not in name:
            continue
        module = name.rsplit(".", 1)[0].replace(".", "/")
        for base in bases:
            for candidate in (f"{module}.py", f"{module}/__init__.py"):
                if (root / base / candidate).is_file():
                    found.add(str((root / base / candidate).relative_to(root)))
    return sorted(found)


def check_mutated(scope_files: list[str], mutated: list[str], config: dict) -> list[str]:
    """Compare the files that received mutants with the configured scope."""
    problems = []
    for name in sorted(set(mutated) - set(scope_files)):
        problems.append(f"{name} received mutants but is outside the recorded scope")
    allowed = set(config.get("no_mutants", {}))
    for name in sorted(set(scope_files) - set(mutated) - allowed):
        problems.append(f"{name} is in the scope but received no mutant")
    return problems


def check_evidence(result: dict, wanted: list[str], config: dict) -> list[str]:
    """Judge the scope recorded in a DEEP result against the eligible inventory."""
    scope_files, mutated = result.get("scope_files"), result.get("mutated_files")
    if not isinstance(scope_files, list) or not isinstance(mutated, list):
        return ["the files that were mutated are not recorded"]
    problems = [
        f"{name} is eligible but not mutated" for name in sorted(set(wanted) - set(scope_files))
    ]
    problems += [
        f"{name} was mutated but is not an eligible file"
        for name in sorted(set(scope_files) - set(wanted))
    ]
    return problems + check_mutated(scope_files, mutated, config)
