"""Check that archived experiment records still describe the current scientific code.

Two questions are kept apart:

* historical integrity: can the fingerprint stored in a record be reproduced
  from a committed tree? Recipe-1 records (made before the verification gates
  were excluded) are checked against the anchor revision named in
  ``evidence/lineage.json``. They are never restamped.
* current-source reproducibility: is the result-affecting code at HEAD the same
  as the code the record is bound to? Compared with the recipe-2 fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import provenance  # noqa: E402

LINEAGE = ROOT / "verification" / "evidence" / "lineage.json"


def fingerprint_v1_of(files: dict[str, bytes]) -> str:
    """Recipe 1 over a source mapping; equals ``provenance._source_fingerprint``."""
    digest = hashlib.sha256()
    for path in sorted(files):
        parts = path.split("/")
        recipe_1 = (
            (parts[0] == "src" and path.endswith(".py"))
            or (parts[0] == "experiments" and len(parts) == 2 and path.endswith(".py"))
            or path == "environment.yml"
        )
        if recipe_1:
            digest.update(path.encode())
            digest.update(files[path])
    project = tomllib.loads(files["pyproject.toml"].decode())["project"]
    digest.update(json.dumps(project, sort_keys=True).encode())
    return digest.hexdigest()


def files_at(revision: str, root: Path = ROOT) -> dict[str, bytes]:
    """Source files of a committed tree, as ``{relative path: content}``."""

    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=root)

    names = git("ls-tree", "-r", "--name-only", revision).decode().splitlines()
    wanted = [n for n in names if n.endswith(".py") and n.split("/")[0] in ("src", "experiments")]
    wanted += [n for n in names if n in ("environment.yml", "pyproject.toml")]
    return {name: git("show", f"{revision}:{name}") for name in wanted}


def worktree_files(root: Path = ROOT) -> dict[str, bytes]:
    paths = [*root.glob("src/**/*.py"), *root.glob("experiments/*.py")]
    paths += [root / "environment.yml", root / "pyproject.toml"]
    return {str(path.relative_to(root)): path.read_bytes() for path in paths}


def check_record(record: dict, anchor: dict[str, bytes], current: dict[str, bytes]) -> list[str]:
    """Return the reasons a record's lineage is not valid (empty when valid)."""
    recipe = record.get("fingerprint_recipe", 1)
    if recipe == 1:
        problems = []
        if record.get("source_fingerprint") != fingerprint_v1_of(anchor):
            problems.append("the anchor tree does not reproduce the recipe-1 fingerprint")
        if provenance.scientific_fingerprint_of(anchor) != (
            provenance.scientific_fingerprint_of(current)
        ):
            problems.append("result-affecting source changed since the anchor revision")
        return problems
    if recipe == provenance.SCIENTIFIC_RECIPE:
        stored = record.get("scientific_fingerprint")
        if stored != provenance.scientific_fingerprint_of(current):
            return ["scientific fingerprint differs from the current source"]
        return []
    return [f"unknown fingerprint recipe {recipe!r}"]


def anchor_revision() -> str:
    return json.loads(LINEAGE.read_text())["legacy_anchor"]["revision"]
