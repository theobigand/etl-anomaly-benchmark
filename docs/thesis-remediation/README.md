# Thesis remediation roadmap

This directory is the canonical, version-controlled backlog for strengthening the ETL anomaly-detection benchmark and its IMRaD manuscript.

- **415 individually numbered actions:** T001–T397 preserve the complete consolidated remediation checklist; T398–T415 add repository-specific verification and coordination requirements.
- **12 checklist volumes:** each task appears once and has a stable identifier.
- **24 active GitHub issues:** 16 core roadmap issues with complete checklists plus eight historical follow-ups with their original acceptance criteria; one historical planning issue is archived.
- **8 planned GitHub milestones:** ordered phases without fabricated due dates.
- **26 GitHub labels:** priority, scope, status, work kind, subject area, and historical provenance.
- **All tasks start unchecked:** documentation of a concern is not proof that it remains unresolved or that it has been fixed.

## Canonical checklists

| Volume | Task IDs | Focus |
| --- | --- | --- |
| [01 — Framing and literature](01-framing-and-literature.md) | T001–T036 | Abstract, Introduction, Related Work |
| [02 — Methods and preprocessing](02-methods-and-preprocessing.md) | T037–T070 | Detector definitions, inductive scoring, ETL preprocessing |
| [03 — Datasets, metrics, visuals](03-datasets-metrics-visuals.md) | T071–T125 | Dataset lineage, AP, figures, tables |
| [04 — Statistical validity](04-statistical-validity.md) | T126–T158 | Paired inference, clustered bootstrap, operational metrics |
| [05 — Thresholds](05-thresholds.md) | T159–T173 | Oracle versus label-free deployment |
| [06 — Fair comparisons](06-fair-comparisons.md) | T174–T198 | Rules versus ML, categorical representation |
| [07 — Fault injection](07-fault-injection.md) | T199–T233 | Training contamination, multivariate faults, ETL failures |
| [08 — Hybrids and ablations](08-hybrids-and-ablations.md) | T234–T264 | Hybrid architectures, PyOD adaptations, tuning |
| [09 — Temporal and cost](09-temporal-and-cost.md) | T265–T303 | Chronological validation, drift, throughput, memory |
| [10 — IMRaD synthesis](10-imrad-synthesis.md) | T304–T335 | Results, Discussion, Conclusion |
| [11 — Reproducibility and publication](11-reproducibility-and-publication.md) | T336–T380 | Provenance, certification, references, governance |
| [12 — Extensions and gates](12-extensions-and-gates.md) | T381–T415 | Future work and repository-specific quality gates |

## GitHub issue index

