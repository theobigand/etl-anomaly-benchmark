# ADR-0010: Grafana Alloy

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Grafana Alloy |
| Need | Collector that receives OTLP and forwards logs, metrics and traces (#162) |
| Version checked | Alloy 1.22.0 (released 2026-11-13) |
| Licence | Apache-2.0 |
| Platform | The grafana/alloy image has linux/amd64 and linux/arm64. |
| Evidence | GitHub repository metadata and latest release; docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Container in the observability profile only.

**Resources and limits.** Single collector instance; its configuration is versioned as code.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
