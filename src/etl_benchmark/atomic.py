"""Publish a result file whole or not at all.

A writer fills a hidden sibling of the destination; only a finished, non-empty,
flushed file is renamed over the destination. An error or an interrupt removes
the sibling and leaves whatever the destination held before.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_path(path: str | Path) -> Iterator[Path]:
    """Yield a hidden path next to ``path``; on success it replaces ``path``.

    The sibling keeps the destination's extension so writers that infer the
    format from it (CSV, PNG) behave as they do for the real name.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.stem}.partial-{os.getpid()}{path.suffix}")
    try:
        yield partial
        if partial.stat().st_size == 0:
            raise ValueError(f"refusing to publish an empty {path.name}")
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def write_text(path: str | Path, text: str) -> Path:
    with atomic_path(path) as partial:
        partial.write_text(text)
    return Path(path)


def write_bytes(path: str | Path, data: bytes) -> Path:
    with atomic_path(path) as partial:
        partial.write_bytes(data)
    return Path(path)
