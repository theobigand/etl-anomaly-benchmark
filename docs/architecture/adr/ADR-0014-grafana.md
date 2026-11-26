# ADR-0014: Grafana

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Grafana |
| Need | Operational dashboards and alerts as code (#163) |
| Version checked | Grafana 13.3.2 (released 2026-11-24) |
| Licence | AGPL-3.0 |
| Platform | The grafana/grafana image has linux/amd64 and linux/arm64. |
| Evidence | GitHub repository metadata and latest release; docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Container in the observability profile only; dashboards and data sources provisioned from files in the repository.

**Resources and limits.** Same AGPL-3.0 note as Loki. Grafana covers operational dashboards; scientific and analytical dashboards use the framework of ADR-0015.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
