"""Fetch the three research datasets from public sources on a clean runner and verify them.

REAL needs the full Credit Card, Water Quality and Cardio files. They are public: this
module downloads each one over https from a fixed host, checks its SHA-256 against
``evidence/manifest.json`` before keeping a single byte, and refuses anything that differs
(a changed upstream file, a substituted mirror, a truncated transfer). Nothing is uploaded
and no row is printed; the report lists only URLs, hashes and sizes. Cardio is rebuilt by
``experiments/fetch_cardio.py`` from the ADBench ``.npz`` and its CSV is checked the same way.

The Credit Card file comes from the copy TensorFlow publishes for its tutorials. Its hash
equals that of the Kaggle file used for the archived runs, which also settles the open point
that the Kaggle copy could not be compared with a fresh download without a login.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import IO, Any
from urllib.parse import urlparse

from etl_benchmark.atomic import atomic_path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "verification" / "evidence" / "manifest.json"
DATA = ROOT / "data"
HOSTS = {"storage.googleapis.com", "raw.githubusercontent.com"}
MAX_BYTES = 200 * 1024 * 1024
SOURCES = {
    "credit_card": (
        "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv",
        "creditcard.csv",
    ),
    "water_quality": (
        "https://raw.githubusercontent.com/MainakRepositor/Datasets/master/water_potability.csv",
        "water_quality.csv",
    ),
}


class AcquisitionError(Exception):
    """A dataset could not be obtained exactly as the reference manifest describes it."""


def allowed(url: str) -> bool:
    parts = urlparse(url)
    return parts.scheme == "https" and parts.hostname in HOSTS


def open_url(url: str, limit: int) -> IO[bytes]:
    """The response body, cut one byte past ``limit`` so an oversized file is noticed."""
    request = urllib.request.Request(url, headers={"User-Agent": "etl-benchmark-verification"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - https only
        return io.BytesIO(response.read(limit + 1))


def run_fetch_cardio(destination: Path) -> None:
    script = ROOT / "experiments" / "fetch_cardio.py"
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True, cwd=ROOT)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _refuse_existing(destination: Path, name: str, file: str) -> None:
    if (destination / file).exists():
        raise AcquisitionError(f"{name}: {file} already exists and is not overwritten")


def acquire(
    sources: Mapping[str, tuple[str, str]],
    manifest: Mapping[str, Any],
    destination: Path,
    *,
    open_url: Callable[[str, int], IO[bytes]] = open_url,
    fetch_cardio: Callable[[Path], None] = run_fetch_cardio,
    limit: int = MAX_BYTES,
) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    datasets: dict[str, Any] = {}
    for name, (url, file) in sources.items():
        if not allowed(url):
            raise AcquisitionError(f"{name}: {url} is not allowed (https and a listed host only)")
        _refuse_existing(destination, name, file)
        data = open_url(url, limit).read(limit + 1)
        if len(data) > limit:
            raise AcquisitionError(f"{name}: the download is larger than {limit} bytes")
        if _sha256(data) != manifest[name]["sha256"]:
            raise AcquisitionError(f"{name}: the download differs from the reference checksum")
        with atomic_path(destination / file) as partial:
            partial.write_bytes(data)
        datasets[name] = {"url": url, "sha256": _sha256(data), "bytes": len(data)}
    _refuse_existing(destination, "cardio", "cardio.csv")
    fetch_cardio(destination)
    produced = destination / "cardio.csv"
    content = produced.read_bytes() if produced.is_file() else b""
    if _sha256(content) != manifest["cardio"]["sha256"]:
        produced.unlink(missing_ok=True)
        raise AcquisitionError("cardio: the rebuilt file differs from the reference checksum")
    datasets["cardio"] = {
        "url": manifest["cardio"]["source_url"],
        "sha256": _sha256(content),
        "bytes": len(content),
    }
    return {"method": "public-download", "datasets": datasets}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text())["datasets"]
    try:
        report = acquire(SOURCES, manifest, args.destination)
    except (AcquisitionError, OSError, subprocess.CalledProcessError) as exc:
        print(f"refused: {exc}")
        return 1
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"acquired {', '.join(sorted(report['datasets']))}; every checksum matches the manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
