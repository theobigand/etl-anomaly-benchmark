# ADR-0015: Streamlit (analytical dashboards)

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Streamlit (analytical dashboards) |
| Need | Scientific and portfolio dashboards over the archived evidence (#185 to #190) |
| Version checked | streamlit 1.67.0 (alternative considered: dash 4.5.1, MIT) |
| Licence | Apache-2.0 |
| Platform | Pure Python wheel, Python >=3.11. |
| Evidence | PyPI metadata (read 2026-11-26) |

**Isolation.** Optional dependency group; the dashboards read committed evidence files only and never run an experiment.

**Resources and limits.** Chosen as the lighter option for read-only analysis pages that need no callback graph; Dash remains the fallback if a page needs fine-grained interaction. Reconfirm when #185 starts.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
