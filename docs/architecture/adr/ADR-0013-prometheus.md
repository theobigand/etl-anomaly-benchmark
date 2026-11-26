# ADR-0013: Prometheus

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Prometheus |
| Need | Metric storage and alert evaluation (#162, #163) |
| Version checked | Prometheus 3.16.0 (released 2026-11-05) |
| Licence | Apache-2.0 |
| Platform | The prom/prometheus image has linux/amd64 and linux/arm64. |
| Evidence | GitHub repository metadata and latest release; docker buildx imagetools inspect (read 2026-11-26) |

**Isolation.** Container in the observability profile only; short local retention.

**Resources and limits.** Single instance; scrape interval and retention are set to fit the 16 GB host and recorded in #162.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
