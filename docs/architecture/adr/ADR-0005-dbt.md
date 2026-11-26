# ADR-0005: dbt Core with dbt-duckdb

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | dbt Core with dbt-duckdb |
| Need | Declarative staging, intermediate and mart models over DuckDB (#146) |
| Version checked | dbt-core 1.12.7 and dbt-duckdb 1.11.1 |
| Licence | Apache-2.0 (dbt-core), Apache-2 (dbt-duckdb, PyPI metadata) |
| Platform | Both are pure Python (py3-none-any wheels), Python >=3.10. dbt-duckdb requires duckdb >=1.0.0 and dbt-core >=1.8.0, which the selected versions satisfy. |
| Evidence | PyPI metadata; GitHub repository metadata and latest release (read 2026-11-26) |

**Isolation.** Separate virtual environment (dbt-core pulls its own Jinja and adapter stack); it reads and writes the DuckDB file and Parquet files only, never the research environment.

**Resources and limits.** No server; runs as a command. dbt Cloud and any paid service are excluded.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
