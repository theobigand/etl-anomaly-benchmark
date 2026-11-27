"""Tracing of the platform tooling with OpenTelemetry, optional and failure-proof (#161).

``span`` opens a span around a unit of work (a run, a stage, a protocol execution; never a row or a
prediction) and closes it with an error status and a scrubbed exception event when the block
raises. The OpenTelemetry API is imported when it is installed (optional dependency group
``observability``, ADR-0009); without it ``span`` yields ``None`` and does nothing, so no code path
depends on it. The trace id of the current span is bound with ``obs_events`` so every log line
written inside the block carries it.

Telemetry never changes an outcome: every call into OpenTelemetry is guarded, an error there is
reported once as a warning and the work goes on, and the exception of the block itself is always
re-raised unchanged. Attributes are limited to scalars whose names and values pass the
ground-truth and secret audit of ``obs_redaction``; anything else is dropped and counted.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from typing import Any

import obs_events
import obs_redaction

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
except ImportError:  # the optional group is absent: tracing is a no-op
    trace = Status = StatusCode = None  # type: ignore[assignment]

LOG = logging.getLogger("etl.tracing")
SCOPE = "etl.platform"
MAX_TEXT = 500
_warned: set[str] = set()


def enabled() -> bool:
    """Whether the OpenTelemetry API is importable."""
    return trace is not None


def _warn(what: str, error: BaseException) -> None:
    if what not in _warned:
        _warned.add(what)
        LOG.warning("tracing %s failed and is ignored: %s", what, _text(error))


def _text(error: BaseException) -> str:
    return obs_redaction.scrub(f"{type(error).__name__}: {error}")[:MAX_TEXT]


def clean(attributes: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """The attributes that may be exported and the number dropped."""
    kept, dropped = {}, 0
    for name, value in attributes.items():
        scalar = isinstance(value, str | int | float | bool)
        if scalar and not obs_redaction.audit({name: value}):
            kept[name] = value[:MAX_TEXT] if isinstance(value, str) else value
        else:
            dropped += 1
    return kept, dropped


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Run the block inside a span named ``name``; yields the span, or ``None`` when disabled."""
    if trace is None:
        yield None
        return
    try:
        manager = trace.get_tracer(SCOPE).start_as_current_span(
            name, record_exception=False, set_status_on_exception=False
        )
        current = manager.__enter__()
    except Exception as error:
        _warn("start", error)
        yield None
        return
    trace_id = _open(current, attributes)
    try:
        with obs_events.bind(trace_id=trace_id):
            yield current
    except BaseException as error:
        _fail(current, error)
        _close(manager, type(error), error, error.__traceback__)
        raise
    _close(manager, None, None, None)


def _open(current: Any, attributes: dict[str, Any]) -> str | None:
    try:
        kept, dropped = clean(attributes)
        current.set_attributes(kept)
        if dropped:
            current.set_attribute("dropped_attributes", dropped)
        context = current.get_span_context()
        return format(context.trace_id, "032x") if context.is_valid else None
    except Exception as error:
        _warn("attributes", error)
        return None


def _fail(current: Any, error: BaseException) -> None:
    try:
        current.add_event(
            "exception",
            {"exception.type": type(error).__name__, "exception.message": _text(error)},
        )
        current.set_status(Status(StatusCode.ERROR, type(error).__name__))
    except Exception as failure:
        _warn("error status", failure)


def _close(manager: Any, kind: Any, error: Any, tb: Any) -> None:
    try:
        manager.__exit__(kind, error, tb)
    except Exception as failure:
        _warn("end", failure)
