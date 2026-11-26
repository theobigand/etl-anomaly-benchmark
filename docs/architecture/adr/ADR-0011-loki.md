# ADR-0011: Grafana Loki

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Grafana Loki |
| Need | Log storage and query (#162) |
| Version checked | Loki 3.7.10 (released 2026-11-13) |
| Licence | AGPL-3.0 |
| Platform | The grafana/loki image has linux/amd64 and linux/arm64. |
| Evidence | GitHub repository metadata and latest release; docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Container in the observability profile only; filesystem storage, single binary mode.

**Resources and limits.** AGPL-3.0 applies to network use of a modified version. The project runs the unmodified official image locally for personal and academic use and does not redistribute or modify it; this must be rechecked before any hosted or distributed deployment. Retention is bounded (#160).

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
