"""MLflow tracking with a local link table to the scientific record (#168).

MLflow records parameters, metrics and timings of a run; it never replaces the scientific evidence
system. ``LinkTable`` is a small SQLite file (standard library, works offline) that ties one
scientific run id, the MLflow run id, the pipeline and DAG run ids, the trace id and the digests of
the artifacts together. Artifacts are referenced by SHA-256 digest and are never uploaded.

``MlflowRest`` speaks the MLflow 3 REST API with ``urllib`` so the governed environment needs no
MLflow package. A run carries ``etl.kind``: ``synthetic``, ``integration`` or ``scientific``; only
a ``scientific`` run may name a scientific run id, so synthetic metrics cannot be mistaken for
results. Every tag, parameter and metric name is audited with ``obs_redaction.audit`` so ground
truth vocabulary and secrets never reach the tracking server. When the server cannot be reached
the run goes on and the link row is stored without an MLflow run id.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import obs_events
import obs_failures
import obs_redaction

KINDS = ("synthetic", "integration", "scientific")
SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    scientific_run_id TEXT,
    mlflow_run_id TEXT,
    pipeline_run_id TEXT,
    dag_run_id TEXT,
    trace_id TEXT,
    artifact_digests TEXT NOT NULL,
    created_at REAL NOT NULL
)
"""
COLUMNS = (
    "kind",
    "status",
    "scientific_run_id",
    "mlflow_run_id",
    "pipeline_run_id",
    "dag_run_id",
    "trace_id",
    "artifact_digests",
    "created_at",
)
LOG = logging.getLogger("etl.mlflow")


