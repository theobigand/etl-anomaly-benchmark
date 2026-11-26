# ADR-0016: Drain3

Status: accepted for planning, 2026-11-26. Nothing is installed or imported by this record.

| Field | Value |
|---|---|
| Component | Drain3 |
| Need | Log template extraction, evaluated against alternatives (#171) |
| Version checked | drain3 0.9.11 (last release 2022-07-17) |
| Licence | MIT (PyPI metadata) |
| Platform | Pure Python; PyPI lists no Python requirement. |
| Evidence | PyPI metadata; GitHub repository metadata and latest release (read 2026-11-26) |

**Isolation.** Evaluation only, in an optional group, behind an interface that lets a simple template miner replace it.

**Resources and limits.** The last release is more than four years old; adoption is conditional on #171 showing it works on the project's logs with the pinned Python and NumPy. If it does not, the decision is to implement a small in-repository template miner instead.

**Consequences.** The research core (`[project]`, `environment.yml`, the locks) is untouched; the component enters only through an optional dependency group, a separate environment or a container profile, in the ticket that needs it. Versions are rechecked at that moment. No claim of adoption by third parties is made.
