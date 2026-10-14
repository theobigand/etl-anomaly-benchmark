"""Reproducible run metadata for thesis experiment artifacts."""

from __future__ import annotations

import gzip
import hashlib
import json
import platform
import subprocess
import sys
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
        parts = stratified_split(marked, label_column, ratios, seed)
        membership = {
            name: part[marker].astype(int).tolist()
            for name, part in zip(("train", "validation", "test"), parts, strict=True)
        }
        if fit_sample is not None and fit_sample < len(parts[0]):
            membership["fit"] = parts[0][marker].sample(n=fit_sample, random_state=seed).tolist()
        partitions[str(seed)] = membership
    record = {"schema_version": 1, "row_count": len(frame), "seeds": partitions}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as zipped:
        zipped.write(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())
    return path


def read_split_ids(path: Path) -> dict:
    """Read an archive produced by :func:`write_split_ids`."""
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


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
