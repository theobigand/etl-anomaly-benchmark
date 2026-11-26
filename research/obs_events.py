"""Event schema v1 and correlation identifiers for the platform's operational logs (#157).

It builds on ``obs_logging`` (#156) and needs only the standard library; structlog is used only
when ``configure_structlog`` is called and the optional ``observability`` dependency group is
installed (ADR-0017). It sits outside ``src/`` and the top-level ``experiments/`` scripts, which
are part of the scientific fingerprint (ADR-0001).

Schema v1. Every event record carries ``schema_version`` (1) and ``event``, a name from the
``EVENTS`` registry (``domain.action``, lower case, stable once published), then the correlation
identifiers that are bound, then the caller's fields. ``obs_logging`` adds ``timestamp`` (UTC),
``level``, ``logger``, ``message`` (the event name) and, for a failure, the structured
``exception``. Identifiers are optional and are never invented or generated here: a field is
present only when its value is known (``IDENTIFIERS``). A caller field may not reuse a reserved
key.

Context lives in ``contextvars``, so it follows threads that copy the context and asyncio tasks.
A child process inherits it through ``environ`` (``ETL_CORR_<NAME>``) and ``adopt``. For systems
that already export an identifier natively, ``from_environ`` adapts ``TRACEPARENT``,
``MLFLOW_RUN_ID`` and ``AIRFLOW_CTX_DAG_RUN_ID``; the ``ETL_CORR_*`` value wins.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import os
import re
from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Any

import obs_logging

SCHEMA_VERSION = 1
#: correlation identifier -> meaning
IDENTIFIERS = {
    "scientific_run_id": "scientific run (the archived run the work belongs to)",
    "mlflow_run_id": "MLflow run",
    "pipeline_run_id": "ETL pipeline run",
    "dag_run_id": "orchestrator DAG run",
    "trace_id": "distributed trace (W3C, 32 lower-case hex digits)",
    "artifact_id": "artifact (digest or registered name)",
    "telemetry_dataset_id": "telemetry dataset",
}
#: event name -> (default log level, meaning); a name is stable once published
EVENTS = {
    "run.started": ("INFO", "a run of the platform tooling began"),
    "run.completed": ("INFO", "a run finished and its outputs are written"),
    "run.failed": ("ERROR", "a run ended without completing"),
    "stage.started": ("INFO", "a stage of a run began"),
    "stage.completed": ("INFO", "a stage of a run finished"),
    "stage.failed": ("ERROR", "a stage failed; the exception is attached"),
    "artifact.written": ("INFO", "an artifact was written to its destination"),
    "subprocess.started": ("INFO", "a child process was launched"),
    "subprocess.completed": ("INFO", "a child process exited; its code is a field"),
}
NAME = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,2}")
VALUE = re.compile(r"[A-Za-z0-9._:+=\-]{1,128}")
TRACE_ID = re.compile(r"[0-9a-f]{32}")
TRACEPARENT = re.compile(r"00-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}")
PREFIX = "ETL_CORR_"
#: names of other systems -> identifier (adapters; ETL_CORR_* takes precedence)
NATIVE = {"MLFLOW_RUN_ID": "mlflow_run_id", "AIRFLOW_CTX_DAG_RUN_ID": "dag_run_id"}
#: keys a caller field may not use: the schema's own, the identifiers and every LogRecord attribute
RESERVED = (
    frozenset({"schema_version", "event", "timestamp", "level", "logger", "message"})
    | set(IDENTIFIERS)
    | obs_logging.STANDARD
)

_NONE: Mapping[str, str] = MappingProxyType({})
_context: contextvars.ContextVar[Mapping[str, str]] = contextvars.ContextVar(
    "etl_corr", default=_NONE
)


def _checked(name: str, value: Any) -> str:
    if name not in IDENTIFIERS:
        raise ValueError(f"unknown correlation identifier {name!r}")
    pattern = TRACE_ID if name == "trace_id" else VALUE
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{name} is not a valid identifier: {value!r}")
    if name == "trace_id" and value == "0" * 32:
        raise ValueError(f"{name} must not be all zeros")
    return value


def current() -> dict[str, str]:
    """The identifiers bound in this context."""
    return dict(_context.get())


@contextlib.contextmanager
def bind(**ids: str | None) -> Iterator[None]:
    """Bind identifiers for the block; ``None`` means unknown and is skipped, never invented."""
    merged = {**_context.get(), **{k: _checked(k, v) for k, v in ids.items() if v is not None}}
    token = _context.set(merged)
    try:
        yield
    finally:
        _context.reset(token)


def reset() -> None:
    """Drop every bound identifier (used after ``adopt``)."""
    _context.set(_NONE)


def build(event: str, fields: Mapping[str, Any]) -> dict[str, Any]:
    """The schema-v1 body of an event: schema, name, bound identifiers, then the fields."""
    if event not in EVENTS:
        raise ValueError(f"unregistered event {event!r}")
    for key in fields:
        if key in RESERVED:
            raise ValueError(f"reserved field {key!r}")
    return {"schema_version": SCHEMA_VERSION, "event": event, **_context.get(), **fields}


def emit(logger: logging.Logger, event: str, level: int | None = None, **fields: Any) -> None:
    """Log a registered event at the registry's level; ``exc_info=True`` attaches a failure."""
    exc_info = fields.pop("exc_info", None)
    body = build(event, fields)
    chosen = getattr(logging, EVENTS[event][0]) if level is None else level
    logger.log(chosen, event, extra=body, exc_info=exc_info)


