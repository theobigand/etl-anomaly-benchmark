# Architecture decisions

Records for the optional platform components of the roadmap (`docs/roadmap/ROADMAP.md`, issue #141). They fix
versions, licences, platform support and isolation before any component is installed. Facts were read on
2026-11-26 from package metadata, repository releases, container manifests and official documentation; resource
needs that were not measured are left to the tickets named in each record.

## Decision rules

1. **The research core does not change.** `[project]` in `pyproject.toml`, `environment.yml` and the locks under
   `verification/environment/` are part of the scientific fingerprint (recipe 2) or of the release evidence. No
   component below is added to them. A component is added to an optional dependency group
   (`[dependency-groups]`, as the PyArrow group already does), a separate virtual environment, or a container
   profile, in the ticket that needs it.
2. **No technology without a functional need.** Each record names the ticket that needs the component. A
   component whose ticket is not started stays a record, not a dependency.
3. **Free and local.** Every component is free software that runs on one MacBook Air M4 (arm64, 16 GB) and on
   Linux; no paid service is used. Container images must publish linux/arm64.
4. **Modular.** The observability and industrial stacks start only from their own profiles (#142); ordinary scientific
   execution never needs them, and code that uses them must work with them absent.
5. **No silent upgrades.** A version change of any record, or of a component of the research lock, is its own
   change with its own replay or verification, never a side effect.

## Records

| Record | Component | Version checked | Licence |
|---|---|---|---|
| [ADR-0001](adr/ADR-0001-dependency-isolation.md) | Dependency isolation | - | - |
| [ADR-0002](adr/ADR-0002-airflow.md) | Apache Airflow | apache-airflow 3.4.0 (released 2026-11-06) | Apache-2.0 |
| [ADR-0003](adr/ADR-0003-spark.md) | Apache Spark (PySpark) | pyspark 4.3.0 | Apache-2.0 |
| [ADR-0004](adr/ADR-0004-duckdb.md) | DuckDB | duckdb 2.0.1 (released 2026-11-20) | MIT |
| [ADR-0005](adr/ADR-0005-dbt.md) | dbt Core with dbt-duckdb | dbt-core 1.12.7 and dbt-duckdb 1.11.1 | Apache-2.0 (dbt-core), Apache-2 (dbt-duckdb, PyPI metadata) |
| [ADR-0006](adr/ADR-0006-postgresql.md) | PostgreSQL | PostgreSQL 18 (supported major; latest minor 18.7 per postgresql.org/versions.json) with psycopg 3.3.9 | PostgreSQL License (server); LGPL-3.0-only (psycopg) |
| [ADR-0007](adr/ADR-0007-great-expectations.md) | Great Expectations | great-expectations 1.24.0 as pinned by the research lock (latest on PyPI: 1.25.0, not adopted) | Apache-2.0 |
| [ADR-0008](adr/ADR-0008-mlflow.md) | MLflow | mlflow 3.18.0 (released 2026-11-04) | Apache-2.0 |
| [ADR-0009](adr/ADR-0009-opentelemetry.md) | OpenTelemetry Python | opentelemetry-api, opentelemetry-sdk and opentelemetry-exporter-otlp 1.45.2 (released 2026-10-29) | Apache-2.0 |
| [ADR-0010](adr/ADR-0010-alloy.md) | Grafana Alloy | Alloy 1.22.0 (released 2026-11-13) | Apache-2.0 |
| [ADR-0011](adr/ADR-0011-loki.md) | Grafana Loki | Loki 3.7.10 (released 2026-11-13) | AGPL-3.0 |
| [ADR-0012](adr/ADR-0012-tempo.md) | Grafana Tempo | Tempo 3.1.1 (released 2026-10-21) | AGPL-3.0 |
| [ADR-0013](adr/ADR-0013-prometheus.md) | Prometheus | Prometheus 3.16.0 (released 2026-11-05) | Apache-2.0 |
| [ADR-0014](adr/ADR-0014-grafana.md) | Grafana | Grafana 13.3.2 (released 2026-11-24) | AGPL-3.0 |
| [ADR-0015](adr/ADR-0015-dashboard-framework.md) | Streamlit (analytical dashboards) | streamlit 1.67.0 (alternative considered: dash 4.5.1, MIT) | Apache-2.0 |
| [ADR-0016](adr/ADR-0016-drain3.md) | Drain3 | drain3 0.9.11 (last release 2022-07-17) | MIT (PyPI metadata) |
| [ADR-0017](adr/ADR-0017-structlog.md) | structlog | structlog 26.1.0 | MIT OR Apache-2.0 |

## Licence note

Grafana, Loki and Tempo are AGPL-3.0. The project runs the unmodified official images locally for personal and
academic use. Any hosted, modified or redistributed deployment needs a licence review first.

## Not verified

Resource use of each service on the 16 GB host, behaviour of the images under the Docker runtime of the host, and
mutual compatibility of the components inside one Compose network are measured in #142, #151 and #162, not
asserted here. Python 3.15 is excluded for Airflow and Great Expectations by their metadata; the project uses 3.11.
