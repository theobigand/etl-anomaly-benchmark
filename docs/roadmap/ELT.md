# Local ELT through DuckDB over Parquet (#143)

`research/elt_duckdb.py` is a synthetic end-to-end ELT run: seeded synthetic orders are written as Parquet, transformed
by DuckDB and aggregated by SQL into a mart, and a manifest records the provenance. It reads no benchmark view, fits
no detector and changes no ledger count or scientific result. DuckDB is pinned exactly (`duckdb==2.0.1`, ADR-0004) in
the optional `elt` dependency group, outside `[project]`, so the scientific fingerprint and the governed environment are
unchanged.

```
uv venv ~/.cache/etl-elt-venv && uv pip install --python ~/.cache/etl-elt-venv/bin/python duckdb==2.0.1 pyarrow pytest
~/.cache/etl-elt-venv/bin/python research/elt_duckdb.py --out /tmp/elt-demo --seed 0 --rows 1000
```

## Stages and provenance

| Stage | Content | Written to |
|---|---|---|
| raw | synthetic orders: nested struct and list columns, a UTC timestamp, a null column | `<out>/raw/orders.parquet` |
| staging | the same rows through DuckDB, ordered by key, nesting kept | `<out>/staging/orders.parquet` |
| marts | orders, units and amount per customer tier, by SQL | `<out>/marts/orders_by_tier.parquet` |

`<out>/manifest.json` holds the DuckDB and PyArrow versions, the seed, the SQL hash, the SHA-256 and row count of every
output, the logical schema of each output, the schema-preservation result and a run identifier derived from them. The
output directory is written next to its final name and renamed, so a failed run leaves nothing. Directories inside
`verification/evidence`, `experiments/results` or `docs/thesis-remediation/evidence` are refused before anything is
written. One DuckDB thread keeps the output bytes reproducible: two runs with one seed give identical files.

## Verified Arrow and Parquet behaviour (DuckDB 2.0.1, PyArrow 26)

- Struct, list, timestamp with time zone, integer width and the null type survive Parquet and DuckDB unchanged.
- Two differences are expected and recorded, not corrected: the list element field is named `item` in memory and
  `element` once it has been through Parquet, and DuckDB marks columns that contain no nulls as required.
  `logical_schema` ignores exactly these two and detects any change of type, width, time zone or field name.
- Nothing is flattened: nested columns stay nested in staging and are queried with struct and list functions.
- DuckDB 2.0 rejects the old `x -> expr` lambda; the SQL uses `lambda x: expr`.

## dbt over the ELT output (#146)

`platform/dbt_orders` is a dbt Core project (dbt-core 1.12.7 and dbt-duckdb 1.11.1, ADR-0005) that reads `raw/orders.parquet`
of an ELT run as a source and builds `stg_orders` and `int_order_units` (views) and `mart_tier_summary` (table). Its tests
are `not_null`, `unique` and `accepted_values` on the keys and tiers, plus a singular test that the dbt mart equals the
DuckDB mart of the same run (`marts/orders_by_tier.parquet`). `research/dbt_runner.py` runs `dbt build` and
`dbt docs generate` through a separate dbt executable (`DBT_BIN` or `--dbt`), so dbt's Jinja and adapter stack never
enter the scientific or ELT environment.

```
uv venv ~/.cache/etl-dbt-venv && uv pip install --python ~/.cache/etl-dbt-venv/bin/python \
    dbt-core==1.12.7 dbt-duckdb==1.11.1 duckdb==2.0.1 pyarrow      # the `dbt` and `elt` groups of pyproject.toml
~/.cache/etl-elt-venv/bin/python research/elt_duckdb.py --out /tmp/elt-demo --seed 0 --rows 1000
python research/dbt_runner.py --elt-out /tmp/elt-demo --dbt ~/.cache/etl-dbt-venv/bin/dbt
```

`<out>/dbt/dbt_run.json` holds the dbt invocation id, the dbt version, the status of every node, the parents of every
node (the lineage the generated docs draw), the SHA-256 of `manifest.json`, `run_results.json` and `catalog.json` and the
`run_id` of the ELT run it was built on. A failed node, a missing result file or a failed docs generation is an error
that names the node and writes no record. `make verify-platform` runs the real dbt build in CI (job `platform`).

## One tracked pipeline: ELT, dbt, MLflow and events

`research/elt_pipeline.py` runs the ELT and then the dbt project as one pipeline and reuses the platform's tracking
instead of adding a registry: the correlation identifiers of `obs_events` (`pipeline_run_id`, `dag_run_id` when an
orchestrator gives one, `trace_id` from the span) are bound for the whole run; every stage emits `stage.started` and
`stage.completed`, is retried by `obs_failures.run_with_retries` when the failure is transient (both stages are
idempotent) and ends in `run.completed` or `run.failed` with its failure class. ELT and dbt errors belong to the failure
taxonomy: a failed model or ELT step is `processing`, failing data tests are `data_quality`, a missing executable or
dependency is a permanent `infrastructure` failure and a dbt timeout a transient one.

With `--mlflow-url` the run is an `integration` run on the MLflow server (`mlflow_link.track`): seed and rows as
parameters, stage durations and node count as metrics, the SHA-256 of `manifest.json` and `dbt/dbt_run.json` as digests,
and a link row ties the MLflow run, pipeline run, DAG run, trace and digests together. Without a URL, or when the
server cannot be reached, the link row is stored untracked and the work continues. A failed stage fails the run and the
MLflow run; nothing is reported as successful.

```
python research/elt_pipeline.py --out /tmp/elt-demo --link-db /tmp/links.sqlite --seed 0 --rows 1000 \
    --dbt ~/.cache/etl-dbt-venv/bin/dbt [--mlflow-url http://127.0.0.1:55000] [--dag-run-id <id>]
```

## Not done here

The Airflow task (#148) and the observability backends of the signal path (#164) are separate issues. DuckDB is not installed in the governed scientific environment; the tests of this module
are not collected there. `make verify-platform` runs them in an environment with the `elt` group, and CI runs it in the `platform` job.
