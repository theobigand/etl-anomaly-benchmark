"""Run the synthetic DAG on the local orchestrator and check what it reports (#157, #158).

Needs the ``orchestration`` and ``mlops`` profiles running (``platform/orchestration_check.sh``
starts them). The check goes through Airflow's REST API: task states, task logs, and the
identifiers and failure events that the platform's logging wrote there. Standard library only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

BASE = f"http://127.0.0.1:{os.environ.get('AIRFLOW_PORT', '58080')}"
DAG = "synthetic_orchestration"
MLFLOW = f"http://127.0.0.1:{os.environ.get('MLFLOW_PORT', '55000')}"
COMPOSE = ["docker", "compose", "-f", os.path.join(os.path.dirname(__file__), "compose.yaml")]
EXPECTED = {
    "bash_adopts": "success",
    "spawn_child": "success",
    "create_mlflow_run": "success",
    "with_mlflow": "success",
    "transient": "success",
    "permanent": "failed",
    "exhausted": "failed",
    "after_permanent": "upstream_failed",
}


def call(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def token() -> str:
    out = subprocess.run(
        [*COMPOSE, "--profile", "orchestration", "exec", "-T", "airflow", "cat",
         "/opt/airflow/simple_auth_manager_passwords.json.generated"],
        capture_output=True, text=True, check=True,
        env={**os.environ, "POSTGRES_PASSWORD": "unused", "GRAFANA_ADMIN_PASSWORD": "unused"},
    )  # fmt: skip
    password = json.loads(out.stdout)["admin"]
    return call("POST", "/auth/token", body={"username": "admin", "password": password})[
        "access_token"
    ]


def log_events(jwt: str, run_id: str, task: str, try_number: int) -> list[dict]:
    path = f"/api/v2/dags/{DAG}/dagRuns/{run_id}/taskInstances/{task}/logs/{try_number}"
    content = call("GET", path + "?full_content=true", jwt)["content"]
    events = []
    for item in content:
        text = item.get("event", "") if isinstance(item, dict) else str(item)
        for line in text.splitlines():
            if line.startswith("{") and '"schema_version"' in line:
                events.append(json.loads(line))
    return events


def main() -> int:
    jwt = token()
    call("PATCH", f"/api/v2/dags/{DAG}", jwt, {"is_paused": False})
    run = call("POST", f"/api/v2/dags/{DAG}/dagRuns", jwt, {"logical_date": None})
    run_id = run["dag_run_id"]
    print("dag run", run_id)
    for _ in range(90):
        state = call("GET", f"/api/v2/dags/{DAG}/dagRuns/{run_id}", jwt)["state"]
        if state in ("success", "failed"):
            break
        time.sleep(2)
    instances = call("GET", f"/api/v2/dags/{DAG}/dagRuns/{run_id}/taskInstances", jwt)
    tasks = {t["task_id"]: t for t in instances["task_instances"]}
    problems: list[str] = []

    for task, expected in EXPECTED.items():
        got = tasks[task]["state"]
        if got != expected:
            problems.append(f"{task}: state {got}, expected {expected}")
    if state != "failed":
        problems.append(f"the DAG run is {state}; a run with failed tasks must not be success")

    def events(task: str) -> list[dict]:
        return log_events(jwt, run_id, task, tasks[task]["try_number"] or 1)

    mlflow_id = events("with_mlflow")
    found = [e for e in mlflow_id if e.get("mlflow_run_id") and e.get("dag_run_id")]
    if not found:
        problems.append("with_mlflow: no event carries both mlflow_run_id and dag_run_id")
    else:
        known = call_mlflow(found[0]["mlflow_run_id"])
        if known != found[0]["mlflow_run_id"]:
            problems.append("with_mlflow: the run id of the log is not a run of the MLflow server")
    adopted = events("bash_adopts")
    if not any(e.get("dag_run_id") == run_id for e in adopted):
        problems.append(f"bash_adopts: no event carries dag_run_id {run_id}")
    child = events("spawn_child")
    ids = [e for e in child if e.get("scientific_run_id") == "synthetic-run"]
    if not (ids and all(e.get("trace_id") == "4bf92f3577b34da6a3ce929d0e0e4736" for e in ids)):
        problems.append("spawn_child: the subprocess did not inherit ETL_CORR_* identifiers")
    if not any(e.get("pipeline_run_id") == "synthetic-pipeline" for e in child):
        problems.append("spawn_child: the identifier bound by the parent is missing")

    retries = [e for e in events("transient") if e.get("event") == "stage.retrying"]
    recovered = [e for e in events("transient") if e.get("final_status") == "recovered"]
    if len(retries) != 2 or not recovered or retries[0].get("dag_run_id") != run_id:
        problems.append(f"transient: expected 2 retry events and a recovery, got {len(retries)}")
    gone = [e for e in events("exhausted") if e.get("final_status") == "exhausted"]
    tries = [e for e in events("exhausted") if e.get("event") == "stage.retrying"]
    if len(tries) != 2 or not gone or gone[0].get("failure_class") != "infrastructure":
        problems.append(f"exhausted: expected 2 retries and an exhausted failure, got {len(tries)}")
    final = [e for e in events("permanent") if e.get("event") == "run.failed"]
    if (
        not final
        or final[0].get("failure_class") != "data_quality"
        or any(e.get("event") == "stage.retrying" for e in events("permanent"))
    ):
        problems.append(
            "permanent: expected one run.failed event of class data_quality and no retry"
        )

    for problem in problems:
        print("FAIL:", problem, file=sys.stderr)
    if not problems:
        print("PASS: states, correlation and failure events seen through the orchestrator")
    return 1 if problems else 0


def call_mlflow(run_id: str) -> str:
    request = urllib.request.Request(f"{MLFLOW}/api/2.0/mlflow/runs/get?run_id={run_id}")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)["run"]["info"]["run_id"]


if __name__ == "__main__":
    sys.exit(main())
