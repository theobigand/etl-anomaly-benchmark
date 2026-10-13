"""Reproducible run metadata for thesis experiment artifacts."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_fingerprint() -> str:
    digest = hashlib.sha256()
    paths = [
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("experiments/*.py"),
        ROOT / "pyproject.toml",
        ROOT / "environment.yml",
    ]
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_record(
    path: Path,
    *,
    experiment: str,
    seeds: list[int],
    dataset: str,
    data_path: Path | None,
    settings: dict,
    outputs: list[str],
) -> Path:
    """Write the code, data and protocol identity beside experiment outputs."""
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    packages = {}
    for name in ("numpy", "pandas", "scikit-learn", "pyod", "great-expectations"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    source = {"identity": dataset}
    if data_path is not None:
        source.update(
            {
                "path": str(data_path),
                "sha256": _hash_file(data_path),
                "bytes": data_path.stat().st_size,
            }
        )
    record = {
        "schema_version": 1,
        "experiment": experiment,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_revision": revision,
        "source_fingerprint": _source_fingerprint(),
        "worktree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": packages,
        "dataset": source,
        "seeds": seeds,
        "settings": settings,
        "outputs": outputs,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return path
