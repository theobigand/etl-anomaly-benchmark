# ADR-0008: MLflow

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | MLflow |
| Need | Experiment tracking linked to the scientific record (#168) |
| Version checked | mlflow 3.18.0 (released 2026-11-04) |
| Licence | Apache-2.0 |
| Platform | Pure Python wheel, Python >=3.10; its requirements numpy <3, pandas <4 and pyarrow <27 admit the research lock's numpy 2.4.6, pandas 3.0.6 and pyarrow 25. The ghcr.io/mlflow/mlflow image has linux/amd64 and linux/arm64. |
| Evidence | PyPI metadata; GitHub repository metadata and latest release; docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Optional dependency group or container; tracking store is a local SQLite file or directory, so it works without a server. MLflow never replaces the archived JSON evidence; it links to it.

**Resources and limits.** Local file store by default; the server profile is optional.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
