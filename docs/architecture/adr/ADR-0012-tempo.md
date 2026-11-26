# ADR-0012: Grafana Tempo

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Grafana Tempo |
| Need | Trace storage and query (#162) |
| Version checked | Tempo 3.1.1 (released 2026-10-21) |
| Licence | AGPL-3.0 |
| Platform | The grafana/tempo image has linux/amd64 and linux/arm64. |
| Evidence | GitHub repository metadata and latest release; docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Container in the observability profile only; local storage, short retention.

**Resources and limits.** Same AGPL-3.0 note as Loki.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
