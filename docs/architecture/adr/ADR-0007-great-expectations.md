# ADR-0007: Great Expectations

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Great Expectations |
| Need | Declarative validation in the pipelines and the declarative-versus-learned comparison (#147) |
| Version checked | great-expectations 1.24.0 as pinned by the research lock (latest on PyPI: 1.25.0, not adopted) |
| Licence | Apache-2.0 |
| Platform | Already part of the research environment on macOS arm64 and Linux; pure Python. |
| Evidence | PyPI metadata; verification/environment locks (read 2026-11-26) |

**Isolation.** No change: it stays in the research lock at the pinned version. Upgrading it would change the scientific fingerprint and is excluded from this decision.

**Resources and limits.** No new service. Upgrade to 1.25.0 is deferred to an explicit dependency ticket with a replay of the archived experiments.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
