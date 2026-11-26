"""Log lifecycle: retention, storage budget, sanitized exports and shutdown flush (#160).

Rotation itself is ``obs_logging`` (``ETL_LOG_MAX_BYTES``, ``ETL_LOG_BACKUPS``). This module cleans
the numbered backups ``<log>.1``, ``<log>.2``... of one log file and nothing else:

* retention: a backup older than ``ETL_LOG_RETENTION_DAYS`` (default 14) is removed;
* storage budget: while the active file and its backups exceed ``ETL_LOG_BUDGET_BYTES`` (default
  100 MiB) the oldest backup is removed; the active file never is;
* evidence stays out: the log folder must not lie inside, or contain, a protected evidence path
  (``PROTECTED`` plus ``ETL_LOG_PROTECTED``, a ``os.pathsep`` list relative to the repository
  root), symbolic links are resolved first, and a violation raises before anything is deleted;
* exports: ``export_sanitized`` copies the lines that pass the redaction audit to a separate
  folder with a SHA-256 sidecar. An export is never overwritten and never touched by ``prune``,
  which only looks at the numbered backups of the log file.

Scientific evidence retention is a different matter and is not decided here.
``install_shutdown`` flushes and closes the logging handler when the process receives SIGTERM.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import obs_logging
import obs_redaction

#: evidence locations (relative to the repository root) that log cleanup must never reach
PROTECTED = ("docs/thesis-remediation/evidence", "verification/evidence", "experiments/results")


def _integer(env: Mapping[str, str], name: str, default: int) -> int:
    text = env.get(name, str(default)).strip()
    if not text.isdecimal() or int(text) < 1:
        raise ValueError(f"{name} must be an integer of at least 1; got {text!r}")
    return int(text)


def settings(env: Mapping[str, str]) -> dict[str, Any]:
    """Validated lifecycle settings; an invalid value is refused by name."""
    extra = tuple(p for p in env.get("ETL_LOG_PROTECTED", "").split(os.pathsep) if p)
    return {
        "retention_days": _integer(env, "ETL_LOG_RETENTION_DAYS", 14),
        "budget_bytes": _integer(env, "ETL_LOG_BUDGET_BYTES", 100 * 1024 * 1024),
        "protected": extra,
    }


def rotated(log_file: Path) -> list[Path]:
    """The numbered backups of ``log_file``, oldest first."""
    pattern = re.compile(re.escape(log_file.name) + r"\.\d+")
    found = [p for p in log_file.parent.iterdir() if pattern.fullmatch(p.name)]
    return sorted(found, key=lambda p: p.stat().st_mtime)


def _check_location(log_file: Path, root: Path, protected: tuple[str, ...]) -> None:
    folder = log_file.resolve().parent
    for relative in (*PROTECTED, *protected):
        evidence = (root / relative).resolve()
        if folder == evidence or evidence in folder.parents or folder in evidence.parents:
            raise ValueError(f"{folder} is or contains the protected evidence path {evidence}")


def prune(
    log_file: Path,
    *,
    now: datetime,
    retention_days: int,
    budget_bytes: int,
    root: Path,
    protected: tuple[str, ...] = (),
) -> list[Path]:
    """Remove expired backups, then the oldest ones until the budget is met; return them."""
    _check_location(log_file, root, protected)
    removed = []
    limit = now.timestamp() - retention_days * 86400
    for backup in rotated(log_file):
        if backup.stat().st_mtime < limit:
            backup.unlink()
            removed.append(backup)
    remaining = rotated(log_file)
    total = sum(p.stat().st_size for p in remaining) + log_file.stat().st_size
    for backup in remaining:
        if total <= budget_bytes:
            break
        total -= backup.stat().st_size
        backup.unlink()
        removed.append(backup)
    return removed


def export_sanitized(
    log_file: Path,
    folder: Path,
    *,
    now: datetime,
    root: Path,
    protected: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Copy the clean JSON lines of the backups and the active file to ``folder``."""
    _check_location(log_file, root, protected)
    if folder.resolve() == log_file.resolve().parent:
        raise ValueError("the export folder must not be the log folder")
    target = folder / f"{log_file.stem}-{now:%Y%m%d}.jsonl"
    if target.exists():
        raise ValueError(f"{target} already exists")
    kept, skipped = [], 0
    for source in (*rotated(log_file), log_file):
        for line in source.read_bytes().decode().splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if isinstance(record, dict) and not obs_redaction.audit(record):
                kept.append(line)
            else:
                skipped += 1
    folder.mkdir(parents=True, exist_ok=True)
    body = "".join(line + "\n" for line in kept).encode()
    target.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    target.with_name(target.name + ".sha256").write_text(f"{digest}  {target.name}\n")
    return {"file": str(target), "lines": len(kept), "skipped": skipped, "sha256": digest}


def shutdown() -> None:
    """Flush and close the handler of ``obs_logging`` and leave foreign handlers alone."""
    root = logging.getLogger()
    for handler in [h for h in root.handlers if hasattr(h, obs_logging.MARK)]:
        handler.flush()
        root.removeHandler(handler)
        handler.close()


def _on_terminate(signum: int, _frame: Any) -> None:
    shutdown()
    signal.signal(signum, signal.SIG_DFL)
    raise SystemExit(128 + signum)


def install_shutdown() -> None:
    """Flush the log and exit with the conventional code when the process is terminated."""
    signal.signal(signal.SIGTERM, _on_terminate)
