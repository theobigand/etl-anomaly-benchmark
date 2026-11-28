# End-to-end signal path of the synthetic pipeline (#164)

`platform/e2e_check.sh` starts the `mlops` services and the `observability` services except Grafana (MLflow, Prometheus,
Loki, Tempo, Alloy), builds one small image with pinned DuckDB, PyArrow, dbt-core, dbt-duckdb and the OpenTelemetry
distribution, runs `research/elt_pipeline.py` in a container on the same network and reads the result back through the
backends' own APIs. It removes everything, volumes included. Synthetic data only; no benchmark view, no detector.

| Component | Logs | Traces | Metrics | Correlation |
|---|---|---|---|---|
| ELT pipeline (`elt_pipeline`, DuckDB stage) | JSON file tailed by Alloy into Loki, found by `pipeline_run_id` | spans `elt_pipeline.run` and `.elt` in Tempo through Alloy (OTLP) | not exported | `pipeline_run_id`, `dag_run_id`, `trace_id` on every event |
| dbt stage (`dbt_runner`) | same file, stage events | span `elt_pipeline.dbt`; dbt's own logs are not forwarded | not exported | same identifiers; the dbt invocation id is in the run record |
| MLflow | tags on the run | not instrumented | stage durations and node count as run metrics | the run carries `etl.trace_id` and `etl.pipeline_run_id`, the link row ties them |
| Airflow | task logs read through its API (`orchestration_check.sh`, #157, #158) | not exported | not exported | DAG run id in the task logs; not joined to this pipeline yet |
| Prometheus | | | ready; the pipeline exports no metric | |
| Spark, PostgreSQL, Great Expectations | not integrated | not integrated | not integrated | |

## Scenarios checked (2026-11-28, all passed)

1. Success: one trace of three spans in Tempo, the lifecycle events in Loki with the trace id and the DAG run id, and an
   MLflow run `FINISHED` carrying the same trace id and pipeline run id.
2. Failure: dbt cannot be started, so the run exits 75 (infrastructure, not transient); Loki shows `run.failed` with its
   failure class, Tempo shows the stage span with an error status and the MLflow run ends `FAILED`.
3. Telemetry outage: with Alloy stopped the pipeline still succeeds and exits 0 (tracing is failure-proof, ADR-0009).

## Not demonstrated

Metrics from the pipeline (Alloy's metrics route exists, nothing feeds it), dbt's and Airflow's native telemetry, the
Airflow DAG running this pipeline (the Airflow image has neither the `elt` nor the `dbt` environment), Grafana dashboards
(#163) and retention behaviour. #164 therefore stays open: its matrix has traces and logs for the pipeline only.
