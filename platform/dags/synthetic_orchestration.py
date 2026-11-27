"""Synthetic DAG for the orchestration checks (#157, #158); no dataset, detector or science."""

import json
import urllib.request
from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

PROBE = "python /opt/airflow/probes/orch_probe.py"
MLFLOW = "http://mlflow:5000"


def mlflow_run(**_: object) -> None:
    """Create a run on the MLflow server and keep its id for the next task."""

    def post(path: str, body: dict) -> dict:
        request = urllib.request.Request(
            f"{MLFLOW}/api/2.0/mlflow/{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        return json.load(urllib.request.urlopen(request, timeout=10))

    name = "synthetic-orchestration"
    try:
        experiment = post("experiments/create", {"name": name})["experiment_id"]
    except Exception:
        found = urllib.request.urlopen(
            f"{MLFLOW}/api/2.0/mlflow/experiments/get-by-name?experiment_name={name}", timeout=10
        )
        experiment = json.load(found)["experiment"]["experiment_id"]
    run = post("runs/create", {"experiment_id": experiment})["run"]["info"]["run_id"]
    with open("/tmp/mlflow_run_id", "w") as handle:
        handle.write(run)


with DAG(
    dag_id="synthetic_orchestration",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["synthetic", "no-science"],
) as dag:
    bash_adopts = BashOperator(task_id="bash_adopts", bash_command=f"{PROBE} adopt")
    spawn_child = BashOperator(
        task_id="spawn_child",
        bash_command=(
            "export ETL_CORR_SCIENTIFIC_RUN_ID=synthetic-run "
            f"ETL_CORR_TRACE_ID=4bf92f3577b34da6a3ce929d0e0e4736; {PROBE} spawn"
        ),
    )
    create_mlflow_run = PythonOperator(task_id="create_mlflow_run", python_callable=mlflow_run)
    with_mlflow = BashOperator(
        task_id="with_mlflow",
        bash_command=f"export MLFLOW_RUN_ID=$(cat /tmp/mlflow_run_id); {PROBE} spawn",
    )
    transient = BashOperator(task_id="transient", bash_command=f"{PROBE} transient")
    permanent = BashOperator(task_id="permanent", bash_command=f"{PROBE} permanent")
    exhausted = BashOperator(task_id="exhausted", bash_command=f"{PROBE} exhausted")
    after_permanent = BashOperator(task_id="after_permanent", bash_command="echo must-not-run")
    bash_adopts >> spawn_child
    create_mlflow_run >> with_mlflow
    permanent >> after_permanent
