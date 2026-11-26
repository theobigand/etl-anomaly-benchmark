# ADR-0009: OpenTelemetry Python

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | OpenTelemetry Python |
| Need | Instrumentation and OTLP export of traces, metrics and logs (#161) |
| Version checked | opentelemetry-api, opentelemetry-sdk and opentelemetry-exporter-otlp 1.45.2 (released 2026-10-29) |
| Licence | Apache-2.0 |
| Platform | Pure Python wheels, Python >=3.10. |
| Evidence | PyPI metadata; GitHub repository metadata and latest release (read 2026-11-26) |

**Isolation.** Optional dependency group; the code paths must work with the group absent (no-op tracer) so that scientific runs never depend on it.

**Resources and limits.** Export is asynchronous and bounded; overhead is measured in #166, not assumed.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
