# ADR-0002: Apache Airflow

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Apache Airflow |
| Need | Orchestration of the ETL and ELT pipelines (#148) |
| Version checked | apache-airflow 3.4.0 (released 2026-11-06) |
| Licence | Apache-2.0 |
| Platform | Python >=3.11 and !=3.15. The project README states it is tested on modern Linux distributions and recent macOS and that Linux is the production target; the apache/airflow image has linux/amd64 and linux/arm64. |
| Evidence | PyPI metadata; GitHub repository metadata and latest release; Airflow README (platform statement); docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Separate container image or virtual environment with Airflow's own constraint set, started only by the orchestration profile (#142). Never installed into the research environment.

**Resources and limits.** Standalone mode with a local executor and a bounded number of workers. A scheduler plus metadata database is the largest of the optional services; its real memory use on the 16 GB host is recorded in #142 and #151, not assumed here.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