class CorrelationFilter(logging.Filter):
    """Adds the bound identifiers to every record that does not already carry the field."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name, value in _context.get().items():
            if not hasattr(record, name):
                setattr(record, name, value)
        return True


def attach() -> None:
    """Install the filter once on the handler ``obs_logging.configure`` created."""
    for handler in logging.getLogger().handlers:
        if hasattr(handler, obs_logging.MARK) and not any(
            isinstance(f, CorrelationFilter) for f in handler.filters
        ):
            handler.addFilter(CorrelationFilter())


def environ(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """``base`` plus the bound identifiers as ``ETL_CORR_*``, for a child process."""
    return {**(base or {}), **{PREFIX + k.upper(): v for k, v in _context.get().items()}}


def from_environ(env: Mapping[str, str]) -> dict[str, str]:
    """Identifiers inherited through ``env``; invalid ``ETL_CORR_*`` values are refused by name.

    Native variables of other systems are adapted first and silently skipped when malformed, so a
    foreign value can never stop a run; the ``ETL_CORR_*`` values then override them.
    """
    found: dict[str, str] = {}
    match = TRACEPARENT.fullmatch(env["TRACEPARENT"]) if "TRACEPARENT" in env else None
    if match and match.group(1) != "0" * 32:
        found["trace_id"] = match.group(1)
    for variable, name in NATIVE.items():
        if VALUE.fullmatch(env.get(variable, "")):
            found[name] = env[variable]
    for variable, value in env.items():
        if variable.startswith(PREFIX):
            name = variable[len(PREFIX) :].lower()
            try:
                found[name] = _checked(name, value)
            except ValueError as error:
                raise ValueError(f"{variable}: {error}") from None
    return found


def adopt(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Bind the inherited identifiers for the whole process; call once at the start of a child."""
    ids = from_environ(os.environ if env is None else env)
    _context.set({**_context.get(), **ids})
    return ids


def structlog_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor: validate the event name, add schema and bound identifiers."""
    fields = {k: v for k, v in event_dict.items() if k not in ("event", "exc_info")}
    body = build(str(event_dict.get("event")), fields)
    if "exc_info" in event_dict:
        body["exc_info"] = event_dict["exc_info"]
    return body


def _to_log_kwargs(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Last processor: keep ``event`` as a field and as the message, lift ``exc_info``."""
    kwargs: dict[str, Any] = {"msg": event_dict["event"]}
    if "exc_info" in event_dict:
        kwargs["exc_info"] = event_dict.pop("exc_info")
    kwargs["extra"] = event_dict
    return kwargs


def configure_structlog() -> None:
    """Route structlog through the standard library so ``obs_logging`` formats and writes it."""
    try:
        import structlog
    except ImportError:
        raise RuntimeError(
            "structlog is not installed; install the optional group: "
            "pip install --group observability (see [dependency-groups] in pyproject.toml)"
        ) from None
    structlog.configure(
        processors=[structlog_processor, _to_log_kwargs],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
