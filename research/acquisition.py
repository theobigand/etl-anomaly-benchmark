"""Lightweight, reproducible acquisition of public data for the dataset strata (tasks T434-T437).

A source is a configuration entry (publisher, licence class, allowed hosts, request interval,
retry and size limits). A ``Snapshot`` fetches files of one source into
``<root>/<source>/<snapshot>/raw`` and records, for every file, its URL, SHA-256, size, the time of
collection and the observation time of the data (kept apart). A stored file is never fetched or
overwritten again; a new snapshot id gets a new directory. Sources whose licence class is not
``open`` or ``research_only`` cannot be opened. Raw data is not committed to Git.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALLOWED_CLASSES = ("open", "research_only")
USER_AGENT = "etl-benchmark-acquisition (academic research)"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")


class AcquisitionError(Exception):
    pass


def open_url(url: str, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - https, listed host
        return response.read(limit + 1)


def open_range(url: str, start: int, length: int) -> dict[str, Any]:
    """One HTTP range request; at most ``length + 1`` bytes are read whatever the server does."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Range": f"bytes={start}-{start + length - 1}"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - https, listed host
        return {
            "status": response.status,
            "content_range": response.headers.get("Content-Range"),
            "body": response.read(length + 1),
        }


_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+|\*)$")


class Snapshot:
    def __init__(
        self,
        root: Path,
        spec: dict[str, Any],
        snapshot_id: str,
        opener: Callable[[str, int], bytes] = open_url,
        sleep: Callable[[float], None] = time.sleep,
        range_opener: Callable[[str, int, int], dict[str, Any]] = open_range,
    ) -> None:
        if spec["licence_class"] not in ALLOWED_CLASSES:
            raise AcquisitionError(f"licence class {spec['licence_class']!r} is not collectable")
        self.spec, self.opener, self.sleep = spec, opener, sleep
        self.range_opener = range_opener
        self.directory = root / spec["id"] / snapshot_id
        self.raw = self.directory / "raw"
        self.manifest_path = self.directory / "manifest.json"
        self.snapshot_id = snapshot_id

    def _manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {"source": self.spec["id"], "snapshot": self.snapshot_id, "files": []}

    def _check(self, url: str, name: str) -> None:
        parts = urllib.parse.urlparse(url)
        if parts.scheme != "https":
            raise AcquisitionError(f"{url}: https only")
        if parts.hostname not in self.spec["hosts"]:
            raise AcquisitionError(f"{url}: host not listed for {self.spec['id']}")
        if not _NAME.match(name):
            raise AcquisitionError(f"{name!r} is not an allowed file name")

    def _get(self, url: str) -> bytes:
        attempts = self.spec["retries"] + 1
        for attempt in range(attempts):
            self.sleep(self.spec["min_interval"])
            try:
                body = self.opener(url, self.spec["max_bytes"])
            except OSError as error:
                last = error
                self.sleep(self.spec["min_interval"] * 2 ** (attempt + 1))
                continue
            if len(body) > self.spec["max_bytes"]:
                raise AcquisitionError(f"{url}: body larger than {self.spec['max_bytes']} bytes")
            return body
        raise AcquisitionError(f"{url}: failed after {attempts} attempts ({last!r})")

    def _get_range(self, url: str, start: int, length: int) -> dict[str, Any]:
        attempts = self.spec["retries"] + 1
        for attempt in range(attempts):
            self.sleep(self.spec["min_interval"])
            try:
                return self.range_opener(url, start, length)
            except OSError as error:
                last = error
                self.sleep(self.spec["min_interval"] * 2 ** (attempt + 1))
        raise AcquisitionError(f"{url}: failed after {attempts} attempts ({last!r})")

    def fetch_range(
        self, url: str, name: str, start: int, length: int, observed: str | None
    ) -> dict[str, Any]:
        """Store ``length`` bytes at ``start`` of a remote file if the server honours the range.

        The entry is marked ``partial``: its checksum is that of the fragment, never of the whole
        file, and it records the exact range and the total size the server reported.
        """
        from etl_benchmark.atomic import atomic_path

        self._check(url, name)
        if start < 0 or length < 1:
            raise AcquisitionError(f"{url}: range length must be positive and start non-negative")
        manifest = self._manifest()
        for entry in manifest["files"]:
            if entry["name"] == name:
                return entry
        if length > self.spec["max_bytes"]:
            raise AcquisitionError(f"{url}: range larger than {self.spec['max_bytes']} bytes")
        answer = self._get_range(url, start, length)
        if answer["status"] != 206:
            raise AcquisitionError(
                f"{url}: the server did not honour the range (status {answer['status']})"
            )
        if answer["content_range"] is None:
            raise AcquisitionError(f"{url}: no Content-Range header in the partial response")
        found = _CONTENT_RANGE.match(answer["content_range"])
        if not found:
            raise AcquisitionError(f"{url}: malformed Content-Range {answer['content_range']!r}")
        first, last_byte = int(found.group(1)), int(found.group(2))
        body = answer["body"]
        if first != start:
            raise AcquisitionError(f"{url}: unexpected offset {first}, asked for {start}")
        if len(body) != last_byte - first + 1 or len(body) > length:
            raise AcquisitionError(f"{url}: body length {len(body)} does not match the range")
        if len(body) > self.spec["max_bytes"]:
            raise AcquisitionError(f"{url}: body larger than {self.spec['max_bytes']} bytes")
        target = self.raw / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with atomic_path(target) as partial:
            partial.write_bytes(body)
        entry = {
            "name": name,
            "url": url,
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "collected": datetime.now(UTC).isoformat(timespec="seconds"),
            "observed": observed,
            "partial": True,
            "range": [first, last_byte],
            "total_bytes": None if found.group(3) == "*" else int(found.group(3)),
        }
        manifest["files"].append(entry)
        with atomic_path(self.manifest_path) as partial:
            partial.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
        return entry

    def fetch(self, url: str, name: str, observed: str | None) -> dict[str, Any]:
        """Store one file once; ``observed`` is when the data describes, not when it was fetched."""
        from etl_benchmark.atomic import atomic_path

        self._check(url, name)
        manifest = self._manifest()
        for entry in manifest["files"]:
            if entry["name"] == name:
                return entry
        body = self._get(url)
        target = self.raw / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with atomic_path(target) as partial:
            partial.write_bytes(body)
        entry = {
            "name": name,
            "url": url,
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "collected": datetime.now(UTC).isoformat(timespec="seconds"),
            "observed": observed,
        }
        manifest["files"].append(entry)
        with atomic_path(self.manifest_path) as partial:
            partial.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
        return entry

    def verify(self) -> list[str]:
        """Names of stored files that are missing or whose checksum changed."""
        bad = []
        for entry in self._manifest()["files"]:
            path = self.raw / entry["name"]
            if (
                not path.exists()
                or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
            ):
                bad.append(entry["name"])
        return bad


