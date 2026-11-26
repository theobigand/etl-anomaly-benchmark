# ADR-0003: Apache Spark (PySpark)

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Apache Spark (PySpark) |
| Need | A second ETL backend run in local mode for the engine comparison (#144, #150, #151) |
| Version checked | pyspark 4.3.0 |
| Licence | Apache-2.0 |
| Platform | Python >=3.11. The official Spark 4.3.0 overview states that Spark runs on Java 17, 21 and 25; the host has OpenJDK 25. PyPI publishes a source distribution only (the JVM jars are bundled), so there is no platform wheel to check. |
| Evidence | PyPI metadata; Spark 4.3.0 documentation overview (Java versions) (read 2026-11-26) |

**Isolation.** Optional dependency group plus a JVM; never part of the research lock. The pandas and PyArrow extras it needs (pandas >=2.2, pyarrow >=18) are within the research lock's versions.

**Resources and limits.** Local mode only; no cluster, no paid service. JVM memory is bounded in the runtime profile; measured use is recorded in #151.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
