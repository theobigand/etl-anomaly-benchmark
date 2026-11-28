"""Read the signals of the synthetic ELT and dbt pipeline back from the real backends (#164).

``e2e_check.sh`` starts MLflow, Prometheus, Loki, Tempo and Alloy and then runs this file. The
pipeline (``research/elt_pipeline.py``) runs in a container of its own with the OpenTelemetry
distribution, writes its JSON log to the volume that Alloy tails, and exports its spans to Alloy over
OTLP. Three runs are made and each is read back through the backends' query APIs:

- a successful run: one trace in Tempo with the run and both stage spans, its events in Loki found by
  the pipeline run id, and an MLflow run that carries the same trace id and pipeline run id;
- a failed run (dbt cannot be started): exit code 75 (infrastructure), an error span, ``run.failed`` in
  Loki, and an MLflow run that ended FAILED;
- a run while the collector is stopped: telemetry is lost but the pipeline still succeeds.

Metrics: the pipeline exports none today; Prometheus is checked for readiness only and the gap is
printed, not hidden. Standard library only. Synthetic data only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
COMPOSE = ["docker", "compose", "-f", os.path.join(HERE, "compose.yaml")]
NETWORK = "etl-platform_default"
LOGS = "etl-platform_etl-logs"
IMAGE = "etl-e2e-pipeline"
TEMPO = f"http://127.0.0.1:{os.environ.get('TEMPO_PORT', '53200')}"
LOKI = f"http://127.0.0.1:{os.environ.get('LOKI_PORT', '53100')}"
MLFLOW = f"http://127.0.0.1:{os.environ.get('MLFLOW_PORT', '55000')}"
PROMETHEUS = f"http://127.0.0.1:{os.environ.get('PROMETHEUS_PORT', '59090')}"
UNREACHABLE = {"POSTGRES_PASSWORD": "unused", "GRAFANA_ADMIN_PASSWORD": "unused"}


def get(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def wait_for(description: str, probe, seconds: int = 90):
    for _ in range(seconds // 3):
        found = probe()
        if found:
            return found
        time.sleep(3)
    raise AssertionError(f"not found in time: {description}")


def pipeline(run_id: str, dag_run_id: str, *, dbt: str = "/usr/local/bin/dbt") -> tuple[int, dict]:
    """Run the pipeline container; returns its exit code and the summary it printed."""
    env = {
        "ETL_LOG_DEST": "file",
        "ETL_LOG_FILE": f"/logs/{run_id}.log",
        "ETL_LOG_FORMAT": "json",
        "OTEL_SERVICE_NAME": "etl-elt-pipeline",
        "OTEL_TRACES_EXPORTER": "otlp",
        "OTEL_METRICS_EXPORTER": "none",
        "OTEL_LOGS_EXPORTER": "none",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://alloy:4318",
        "OTEL_BSP_SCHEDULE_DELAY": "500",
    }
    command = [
        "docker", "run", "--rm", "--memory", "1g", "--network", NETWORK,
        "-v", f"{os.path.dirname(HERE)}:/repo:ro", "-v", f"{LOGS}:/logs",
        *[arg for k, v in env.items() for arg in ("-e", f"{k}={v}")],
        IMAGE, "opentelemetry-instrument", "python", "/repo/research/elt_pipeline.py",
        "--out", "/tmp/out", "--link-db", "/tmp/links.sqlite", "--seed", "3", "--rows", "300",
        "--dbt", dbt, "--mlflow-url", "http://mlflow:5000",
        "--pipeline-run-id", run_id, "--dag-run-id", dag_run_id,
    ]  # fmt: skip
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        summary = json.loads(done.stdout)
    except ValueError:
        summary = {}
    return done.returncode, summary


def loki_events(run_id: str) -> dict[str, dict]:
    """Events of a run: name -> the log line as JSON, found by the pipeline run id."""
    query = f'{{job="etl-pipeline"}} | pipeline_run_id="{run_id}"'
    end = int(time.time() * 1e9)
    url = f"{LOKI}/loki/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": query, "limit": 200, "start": end - int(3600e9), "end": end + int(60e9)}
    )
    found = get(url)
    events = {}
    for stream in (found or {}).get("data", {}).get("result", []):
        for _, line in stream["values"]:
            body = json.loads(line)
            events[body["event"]] = body
    return events


def tempo_spans(trace_id: str) -> list[dict]:
    found = get(f"{TEMPO}/api/traces/{trace_id}")
    spans = []
    for batch in (found or {}).get("batches", []):
        for scope in batch.get("scopeSpans", []):
            spans += scope.get("spans", [])
    return spans


def mlflow_run(run_id: str) -> dict:
    run = get(f"{MLFLOW}/api/2.0/mlflow/runs/get?run_id={run_id}")["run"]
    return {
        "status": run["info"]["status"],
        "tags": {t["key"]: t["value"] for t in run["data"].get("tags", [])},
    }


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


def success() -> None:
    code, summary = pipeline("e2e-ok", "dag-e2e-ok")
    check(
        code == 0 and summary.get("trace_id"), "the successful run exits 0 and reports its trace id"
    )
    trace = summary["trace_id"]
    spans = wait_for(
        "the three spans in Tempo", lambda: len(tempo_spans(trace)) >= 3 and tempo_spans(trace)
    )
    names = sorted(span["name"] for span in spans)
    check(
        names == ["elt_pipeline.dbt", "elt_pipeline.elt", "elt_pipeline.run"],
        f"Tempo returns the run and both stage spans of one trace ({', '.join(names)})",
    )
    events = wait_for(
        "the run events in Loki", lambda: "run.completed" in (e := loki_events("e2e-ok")) and e
    )
    check(
        {"run.started", "stage.started", "stage.completed", "run.completed"} <= set(events),
        "Loki returns the lifecycle events found by the pipeline run id",
    )
    check(
        all(e["trace_id"] == trace and e["dag_run_id"] == "dag-e2e-ok" for e in events.values()),
        "every logged event carries the trace id and the DAG run id",
    )
    run = mlflow_run(summary["mlflow_run_id"])
    check(
        run["status"] == "FINISHED" and run["tags"]["etl.trace_id"] == trace
        and run["tags"]["etl.pipeline_run_id"] == "e2e-ok",
        "the MLflow run is FINISHED and carries the same trace id and pipeline run id",
    )  # fmt: skip


def failure() -> None:
    code, summary = pipeline("e2e-fail", "dag-e2e-fail", dbt="/nonexistent/dbt")
    check(code == 75, "a run whose dbt cannot start exits 75 (infrastructure failure)")
    events = wait_for(
        "run.failed in Loki", lambda: "run.failed" in (e := loki_events("e2e-fail")) and e
    )
    failed = events["run.failed"]
    check(
        (failed["failure_class"], failed["transient"]) == ("infrastructure", False),
        "Loki shows run.failed with its failure class and that it is not transient",
    )
    trace = failed["trace_id"]
    spans = wait_for("the error span in Tempo", lambda: tempo_spans(trace))
    errors = [s for s in spans if s.get("status", {}).get("code") in (2, "STATUS_CODE_ERROR")]
    check(bool(errors), "Tempo shows the failed stage with an error status")
    search = urllib.request.Request(
        f"{MLFLOW}/api/2.0/mlflow/runs/search",
        data=json.dumps(
            {"experiment_ids": [e["experiment_id"] for e in experiments()], "filter": "tags.`etl.pipeline_run_id` = 'e2e-fail'"}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )  # fmt: skip
    found = json.load(urllib.request.urlopen(search, timeout=10))["runs"]
    check(len(found) == 1 and found[0]["info"]["status"] == "FAILED", "the MLflow run ended FAILED")


def experiments() -> list[dict]:
    request = urllib.request.Request(
        f"{MLFLOW}/api/2.0/mlflow/experiments/search",
        data=json.dumps({"max_results": 50}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(request, timeout=10))["experiments"]


def outage() -> None:
    subprocess.run([*COMPOSE, "--profile", "observability", "stop", "alloy"], check=True,
                   capture_output=True, env={**os.environ, **UNREACHABLE})  # fmt: skip
    code, summary = pipeline("e2e-outage", "dag-e2e-outage")
    check(
        code == 0 and summary.get("elt_run_id"),
        "with the collector stopped the pipeline still succeeds",
    )


def main() -> int:
    with urllib.request.urlopen(f"{PROMETHEUS}/-/ready", timeout=10) as ready:
        check(ready.status == 200, "Prometheus is ready")
    subprocess.run(
        ["docker", "run", "--rm", "--user", "0", "-v", f"{LOGS}:/logs", IMAGE, "chown", "runner", "/logs"],
        check=True, capture_output=True,
    )  # fmt: skip
    success()
    failure()
    outage()
    print(
        "NOTE: metrics are not exported by the pipeline yet; only the trace and log paths are demonstrated"
    )
    print(
        "PASS: traces, logs and the MLflow run are retrievable and correlated; failure and outage behave as designed"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