def gzip_prefix_lines(blob: bytes, max_output: int) -> dict[str, Any]:
    """Complete text lines at the start of a gzip stream, even if the stream is cut off.

    Reading is sequential from the stream start, so the result is a prefix sample (ordered by the
    file, not random). A line torn by the cut is dropped. ``complete`` is true only when the whole
    stream ended inside ``blob`` and ``max_output`` was not reached.
    """
    import zlib

    decoder = zlib.decompressobj(wbits=31)
    out = bytearray()
    try:
        for offset in range(0, len(blob), 4096):
            out += decoder.decompress(blob[offset : offset + 4096], max_output + 1 - len(out))
            if len(out) > max_output or decoder.unconsumed_tail:
                break
    except zlib.error as error:
        raise AcquisitionError(f"not a readable gzip stream ({error})") from error
    complete = decoder.eof and len(out) <= max_output and not decoder.unconsumed_tail
    lines = bytes(out).split(b"\n")
    tail = lines.pop()  # what follows the last newline: a torn line unless the stream ended
    if complete and tail:
        lines.append(tail)
    decoded = [line.decode("utf-8", "replace") for line in lines]
    return {"lines": decoded, "complete": complete, "output_bytes": len(out)}


def paginate(get_page: Callable[[int], list[Any]], max_pages: int) -> Iterator[list[Any]]:
    """Pages 0, 1, ... until one is empty or the page budget is spent."""
    for index in range(max_pages):
        page = get_page(index)
        if not page:
            return
        yield page


SOURCES = (
    Path(__file__).resolve().parent.parent
    / "verification/evidence/dataset_registry_v2/acquisition_sources.json"
)
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "data" / "acquired"


def plan(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Requests of a source: its fixed files, then its numbered pages (``{n}`` in the template)."""
    requests = [dict(f) for f in spec.get("files", [])]
    paged = spec.get("pages")
    if paged:
        numbers = paged.get("numbers") or range(paged["count"])
        for n in numbers:
            requests.append(
                {
                    "url": paged["url"].format(n=n, n1=n + 1, skip=n * paged["size"]),
                    "name": paged["name"].format(n=n),
                    "observed": paged.get("observed"),
                }
            )
    return requests


def _collect(node: Any, parts: list[str]) -> Iterator[Any]:
    if isinstance(node, list):
        for item in node:
            yield from _collect(item, parts)
    elif parts and isinstance(node, dict):
        if parts[0] in node:
            yield from _collect(node[parts[0]], parts[1:])
    elif not parts and node is not None:
        yield node


def expand(stage: dict[str, Any], raw: Path) -> list[dict[str, Any]]:
    """Batched requests for the distinct values at a dotted path in earlier-stage files."""
    found: set[str] = set()
    for path in sorted(raw.glob(stage["from"])):
        found.update(
            str(v) for v in _collect(json.loads(path.read_text()), stage["path"].split("."))
        )
    values = sorted({v.rsplit("/", 1)[-1] for v in found} if stage.get("short") else found)
    size = stage["batch"]
    return [
        {
            "url": stage["url"].format(ids=stage["join"].join(values[i : i + size])),
            "name": stage["name"].format(n=i // size),
            "observed": stage.get("observed"),
        }
        for i in range(0, len(values), size)
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    specs = {s["id"]: s for s in json.loads(SOURCES.read_text())["sources"]}
    snap = Snapshot(args.root, specs[args.source], args.snapshot)
    done = 0
    for request in plan(specs[args.source]):
        snap.fetch(request["url"], request["name"], request.get("observed"))
        done += 1
    for part in specs[args.source].get("ranges", []):  # bounded fragments of large files
        snap.fetch_range(
            part["url"], part["name"], part["start"], part["length"], part.get("observed")
        )
        done += 1
    for stage in specs[args.source].get("stages", []):  # later stages read earlier files
        for request in expand(stage, snap.raw):
            snap.fetch(request["url"], request["name"], request.get("observed"))
            done += 1
    print(f"{args.source}/{args.snapshot}: {done} files, mismatches {snap.verify()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
