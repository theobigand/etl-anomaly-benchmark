"""Synthetic, non-scientific tasks for the orchestration checks (#157, #158).

Runs inside the orchestrator container with ``research/`` on the path. Every command logs JSON lines
through the platform's own logging, event and redaction modules, so what the orchestrator stores is
what the platform produces. It reads no dataset and runs no detector.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

import obs_events as oe
import obs_failures as of
import obs_logging as ol
import obs_redaction as orr

LOG = logging.getLogger("etl.orchestration_probe")


def setup() -> None:
    ol.configure({**os.environ, "ETL_LOG_FORMAT": "json", "ETL_LOG_DEST": "stdout"})
    oe.attach()
    orr.attach()


def adopt() -> None:
    """A child task: take the identifiers the orchestrator exported and report them."""
    setup()
    oe.adopt()
    oe.emit(LOG, "stage.completed", stage="adopt")


def spawn() -> None:
    """A parent task: bind identifiers, start a child with ``ETL_CORR_*``, report its exit code."""
    setup()
    oe.adopt()
    with oe.bind(pipeline_run_id=os.environ.get("PROBE_PIPELINE_RUN_ID", "synthetic-pipeline")):
        oe.emit(LOG, "subprocess.started", stage="spawn")
        child = subprocess.run(
            [sys.executable, __file__, "adopt"],
            env=oe.environ(os.environ),
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stdout.write(child.stdout)
        oe.emit(LOG, "subprocess.completed", stage="spawn", code=child.returncode)
        if child.returncode:
            raise SystemExit(child.returncode)


def transient() -> None:
    """Fails twice with a transient error, then succeeds: retries are visible and bounded."""
    setup()
    oe.adopt()
    calls = {"n": 0}

    def flaky() -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise of.InfrastructureFailure("synthetic link down")

    of.run_with_retries(
        flaky,
        stage="transient",
        policy=of.Policy(3, 0.1, 1.0, None),
        idempotent=True,
        logger=LOG,
    )


def exhausted() -> None:
    """Always fails with a transient error: retries stop at the limit and the task must fail."""
    setup()
    oe.adopt()

    def down() -> None:
        raise of.InfrastructureFailure("synthetic link down")

    of.run_with_retries(
        down,
        stage="exhausted",
        policy=of.Policy(3, 0.1, 1.0, None),
        idempotent=True,
        logger=LOG,
    )


def permanent() -> None:
    """Fails with a data-quality error: not retried, and the task must fail with its exit code."""
    setup()
    oe.adopt()

    def bad() -> None:
        raise of.DataQualityFailure("synthetic invalid input")

    raise SystemExit(of.run_guarded(bad, stage="permanent", logger=LOG))


COMMANDS = {
    "adopt": adopt,
    "spawn": spawn,
    "transient": transient,
    "exhausted": exhausted,
    "permanent": permanent,
}

if __name__ == "__main__":
    COMMANDS[sys.argv[1]]()