| Issue | Tasks | Priority | Planned milestone |
| --- | --- | --- | --- |
| [#88 — Framing and literature](https://github.com/theobigand/etl-anomaly-benchmark/issues/88) | T001–T036 | P0 | Thesis 01 |
| [#89 — Methods and preprocessing](https://github.com/theobigand/etl-anomaly-benchmark/issues/89) | T037–T070 | P0 | Thesis 01 |
| [#90 — Dataset inventory](https://github.com/theobigand/etl-anomaly-benchmark/issues/90) | T071–T089 | P0 | Thesis 01 |
| [#91 — AP and metrics](https://github.com/theobigand/etl-anomaly-benchmark/issues/91) | T090–T099 | P0 | Thesis 02 |
| [#92 — Figures and tables](https://github.com/theobigand/etl-anomaly-benchmark/issues/92) | T100–T125 | P0 | Thesis 01 |
| [#93 — Statistical validity](https://github.com/theobigand/etl-anomaly-benchmark/issues/93) | T126–T158 | P0 | Thesis 02 |
| [#94 — Deployment thresholds](https://github.com/theobigand/etl-anomaly-benchmark/issues/94) | T159–T173 | P0 | Thesis 02 |
| [#95 — Fair comparisons](https://github.com/theobigand/etl-anomaly-benchmark/issues/95) | T174–T198 | P1 | Thesis 03 |
| [#96 — Fault injection](https://github.com/theobigand/etl-anomaly-benchmark/issues/96) | T199–T233 | P1 | Thesis 03 |
| [#97 — Hybrids and ablations](https://github.com/theobigand/etl-anomaly-benchmark/issues/97) | T234–T264 | P1 | Thesis 04 |
| [#98 — Temporal and cost](https://github.com/theobigand/etl-anomaly-benchmark/issues/98) | T265–T303 | P1 | Thesis 05 |
| [#99 — IMRaD rewrite](https://github.com/theobigand/etl-anomaly-benchmark/issues/99) | T304–T335 | P0 | Thesis 06 |
| [#100 — Reproducibility](https://github.com/theobigand/etl-anomaly-benchmark/issues/100) | T336–T366 | P0 | Thesis 07 |
| [#101 — Academic presentation](https://github.com/theobigand/etl-anomaly-benchmark/issues/101) | T367–T380 | P0 | Thesis 06 |
| [#102 — Optional extensions](https://github.com/theobigand/etl-anomaly-benchmark/issues/102) | T381–T397 | P2 | Thesis 08 |
| [#103 — Repository-specific gates](https://github.com/theobigand/etl-anomaly-benchmark/issues/103) | T398–T415 | P1 | Thesis 07 |

## Historical issue dispositions

The original nine remaining issues were triaged individually. [#70](https://github.com/theobigand/etl-anomaly-benchmark/issues/70) was closed as a completed planning decision. [#77–#84](HISTORICAL_ISSUES.md) remain open, classified by priority and milestone, and linked to their new thematic parent issues. See the [full historical issue triage and grouping matrix](HISTORICAL_ISSUES.md). Their specific acceptance criteria remain in force; optional extensions are not release blockers.

## Milestone plan

1. **Thesis 01 — Manuscript and methods corrections:** eliminate factual errors, audit implementations and data accounting, repair figures and tables.
2. **Thesis 02 — Statistical validity and deployment thresholds:** recompute source-aware paired inference and compare oracle versus deployable thresholds.
3. **Thesis 03 — Fair baselines and ETL fault fidelity:** balance rule/model information and validate realistic injected faults.
4. **Thesis 04 — Hybrid pipelines and detector ablations:** test actual pipeline combinations, PyOD adaptations, and tuning.
5. **Thesis 05 — Temporal validity and operational cost:** validate temporal assumptions and measure separate fit, scoring, and pipeline costs.
6. **Thesis 06 — IMRaD synthesis and academic quality:** rewrite the paper against final results, verify references, and review formatting.
7. **Thesis 07 — Reproducibility and certified release:** verify evidence lineage, run applicable gates, and archive the final revision.
8. **Thesis 08 — Optional research extensions:** pursue non-blocking follow-up studies only after the core thesis is defensible.

These are planning phases, not the existing historical M00–M13 verification milestones. Do not overwrite `verification/milestones.json`.

## Priority and status

- **P0:** correctness, validity, or publication-integrity requirement; address before final scientific claims.
- **P1:** important new experiment or validation; prioritize according to available time and dependency.
- **P2:** optional extension; do not let it block the core thesis.
- **Needs audit:** a task is recorded but may already be partly implemented. Check the current repository and evidence before writing new code.
- **Done:** close a task only with reproducible evidence, or mark it not applicable with a reason.

## Completion protocol

For every task:

1. Inspect current code, paper, registered protocol, and archived results; link existing work when already sufficient.
2. State the acceptance criterion and affected files.
3. For new experiments, record a dated protocol before running; label post-hoc work exploratory.
4. Implement the smallest scientifically defensible change. Do not silently alter historical baselines, hypotheses, or negative results.
5. Run relevant tests, evidence checks, and artifact-generation steps. Record failures as well as successes.
6. Link the commit, run, table, figure, and manuscript section in the tracking issue.
7. Check the task in both its issue and canonical volume; keep the two representations synchronized.
8. Reassess affected conclusions, then close the issue only when all its tasks are resolved or explicitly dispositioned.

## Existing work and dependencies

Consult the [historical issue triage](HISTORICAL_ISSUES.md) before duplicating work. The original scope decision [#70](https://github.com/theobigand/etl-anomaly-benchmark/issues/70) is archived; the eight unresolved historical deliverables (#77–#84) remain active and cross-linked to roadmap issues. The existing verification archive, release policy, claims checks, and scientific fingerprint remain authoritative.

The proposed milestone/label/issue mapping is stored in [tracking.json](tracking.json). The synchronization workflow is idempotent and must not modify research artifacts.

## Release condition

Do not call the final thesis verified solely because checklists are complete, tests have full coverage, or a release script returns success. The final scientific review must confirm that the experiments support the stated conclusions, that dataset dependence and label access are treated correctly, that all figures and tables match their sources, and that remaining limitations are explicit.
