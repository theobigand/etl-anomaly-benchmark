"""Pool of public tabular anomaly datasets: pinned download, diagnostics, provenance (issue 66).

Tier 1 is the 47 tabular real-world sets of ADBench (Han et al., NeurIPS 2022), read from the
ADBench npz packaging (BSD-2-Clause) at a pinned commit. The packaging licence is not the
licence of the underlying data: every row keeps ``underlying_terms`` as TO_CHECK and
``decision`` as PENDING until the original source has been read. Nothing is redistributed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT / "src")]

ADBENCH_COMMIT = "3dac8221081e190f157d78e93bfa8867f90d0965"
ADBENCH_BASE = f"https://raw.githubusercontent.com/Minqi824/ADBench/{ADBENCH_COMMIT}/adbench/datasets/Classical/"
HOSTS = {"raw.githubusercontent.com"}
MAX_BYTES = 100 * 1024 * 1024
_TABLE = """ALOI|Image annthyroid|Healthcare backdoor|Network breastw|Healthcare campaign|Finance
cardio|Healthcare Cardiotocography|Healthcare celeba|Image census|Sociology cover|Botany
donors|Sociology fault|Physical fraud|Finance glass|Forensic Hepatitis|Healthcare http|Web
InternetAds|Image Ionosphere|Oryctognosy landsat|Astronautics letter|Image Lymphography|Healthcare
magic.gamma|Physical mammography|Healthcare mnist|Image musk|Chemistry optdigits|Image
PageBlocks|Document pendigits|Image Pima|Healthcare satellite|Astronautics satimage-2|Astronautics
shuttle|Astronautics skin|Image smtp|Web SpamBase|Document speech|Linguistics Stamps|Document
thyroid|Healthcare vertebral|Biology vowels|Linguistics Waveform|Physics WBC|Healthcare
WDBC|Healthcare Wilt|Botany wine|Chemistry WPBC|Healthcare yeast|Biology"""
ADBENCH_TABULAR = [
    {"name": name, "file": f"{index}_{name}.npz", "domain": domain}
    for index, (name, domain) in enumerate((p.split("|") for p in _TABLE.split()), start=1)
]


class RegistryError(Exception):
    """A dataset could not be obtained or described as recorded."""


def diagnose(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """What the normalisation policy must handle for this file."""
    x, y = np.asarray(x, dtype=float), np.asarray(y)
    if not set(np.unique(y)) <= {0, 1}:
        raise ValueError("labels must be binary (0/1)")
    if y.min() == y.max():
        raise ValueError("both classes are required")
    nan = np.isnan(x)
    constant = [bool(np.all(col[~np.isnan(col)] == col[~np.isnan(col)][0])) for col in x.T]
    rows = {tuple(np.where(np.isnan(r), np.inf, r)) for r in x}
    return {
        "rows": int(x.shape[0]),
        "features": int(x.shape[1]),
        "anomalies": int(y.sum()),
        "anomaly_rate": float(y.mean()),
        "exact_duplicate_rows": int(len(x) - len(rows)),
        "constant_features": int(sum(constant)),
        "nan_cells": int(nan.sum()),
        "features_with_nan": int(nan.any(axis=0).sum()),
    }


def _allowed(url: str) -> bool:
    parts = urlparse(url)
    return parts.scheme == "https" and parts.hostname in HOSTS


def open_url(url: str, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "etl-benchmark-registry"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - https only
        return response.read(limit + 1)


def _download(url: str, opener: Callable[[str, int], bytes], limit: int) -> bytes:
    if not _allowed(url):
        raise RegistryError(f"{url} is not allowed (https and a listed host only)")
    data = opener(url, limit)
    if len(data) > limit:
        raise RegistryError(f"the download is larger than {limit} bytes")
    return data


def _publish(path: Path, data: bytes) -> Path:
    from etl_benchmark.atomic import atomic_path

    with atomic_path(path) as partial:
        partial.write_bytes(data)
    return path


def fetch(url: str, sha256: str, path: Path, opener=open_url, limit: int = MAX_BYTES) -> Path:
    data = _download(url, opener, limit)
    if hashlib.sha256(data).hexdigest() != sha256:
        raise RegistryError(f"checksum of {url} differs from the pinned one")
    return _publish(path, data)


def fetch_unpinned(url: str, path: Path, opener=open_url, limit: int = MAX_BYTES):
    """First acquisition: the digest is recorded in the inventory, then pinned."""
    data = _download(url, opener, limit)
    return _publish(path, data), hashlib.sha256(data).hexdigest()


def inventory_row(entry: dict[str, str], path: Path, url: str) -> dict[str, Any]:
    raw = path.read_bytes()
    with np.load(io.BytesIO(raw)) as archive:
        stats = diagnose(archive["X"], archive["y"])
    return {
        **entry,
        "source_url": url,
        "source_commit": ADBENCH_COMMIT,
        "packaging_licence": "BSD-2-Clause",
        "underlying_terms": "TO_CHECK",
        "decision": "PENDING",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        **stats,
    }


def build_inventory(destination: Path, opener=open_url) -> list[dict[str, Any]]:
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in ADBENCH_TABULAR:
        url = ADBENCH_BASE + entry["file"]
        path = destination / entry["file"]
        if not path.is_file():
            fetch_unpinned(url, path, opener=opener)
        rows.append(inventory_row(entry, path, url))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "data" / "adbench")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = build_inventory(args.destination)
    from etl_benchmark.atomic import atomic_path

    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    print(f"inventoried {len(rows)} datasets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
