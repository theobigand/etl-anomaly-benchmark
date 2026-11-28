"""The synthetic ELT and dbt run as one tracked pipeline (#143, #146, #164; ADR-0004, 0005, 0008).

``run_pipeline`` runs ``elt_duckdb.run_elt`` and then ``dbt_runner.run_dbt`` and ties both to the
platform's tracking and event infrastructure instead of keeping a second registry:

- the correlation identifiers of ``obs_events`` (``pipeline_run_id``, ``dag_run_id`` when an
  orchestrator gives one, ``trace_id`` from the span) are bound for the whole run, so every log line
  and every child process carries them;
- each stage emits ``stage.started`` and ``stage.completed`` and is retried by
  ``obs_failures.run_with_retries`` (both stages are idempotent: the ELT output is replaced
  atomically and dbt rebuilds its target), which logs ``stage.retrying`` and a terminal
  ``stage.failed``; ``run.started``, ``run.completed`` and ``run.failed`` bracket the run;
- with an MLflow URL the run is an ``integration`` run on the server (``mlflow_link.track``): its
  parameters, metrics and the digests of the ELT and dbt manifests are recorded, and a link row ties
  the MLflow run, the pipeline run, the DAG run, the trace and the digests together; without a URL,
  or when the server cannot be reached, the link row is stored untracked and the work continues;
- a failed stage fails the run: the exception is re-raised after the failure was logged and the run
  was ended ``FAILED``, so a failed transformation never looks successful.

Synthetic data only: no benchmark view, no detector, no scientific result. Names and values pass the
ground-truth and secret audit of ``obs_redaction`` before they leave the process. The module sits
outside the scientific fingerprint.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import dbt_runner
import elt_duckdb
import mlflow_link
import obs_events
import obs_failures
import obs_logging
import obs_redaction
import obs_tracing

LOG = logging.getLogger("etl.elt_pipeline")
EXPERIMENT = "elt-synthetic"


def default_run_id(seed: int, rows: int) -> str:
    return f"elt-{seed}-{rows}"


def _stage(name: str, call, policy: obs_failures.Policy) -> tuple[Any, float]:
    """Run one stage under the retry policy with its events and span; return result and seconds."""
    started = time.monotonic()
    with obs_tracing.span(f"elt_pipeline.{name}"):
        obs_events.emit(LOG, "stage.started", stage=name)
        result = obs_failures.run_with_retries(
            call, stage=name, policy=policy, idempotent=True, logger=LOG
        )
        seconds = time.monotonic() - started
        obs_events.emit(LOG, "stage.completed", stage=name, duration_s=round(seconds, 3))
    return result, seconds


def run_pipeline(
    out: Path,
    seed: int,
    rows: int,
    *,
    link_db: Path,
    dbt: str | None = None,
    mlflow_url: str | None = None,
    pipeline_run_id: str | None = None,
    dag_run_id: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = os.environ if env is None else env
    policy = obs_failures.policy(environment)
    run_id = pipeline_run_id or default_run_id(seed, rows)
    ids = {"pipeline_run_id": run_id, **({"dag_run_id": dag_run_id} if dag_run_id else {})}
    table = mlflow_link.LinkTable(link_db)
    client = mlflow_link.MlflowRest(mlflow_url) if mlflow_url else None
    out = Path(out)
    with obs_events.bind(**ids), obs_tracing.span("elt_pipeline.run", seed=seed, rows=rows):
        obs_events.emit(LOG, "run.started", seed=seed, rows=rows)
        tracking = (
            mlflow_link.track(
                client,
                table,
                experiment=EXPERIMENT,
                run_name=run_id,
                kind="integration",
                params={"seed": str(seed), "rows": str(rows)},
            )
            if client
            else contextlib.nullcontext({"metrics": {}, "artifacts": {}})
        )
        try:
            with tracking as tracked:
                manifest, elt_seconds = _stage(
                    "elt", lambda: elt_duckdb.run_elt(out, seed, rows), policy
                )
                record, dbt_seconds = _stage("dbt", lambda: dbt_runner.run_dbt(out, dbt), policy)
                tracked["artifacts"].update(
                    {
                        "elt_manifest": out / "manifest.json",
                        "dbt_run": out / "dbt" / "dbt_run.json",
                    }
                )
                tracked["metrics"].update(
                    {
                        "elt_duration_s": elt_seconds,
                        "dbt_duration_s": dbt_seconds,
                        "dbt_nodes": float(len(record["nodes"])),
                    }
                )
                for name in ("manifest.json", "dbt/dbt_run.json"):
                    digest = mlflow_link.sha256_file(out / name)
                    with obs_events.bind(artifact_id=digest):
                        obs_events.emit(LOG, "artifact.written", artifact=name)
                summary = {
                    "pipeline_run_id": run_id,
                    "dag_run_id": dag_run_id,
                    "elt_run_id": manifest["run_id"],
                    "dbt_invocation_id": record["invocation_id"],
                    "mlflow_run_id": obs_events.current().get("mlflow_run_id"),
                    "trace_id": obs_events.current().get("trace_id"),
                }
        except BaseException as error:
            failure_class, transient = obs_failures.classify(error)
            obs_events.emit(LOG, "run.failed", failure_class=failure_class, transient=transient)
            vars(error)["_etl_logged"] = True  # run_guarded must not report it a second time
            if not client:
                table.add(_untracked_row("FAILED", {}))
            raise
        if not client:
            table.add(
                _untracked_row(
                    "UNTRACKED",
                    {
                        "elt_manifest": mlflow_link.sha256_file(out / "manifest.json"),
                        "dbt_run": mlflow_link.sha256_file(out / "dbt" / "dbt_run.json"),
                    },
                )
            )
        obs_events.emit(
            LOG,
            "run.completed",
            elt_run_id=summary["elt_run_id"],
            dbt_invocation_id=summary["dbt_invocation_id"],
        )
    return summary


def _untracked_row(status: str, digests: Mapping[str, str]) -> dict[str, Any]:
    ids = obs_events.current()
    return {
        "kind": "integration",
        "status": status,
        "mlflow_run_id": None,
        **{k: ids.get(k) for k in ("scientific_run_id", "pipeline_run_id", "dag_run_id")},
        "trace_id": ids.get("trace_id"),
        "artifact_digests": dict(digests),
        "created_at": time.time(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--link-db", type=Path, required=True)
    parser.add_argument("--dbt")
    parser.add_argument("--mlflow-url")
    parser.add_argument("--pipeline-run-id")
    parser.add_argument("--dag-run-id")
    args = parser.parse_args(argv)
    obs_logging.configure()
    obs_events.attach()
    obs_redaction.attach()

    def run() -> int:
        summary = run_pipeline(
            args.out,
            args.seed,
            args.rows,
            link_db=args.link_db,
            dbt=args.dbt,
            mlflow_url=args.mlflow_url,
            pipeline_run_id=args.pipeline_run_id,
            dag_run_id=args.dag_run_id,
        )
        print(json.dumps(summary, indent=1, sort_keys=True))
        return 0

    return obs_failures.run_guarded(run, stage="elt_pipeline", logger=LOG)


if __name__ == "__main__":
    raise SystemExit(main())
