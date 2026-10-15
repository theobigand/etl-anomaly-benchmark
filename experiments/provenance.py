"""Reproducible run metadata for thesis experiment artifacts."""

from __future__ import annotations

import gzip
import hashlib
import json
import platform
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd

from etl_benchmark.split import stratified_split

ROOT = Path(__file__).resolve().parents[1]


def write_split_ids(
    path: Path,
    frame: pd.DataFrame,
    label_column: str,
    seeds: list[int],
    ratios: tuple[float, float, float],
    fit_sample: int | None = None,
) -> Path:
    """Archive row positions after preprocessing for each seeded split."""
    if fit_sample is not None and fit_sample <= 0:
        raise ValueError("fit_sample must be positive")
    marker = "_split_row_id"
    if marker in frame:
        raise ValueError(f"reserved split marker {marker!r} is already present")
    marked = frame.assign(**{marker: range(len(frame))})
    partitions = {}
    for seed in seeds:
        train, validation, test = stratified_split(marked, label_column, ratios, seed)
        membership = {
            name: part[marker].astype(int).tolist()
            for name, part in (("train", train), ("validation", validation), ("test", test))
        }
        if fit_sample is not None and fit_sample < len(train):
            membership["fit"] = train[marker].sample(n=fit_sample, random_state=seed).tolist()
        partitions[str(seed)] = membership
    record = {"schema_version": 1, "row_count": len(frame), "seeds": partitions}
    path.parent.mkdir(parents=True, exist_ok=True)
    document = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(gzip.compress(document, mtime=0))
    return path


def read_split_ids(path: Path) -> dict:
    """Read an archive produced by :func:`write_split_ids`."""
    with gzip.open(path) as stream:
        return json.load(stream)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, hashlib.sha256).hexdigest()


def _source_fingerprint() -> str:
    """Hash the code, the environment file and the project metadata.

    Only the ``[project]`` table of ``pyproject.toml`` counts (name,
    dependencies); settings of test and mutation tools do not change a result.
    """
    digest = hashlib.sha256()
    paths = [
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("experiments/*.py"),
        ROOT / "environment.yml",
    ]
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    digest.update(json.dumps(project, sort_keys=True).encode())
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
    revision = _git("rev-parse", "HEAD")
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
        "worktree_dirty": bool(_git("status", "--porcelain")),
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
