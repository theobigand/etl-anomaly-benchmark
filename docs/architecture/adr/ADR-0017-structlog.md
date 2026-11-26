# ADR-0017: structlog

Status: accepted, 2026-11-26. The record installs nothing; #157 adds the optional group below.

| Field | Value |
|---|---|
| Component | structlog |
| Need | Structured logging on top of the standard library (#156, #157) |
| Version checked | structlog 26.1.0 |
| Licence | MIT OR Apache-2.0 |
| Platform | Pure Python wheel (py3-none-any), Python >=3.10. |
| Evidence | PyPI metadata (read 2026-11-26) |

**Isolation.** Optional dependency group `observability` (`[dependency-groups]` in `pyproject.toml`, `structlog>=26.1,<27`; #157). The central configuration works with the standard library alone and uses structlog only when it is importable. The existing logging setup lives under src/ and experiments/, which are part of the scientific fingerprint, so adoption there is a separate replay decision.

**Resources and limits.** No service. Not installed in the research lock.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
