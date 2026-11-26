# ADR-0004: DuckDB

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | DuckDB |
| Need | Local columnar ELT engine and query layer over Parquet (#143, #146) |
| Version checked | duckdb 2.0.1 (released 2026-11-20) |
| Licence | MIT |
| Platform | Python >=3.11. PyPI publishes a macosx universal2 wheel, so Apple Silicon is covered; Linux wheels are also published. |
| Evidence | PyPI metadata; GitHub repository metadata and latest release (read 2026-11-26) |

**Isolation.** Optional dependency group, imported only by the ELT modules. Parquet and Arrow reading uses the PyArrow already declared in the research dependency group.

**Resources and limits.** Embedded and single process: no server. A 2.0 release is new, so the first adoption pins it exactly and the ELT tests record the engine version in every artifact.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