def sha256_file(path: Path) -> str:
    """The SHA-256 of a file, read in blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class LinkTable:
    """The link table; one row per tracked run, kept after the run ends."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with self._connect() as db:
            db.execute(SCHEMA)

    def _connect(self) -> contextlib.closing[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return contextlib.closing(db)

    def add(self, row: Mapping[str, Any]) -> int:
        values = {name: row.get(name) for name in COLUMNS}
        values["artifact_digests"] = json.dumps(row.get("artifact_digests", {}), sort_keys=True)
        marks = ", ".join("?" for _ in COLUMNS)
        with self._connect() as db, db:
            cursor = db.execute(
                f"INSERT INTO links ({', '.join(COLUMNS)}) VALUES ({marks})",
                [values[name] for name in COLUMNS],
            )
            return int(cursor.lastrowid or 0)

    def rows(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            found = db.execute("SELECT * FROM links ORDER BY link_id").fetchall()
        return [{**dict(r), "artifact_digests": json.loads(r["artifact_digests"])} for r in found]

    def find(self, **match: str) -> list[dict[str, Any]]:
        return [r for r in self.rows() if all(r.get(k) == v for k, v in match.items())]


class MlflowRest:
    """The few MLflow REST calls the linkage needs."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base = base_url.rstrip("/") + "/api/2.0/mlflow/"
        self.timeout = timeout

    def _call(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        url = self.base + path
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            url, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raise obs_failures.InfrastructureFailure(
                f"MLflow {method} {path} answered {error.code}", transient=error.code >= 500
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise obs_failures.InfrastructureFailure(f"MLflow unreachable: {error}") from None

    def experiment(self, name: str) -> str:
        """The id of the experiment ``name``, created when absent."""
        try:
            found = self._call("GET", "experiments/get-by-name?" + _query(experiment_name=name))
            return str(found["experiment"]["experiment_id"])
        except obs_failures.InfrastructureFailure as error:
            if "unreachable" in str(error):
                raise
        return str(self._call("POST", "experiments/create", {"name": name})["experiment_id"])

    def create_run(self, experiment_id: str, name: str, started_ms: int) -> str:
        body = {"experiment_id": experiment_id, "run_name": name, "start_time": started_ms}
        return str(self._call("POST", "runs/create", body)["run"]["info"]["run_id"])

    def log_batch(
        self,
        run_id: str,
        tags: Mapping[str, str],
        params: Mapping[str, str],
        metrics: Mapping[str, float],
        at_ms: int,
    ) -> None:
        body = {
            "run_id": run_id,
            "tags": [{"key": k, "value": v} for k, v in tags.items()],
            "params": [{"key": k, "value": v} for k, v in params.items()],
            "metrics": [
                {"key": k, "value": v, "timestamp": at_ms, "step": 0} for k, v in metrics.items()
            ],
        }
        self._call("POST", "runs/log-batch", body)

    def end_run(self, run_id: str, status: str, ended_ms: int) -> None:
        self._call(
            "POST", "runs/update", {"run_id": run_id, "status": status, "end_time": ended_ms}
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        found = self._call("GET", "runs/get?" + _query(run_id=run_id))["run"]
        return {
            "status": found["info"]["status"],
            "tags": {t["key"]: t["value"] for t in found["data"].get("tags", [])},
            "params": {p["key"]: p["value"] for p in found["data"].get("params", [])},
            "metrics": {m["key"]: m["value"] for m in found["data"].get("metrics", [])},
        }


def _query(**fields: str) -> str:
    return urllib.parse.urlencode(fields)


def _audited(kind: str, groups: Mapping[str, Mapping[str, Any]]) -> None:
    """Refuse names or values that reveal ground truth or hold a secret."""
    findings = []
    for group, entries in groups.items():
        findings += [
            f"{group} {f}" for f in obs_redaction.audit({k: v for k, v in entries.items()})
        ]
        findings += [
            f"{group} {k}: not a finite number"
            for k, v in entries.items()
            if group == "metrics" and not _finite(v)
        ]
    if findings:
        raise ValueError(f"{kind} run refused: " + "; ".join(findings))


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@contextlib.contextmanager
def track(
    client: MlflowRest,
    table: LinkTable,
    *,
    experiment: str,
    run_name: str,
    kind: str,
    params: Mapping[str, str] | None = None,
    metrics: Mapping[str, float] | None = None,
    artifacts: Mapping[str, Path] | None = None,
    clock: Callable[[], float] = time.time,
) -> Iterator[dict[str, Any]]:
    """Track one run on the MLflow server and store its link row when the block ends.

    The correlation identifiers bound with ``obs_events`` (scientific run, pipeline run, DAG run,
    trace) go on the MLflow run as tags and into the link row; the MLflow run id is bound for the
    block so every log line carries it. The yielded dict collects ``metrics`` the block adds and
    ``artifacts`` (name -> path) the block writes: their digests are taken when the block ends,
    and a file the block did not write is left out.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown run kind {kind!r}; choose one of {', '.join(KINDS)}")
    ids = obs_events.current()
    if kind != "scientific" and "scientific_run_id" in ids:
        raise ValueError(f"a {kind} run must not carry a scientific run id")
    digests = {name: sha256_file(path) for name, path in (artifacts or {}).items()}
    tags = {"etl.kind": kind, **{f"etl.{k}": v for k, v in ids.items()}}
    params = dict(params or {})
    result: dict[str, Any] = {"metrics": dict(metrics or {}), "artifacts": {}}
    _audited(kind, {"tags": tags, "params": params, "artifacts": digests})
    run_id: str | None = None
    status = "FINISHED"
    started = clock()
    try:
        run_id = client.create_run(client.experiment(experiment), run_name, int(started * 1000))
    except obs_failures.InfrastructureFailure as error:
        obs_failures.log_failure(LOG, "mlflow.create_run", error, final_status="degraded")
    bound = {"mlflow_run_id": run_id} if run_id else {}
    try:
        with obs_events.bind(**bound):
            yield result
    except BaseException:
        status = "FAILED"
        raise
    finally:
        ended = clock()
        refused: ValueError | None = None
        digests.update(
            {
                name: sha256_file(path)
                for name, path in result["artifacts"].items()
                if path.is_file()
            }
        )
        try:
            _audited(kind, {"metrics": result["metrics"], "artifacts": digests})
        except ValueError as error:
            refused, status, result["metrics"] = error, "FAILED", {}
        if run_id:
            digest_params = {f"digest.{n}": d for n, d in digests.items()}
            try:
                client.log_batch(
                    run_id, tags, {**params, **digest_params}, result["metrics"], int(ended * 1000)
                )
                client.end_run(run_id, status, int(ended * 1000))
            except obs_failures.InfrastructureFailure as error:
                obs_failures.log_failure(LOG, "mlflow.finish_run", error, final_status="degraded")
                status = "UNFINISHED"
        table.add(
            {
                "kind": kind,
                "status": status if run_id else "UNTRACKED",
                "mlflow_run_id": run_id,
                **{k: ids.get(k) for k in ("scientific_run_id", "pipeline_run_id", "dag_run_id")},
                "trace_id": ids.get("trace_id"),
                "artifact_digests": digests,
                "created_at": ended,
            }
        )
        if refused:
            raise refused


def verify(client: MlflowRest, row: Mapping[str, Any]) -> list[str]:
    """Problems found when the link row and the MLflow run are compared; empty means linked."""
    run_id = row.get("mlflow_run_id")
    if not run_id:
        return ["the link row has no MLflow run id"]
    run = client.get_run(run_id)
    problems = []
    for name in ("scientific_run_id", "pipeline_run_id", "dag_run_id", "trace_id"):
        if run["tags"].get(f"etl.{name}") != row.get(name):
            problems.append(f"{name} differs between the link row and the MLflow tags")
    if run["tags"].get("etl.kind") != row["kind"]:
        problems.append("kind differs between the link row and the MLflow tags")
    for name, digest in row["artifact_digests"].items():
        if run["params"].get(f"digest.{name}") != digest:
            problems.append(f"digest of {name} differs from the one on the MLflow run")
    if row["status"] != run["status"]:
        problems.append(f"status {row['status']} differs from MLflow status {run['status']}")
    return problems
