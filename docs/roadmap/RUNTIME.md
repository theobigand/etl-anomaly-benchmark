# Local runtime profiles (#142)

`platform/compose.yaml` defines nine independent profiles. Nothing starts without `--profile`, ordinary tests and the
scientific environment never need a container, and no profile depends on another. Versions follow
[`docs/architecture/adr`](../architecture/adr/README.md).

```bash
platform/smoke.sh <profile>      # start the profile alone, check it, restart it where relevant, shut it down
docker compose -f platform/compose.yaml --profile observability up -d   # POSTGRES_PASSWORD and GRAFANA_ADMIN_PASSWORD must be set
```

Every published port is bound to `127.0.0.1`; every service has a memory limit and `no-new-privileges`. Credentials
come from the environment (the smoke script generates them for the run); the file holds none. Ports can be changed
through `*_PORT` variables.

| Profile | Services | Loopback ports | Memory limit | Measured idle use | What the smoke test checks |
|---|---|---|---|---|---|
| core | stdlib tooling | none | 256 MiB | one-shot | the roadmap validator runs with no platform service |
| elt | DuckDB 2.0.1, PyArrow | none | 1 GiB | one-shot | a Parquet file is written and queried |
| etl | PySpark 4.3.0, Java runtime | none | 2 GiB | one-shot | a local-mode DataFrame is counted |
| aiops | Drain3 0.9.11 | none | 512 MiB | one-shot | a log template is mined |
| analytics | Streamlit 1.67.0 | 58501 | 512 MiB | not measured | the health endpoint answers |
| relational | PostgreSQL 18.7 | 55432 | 512 MiB | 28 MiB | insert, select, data kept after a restart, an invalid query fails |
| mlops | MLflow 3.18.0 (SQLite, local artifacts) | 55000 | 1.5 GiB | about 1 GiB | experiment created, kept after a restart |
| orchestration | Airflow 3.4.0, standalone, LocalExecutor | 58080 | 3 GiB | about 920 MiB | metadata database and scheduler report healthy |
| observability | Prometheus 3.16.0, Loki 3.7.10, Tempo 3.1.1, Alloy 1.22.0, Grafana 13.3.2 | 59090, 53100, 53200, 52345, 54317, 54318, 53000 | 2.5 GiB together | about 570 MiB together | all five ready; a log sent to Alloy over OTLP is found in Loki; Grafana provisions three data sources |

Measured on Docker Desktop 29.9.3 (Compose 5.7.0, aarch64, 8 GiB assigned to the virtual machine), 2026-11-27, with
images pulled for linux/arm64. Image sizes: Airflow 3.24 GB, Grafana 1.89 GB, PySpark tool image 1.49 GB, MLflow
1.37 GB, the others under 1 GB. Run one service profile at a time on a 16 GB host; two together (for example
observability and relational) fit.

## Findings

- MLflow was killed for memory at 768 MiB with the default worker count; it now runs one worker with a 1.5 GiB limit and an explicit allowed-hosts list.
- Loki, Tempo and Alloy images have no shell or HTTP client, so Compose health checks are not possible for them; readiness is probed from the host by the smoke script.
- Tempo 3.x rejects the `compactor` block of earlier versions and runs standalone without an external queue; the configuration is minimal.
- Alloy forwards OTLP logs to Loki and traces to Tempo; the log path is proven end to end, the trace path is configured but not yet exercised.
- Airflow uses its own embedded database in standalone mode; sharing the relational profile is left to #148.

## Orchestration check (#157, #158)

`platform/orchestration_check.sh` starts the orchestration and mlops profiles together, triggers the synthetic DAG
`synthetic_orchestration` (`platform/dags`, tasks in `platform/probes`; no dataset, detector or scientific run) through
Airflow's REST API, waits for the run and checks what Airflow itself reports: task states, task logs and the structured
events in them. It exits non-zero on any deviation. It takes about 25 seconds from a cold start. The `research/` folder
is mounted read-only in the Airflow container, so the platform modules that run are the ones of the working tree.

| Check | Result |
|---|---|
| Airflow exports `AIRFLOW_CTX_DAG_RUN_ID` to a task; the platform adapts it | the events of the task carry the real `dag_run_id` |
| `ETL_CORR_*` reaches a subprocess of a task | the child logs the parent's `scientific_run_id`, `trace_id` and `pipeline_run_id` |
| A run created on the MLflow server is adopted through `MLFLOW_RUN_ID` | the logged `mlflow_run_id` is found on the server and sits beside the `dag_run_id` |
| Transient failure within the limit | task `success`; two `stage.retrying` events and a `recovered` completion |
| Transient failure beyond the limit | task `failed`; `exhausted` failure of class `infrastructure` after two retries |
| Permanent failure | task `failed` with exit code 65; one `run.failed` event of class `data_quality`; no retry |
| Task downstream of the failure | `upstream_failed` |
| DAG run with failed tasks | `failed`, never `success` |

Not done here: DAG content for the roadmap (#148, #164); trace delivery to Tempo; the `TRACEPARENT` path through a real
tracing service; Compose on Linux; a restart of Airflow during a run.
