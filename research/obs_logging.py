"""Central logging configuration (#156): JSON for collection, readable console for development.

One function, ``configure``, sets up the standard ``logging`` package from environment variables and
needs no infrastructure and no third-party package. It is deliberately outside ``src/`` and the
top-level ``experiments/`` scripts: those files are part of the scientific fingerprint (ADR-0001),
so adopting this module in them is a separate, replayed decision.

Variables (all optional):

* ``ETL_LOG_LEVEL``: DEBUG, INFO, WARNING, ERROR or CRITICAL (default INFO);
* ``ETL_LOG_FORMAT``: ``console`` (default) or ``json``, one JSON object per line;
* ``ETL_LOG_DEST``: ``stderr`` (default), ``stdout`` or ``file``; ``file`` needs ``ETL_LOG_FILE``;
* ``ETL_LOG_MAX_BYTES``, ``ETL_LOG_BACKUPS``: a file log rotates at that size (default 10 MiB) and
  keeps that many numbered backups (default 5); retention and the budget are in ``obs_lifecycle``;
* ``ETL_LOG_THIRD_PARTY_LEVEL``: level of noisy libraries (default WARNING);
* ``ETL_LOG_CAPTURE_WARNINGS``: ``1`` (default) sends ``warnings.warn`` to the ``py.warnings`` log.

Level policy: a log level states how important an operational event is for whoever reads the log.
It never stands for the severity of an anomaly or a fault; that belongs to the scientific record.
DEBUG is for diagnosis, INFO for the stages of a run, WARNING for a recoverable deviation, ERROR for
a failed unit of work, CRITICAL for a run that cannot continue. Never log per row or per scored
unit: the volume is the data, and the data is serialised in the scientific artifacts, not in logs.
Timestamps are UTC.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
FORMATS = ("console", "json")
DESTINATIONS = ("stderr", "stdout", "file")
#: libraries that log more than a pipeline run needs at INFO
THIRD_PARTY = ("great_expectations", "matplotlib", "urllib3", "numba", "PIL")
MARK = "_etl_obs_handler"
STANDARD = frozenset(logging.LogRecord("n", 0, "p", 0, "m", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}
CONSOLE = "%(asctime)s [%(name)s] %(levelname)s %(message)s"


class JsonFormatter(logging.Formatter):
    """One JSON object per record: UTC timestamp, level, logger, message, extras, exception."""

    def format(self, record: logging.LogRecord) -> str:
        stamp = datetime.fromtimestamp(record.created, UTC)
        body: dict[str, Any] = {
            "timestamp": stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        body.update({k: v for k, v in sorted(record.__dict__.items()) if k not in STANDARD})
        if record.exc_info and record.exc_info[0] is not None:
            body["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stack": record.exc_text or self.formatException(record.exc_info),
            }
        return json.dumps(body, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """The readable development format, in UTC."""

    converter = staticmethod(time.gmtime)


def _choice(
    env: Mapping[str, str], name: str, allowed: tuple[str, ...], default: str, upper: bool = False
) -> str:
    value = env.get(name, default).strip()
    value = value.upper() if upper else value.lower()
    if value not in allowed:
        raise ValueError(f"{name} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def _integer(env: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    text = env.get(name, str(default)).strip()
    if not text.isdecimal() or int(text) < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}; got {text!r}")
    return int(text)


def settings(env: Mapping[str, str]) -> dict[str, Any]:
    """Validated settings from the environment; an invalid value is refused, never ignored."""
    destination = _choice(env, "ETL_LOG_DEST", DESTINATIONS, "stderr")
    path = env.get("ETL_LOG_FILE", "").strip()
    if destination == "file" and not path:
        raise ValueError("ETL_LOG_DEST=file needs ETL_LOG_FILE")
    capture = env.get("ETL_LOG_CAPTURE_WARNINGS", "1").strip()
    if capture not in ("0", "1"):
        raise ValueError(f"ETL_LOG_CAPTURE_WARNINGS must be 0 or 1; got {capture!r}")
    return {
        "level": _choice(env, "ETL_LOG_LEVEL", LEVELS, "INFO", upper=True),
        "format": _choice(env, "ETL_LOG_FORMAT", FORMATS, "console"),
        "destination": destination,
        "file": path or None,
        "max_bytes": _integer(env, "ETL_LOG_MAX_BYTES", 10 * 1024 * 1024, 1),
        "backups": _integer(env, "ETL_LOG_BACKUPS", 5, 0),
        "third_party": _choice(env, "ETL_LOG_THIRD_PARTY_LEVEL", LEVELS, "WARNING", upper=True),
        "capture_warnings": capture == "1",
    }


def _handler(chosen: Mapping[str, Any], stream: Any) -> logging.Handler:
    if chosen["destination"] == "file":
        path = Path(chosen["file"])
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            path, maxBytes=chosen["max_bytes"], backupCount=chosen["backups"], encoding="utf-8"
        )
    else:
        target = stream or (sys.stdout if chosen["destination"] == "stdout" else sys.stderr)
        handler = logging.StreamHandler(target)
    handler.setFormatter(
        JsonFormatter()
        if chosen["format"] == "json"
        else ConsoleFormatter(CONSOLE, datefmt="%H:%M:%SZ")
    )
    setattr(handler, MARK, True)
    return handler


def configure(env: Mapping[str, str] | None = None, stream: Any = None) -> dict[str, Any]:
    """Install the handler on the root logger; calling it again replaces only its own handler."""
    chosen = settings(os.environ if env is None else env)
    root = logging.getLogger()
    for existing in [h for h in root.handlers if getattr(h, MARK, False)]:
        root.removeHandler(existing)
        existing.close()
    root.addHandler(_handler(chosen, stream))
    root.setLevel(chosen["level"])
    for name in THIRD_PARTY:
        logging.getLogger(name).setLevel(chosen["third_party"])
    logging.captureWarnings(chosen["capture_warnings"])
    return chosen
