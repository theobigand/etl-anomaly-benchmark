# ADR-0006: PostgreSQL

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | PostgreSQL |
| Need | Relational store for referential-integrity and transactional experiments (#145) |
| Version checked | PostgreSQL 18 (supported major; latest minor 18.7 per postgresql.org/versions.json) with psycopg 3.3.9 |
| Licence | PostgreSQL License (server); LGPL-3.0-only (psycopg) |
| Platform | The official postgres:18 image has linux/amd64 and linux/arm64/v8. psycopg is pure Python (Python >=3.10). |
| Evidence | PyPI metadata; postgresql.org versions.json; docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Container started only by the relational profile (#142); client library in an optional dependency group. The LGPL client is used unmodified through its public API.

**Resources and limits.** One small instance with bounded shared buffers. The project's versions list also shows a 19 entry; it is not selected, and the choice stays on major 18.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
