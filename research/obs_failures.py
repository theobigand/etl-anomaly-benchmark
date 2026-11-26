"""Failure taxonomy, bounded retries and visible failures for the platform tooling (#158).

Every failure belongs to one class of ``CLASSES`` and is *transient* or not. A class is never
inferred from the data: an exception the code did not classify is ``unexpected``, never a data
anomaly. ``classify`` maps an exception to ``(class, transient)``: the ``Failure`` subclasses state
theirs, ``ConnectionError``, ``TimeoutError`` and ``InterruptedError`` are transient infrastructure
failures, other ``OSError`` and ``MemoryError`` are permanent infrastructure failures.

``run_with_retries`` retries only a transient failure of a call declared ``idempotent``, at most
``Policy.max_attempts`` times with exponential backoff (``base_delay_s`` doubling up to
``max_delay_s``, no jitter, so runs stay reproducible) and within an optional total ``deadline_s``.
It logs one ``stage.retrying`` event per retry and one terminal ``stage.failed`` event, then raises
the original exception with a note; nothing is swallowed and no failure becomes a success. A call
that hangs is the callee's concern: give it its own timeout.

``log_failure`` marks an exception once logged, so several layers can report it without
duplicates. ``run_guarded`` turns an uncaught failure into the class's non-zero exit code, which is
what an orchestrator sees. ``KeyboardInterrupt`` and ``SystemExit`` always pass through.
The module sits outside the scientific fingerprint (ADR-0001).
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

import obs_events

T = TypeVar("T")

CLASSES = {
    "infrastructure": {
        "exit_code": 75,
        "description": "storage, network, memory or service failure",
    },
    "processing": {"exit_code": 1, "description": "a pipeline step failed on valid input"},
    "data_quality": {"exit_code": 65, "description": "the input violates a declared expectation"},
    "detector": {"exit_code": 2, "description": "a detector failed to fit or score"},
    "inapplicability": {"exit_code": 3, "description": "a protocol or unit does not apply"},
    "injected": {"exit_code": 4, "description": "a fault injected on purpose for a test"},
    "unexpected": {"exit_code": 70, "description": "an error nobody classified"},
}
TRANSIENT_ERRORS = (ConnectionError, TimeoutError, InterruptedError)


class Failure(Exception):
    """Base of the classified failures; ``failure_class`` and ``transient`` state the taxonomy."""

    failure_class = "unexpected"
    transient = False


class InfrastructureFailure(Failure):
    failure_class = "infrastructure"

    def __init__(self, message: str, transient: bool = True) -> None:
        super().__init__(message)
        self.transient = transient


class ProcessingFailure(Failure):
    failure_class = "processing"


class DataQualityFailure(Failure):
    failure_class = "data_quality"


class DetectorFailure(Failure):
    failure_class = "detector"


class InapplicableFailure(Failure):
    failure_class = "inapplicability"


class InjectedFailure(Failure):
    failure_class = "injected"


def classify(error: BaseException) -> tuple[str, bool]:
    """``(failure class, transient)`` of an exception."""
    if isinstance(error, Failure):
        return error.failure_class, error.transient
    if isinstance(error, TRANSIENT_ERRORS):
        return "infrastructure", True
    if isinstance(error, OSError | MemoryError):
        return "infrastructure", False
    return "unexpected", False


@dataclass(frozen=True)
class Policy:
    max_attempts: int
    base_delay_s: float
    max_delay_s: float
    deadline_s: float | None


def _number(env: Mapping[str, str], name: str, default: float | None) -> float | None:
    if name not in env:
        return default
    text = env[name].strip()
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a number greater than 0; got {text!r}")
    return value


def policy(env: Mapping[str, str]) -> Policy:
    """Retry policy from ``ETL_RETRY_*``; an invalid value is refused by name."""
    attempts = env.get("ETL_RETRY_MAX_ATTEMPTS", "3").strip()
    if not attempts.isdecimal() or int(attempts) < 1:
        raise ValueError(
            f"ETL_RETRY_MAX_ATTEMPTS must be an integer of at least 1; got {attempts!r}"
        )
    base = _number(env, "ETL_RETRY_BASE_DELAY_S", 0.5)
    cap = _number(env, "ETL_RETRY_MAX_DELAY_S", 30.0)
    if cap < base:
        raise ValueError("ETL_RETRY_MAX_DELAY_S must not be below ETL_RETRY_BASE_DELAY_S")
    return Policy(int(attempts), base, cap, _number(env, "ETL_RETRY_DEADLINE_S", None))


def log_failure(
    logger: logging.Logger,
    stage: str,
    error: BaseException,
    *,
    attempt: int = 1,
    max_attempts: int = 1,
    final_status: str = "failed",
    event: str = "stage.failed",
) -> None:
    """Log a terminal failure once; a second call for the same exception does nothing."""
    if vars(error).get("_etl_logged"):
        return
    failure_class, transient = classify(error)
    obs_events.emit(
        logger,
        event,
        stage=stage,
        attempt=attempt,
        max_attempts=max_attempts,
        failure_class=failure_class,
        transient=transient,
        retry=False,
        final_status=final_status,
        exc_info=(type(error), error, error.__traceback__),
    )
    error._etl_logged = True  # type: ignore[attr-defined]


def run_with_retries(
    call: Callable[[], T],
    *,
    stage: str,
    policy: Policy,
    idempotent: bool,
    logger: logging.Logger,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> T:
    """Run ``call``, retrying transient failures of an idempotent call within ``policy``."""
    started = clock()
    attempt = 0
    while True:
        attempt += 1
        try:
            result = call()
        except Exception as error:
            failure_class, transient = classify(error)
            status = "failed"
            if transient and idempotent:
                if attempt >= policy.max_attempts:
                    status = "exhausted"
                else:
                    delay = min(policy.base_delay_s * 2 ** (attempt - 1), policy.max_delay_s)
                    if (
                        policy.deadline_s is not None
                        and clock() - started + delay > policy.deadline_s
                    ):
                        status = "deadline"
                    else:
                        obs_events.emit(
                            logger,
                            "stage.retrying",
                            stage=stage,
                            attempt=attempt,
                            max_attempts=policy.max_attempts,
                            failure_class=failure_class,
                            transient=True,
                            retry=True,
                            delay_s=delay,
                        )
                        sleep(delay)
                        continue
            noun = "attempt" if attempt == 1 else "attempts"
            error.add_note(
                f"stage {stage} failed after {attempt} {noun} ({failure_class}, {status})"
            )
            log_failure(
                logger,
                stage,
                error,
                attempt=attempt,
                max_attempts=policy.max_attempts,
                final_status=status,
            )
            raise
        if attempt > 1:
            obs_events.emit(
                logger,
                "stage.completed",
                stage=stage,
                attempt=attempt,
                max_attempts=policy.max_attempts,
                final_status="recovered",
            )
        return result


def run_guarded(main: Callable[[], Any], *, stage: str, logger: logging.Logger) -> int:
    """Run ``main`` and return its integer result, or the exit code of the failure it raised."""
    try:
        result = main()
    except Exception as error:
        log_failure(logger, stage, error, event="run.failed")
        return CLASSES[classify(error)[0]]["exit_code"]
    return result if isinstance(result, int) else 0
