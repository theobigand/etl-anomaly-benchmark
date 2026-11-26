"""Allowlist-first fields, secret redaction and ground-truth isolation for operational logs (#159).

``attach`` installs a filter on the handler that ``obs_logging.configure`` created, so every record
is cleaned before any formatter, file, export or dashboard sees it:

* extra fields: only the names in ``ALLOWED`` and only scalar values (text up to 500 characters)
  survive; anything else is removed and counted in ``dropped_fields``, so raw rows, held-out labels
  and unknown attributes cannot be logged by accident;
* text (message, string fields, exception message, stack): secrets (``password=``, tokens, bearer
  credentials, credentials in URLs, cloud keys) and the vocabulary of the injected-fault ground
  truth (``ground_truth``, ``y_true``, ``label``, ``injected``, ``held-out`` and similar) are
  replaced by ``[REDACTED]``, so detector-accessible telemetry cannot name the injected fault.

``audit`` and ``audit_vocabulary`` are the leakage audit over names, paths, attributes and ids.
The module sits outside the scientific fingerprint (ADR-0001) and uses the standard library only.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from typing import Any

import obs_events
import obs_logging

MARK = "[REDACTED]"
LIMIT = 500
#: extra field names a record may carry; everything else is dropped
ALLOWED = (
    frozenset({"schema_version", "event", "dropped_fields"})
    | frozenset(obs_events.IDENTIFIERS)
    | frozenset(
        {
            "stage",
            "rows",
            "code",
            "attempt",
            "max_attempts",
            "retry",
            "duration_ms",
            "failure_class",
            "final_status",
        }
    )
)
#: ground-truth vocabulary in free text and paths (whole words, so ``labelled`` is untouched)
GROUND_TRUTH = re.compile(
    r"(?i)ground[_-]?truth|y_true|is_anomal\w*|anomaly_label|fault_mask|injected|injection"
    r"|held[_-]?out|holdout|\blabels?\b"
)
#: the same concepts inside field, event and identifier names (``label_id`` counts)
GROUND_TRUTH_NAME = re.compile(
    r"(?i)ground[_-]?truth|y_true|is_anomal|anomaly_label|fault_mask|inject|held[_-]?out|holdout|label"
)
KEYED = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|apikey|authorization|credential)s?\b"
    r"\s*[=:]\s*\S+"
)
PATTERNS = (
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), MARK),
    (KEYED, rf"\1={MARK}"),
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@"), f"{MARK}@"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), MARK),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), MARK),
)


def scrub(text: str) -> str:
    """Replace secrets and ground-truth vocabulary in ``text``."""
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return GROUND_TRUTH.sub(MARK, text)


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, bool | int | float | str)


class RedactionFilter(logging.Filter):
    """Clean one record in place; it must see the fields other filters add, so it runs last."""

    runs_last = True

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = scrub(record.getMessage()), ()
        dropped = 0
        for name in [n for n in record.__dict__ if n not in obs_logging.STANDARD]:
            value = record.__dict__[name]
            if name not in ALLOWED or not _scalar(value):
                delattr(record, name)
                dropped += 1
            elif isinstance(value, str):
                value = scrub(value)
                setattr(record, name, value if len(value) <= LIMIT else value[:LIMIT] + "...")
        if dropped:
            record.dropped_fields = dropped
        if record.exc_info and any(record.exc_info):
            kind, value, trace = record.exc_info
            clean = type(kind.__name__, (Exception,), {})(scrub(str(value)))
            record.exc_text = scrub(logging.Formatter().formatException(record.exc_info))
            record.exc_info = (type(clean), clean, trace)
        if record.stack_info:
            record.stack_info = scrub(record.stack_info)
        return True


def attach() -> None:
    """Install the filter once on the handler ``obs_logging.configure`` created."""
    for handler in logging.getLogger().handlers:
        if hasattr(handler, obs_logging.MARK) and not any(
            isinstance(f, RedactionFilter) for f in handler.filters
        ):
            handler.addFilter(RedactionFilter())


def audit(record: Mapping[str, Any]) -> list[str]:
    """Findings in a log record: names, text values, paths and ids that leak or hold a secret."""
    findings = []
    for name, value in record.items():
        if GROUND_TRUTH_NAME.search(name):
            findings.append(f"{name}: field name names a ground-truth concept")
        elif isinstance(value, str):
            if GROUND_TRUTH.search(value):
                findings.append(f"{name}: {value!r} names a ground-truth concept")
            elif scrub(value) != value:
                findings.append(f"{name}: {value!r} contains a secret")
    return findings


def audit_vocabulary(
    events: Iterable[str] | None = None, identifiers: Iterable[str] | None = None
) -> list[str]:
    """Findings in the registered event names and correlation identifier names."""
    findings = []
    for kind, names in (
        ("event", obs_events.EVENTS if events is None else events),
        ("identifier", obs_events.IDENTIFIERS if identifiers is None else identifiers),
    ):
        findings += [
            f"{kind} {name!r} names a ground-truth concept"
            for name in names
            if GROUND_TRUTH_NAME.search(name)
        ]
    return findings
