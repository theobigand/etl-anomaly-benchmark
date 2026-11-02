# Thesis remediation backlog — Volume 12: Extensions and Repository-Specific Controls

**Scope:** T381–T415. **Priority:** P2 for optional research, P1 for additional verification controls. **Milestones:** Thesis 08 and Thesis 07.

Optional work must not delay core corrections. Existing issues and verification records are authoritative for work already completed. Use new follow-up protocols and evidence rather than rewriting historical records.

## 22. Optional research extensions (P2; Thesis 08)

- [ ] T381 Build a semi-realistic ETL dataset with complete business constraints.
- [ ] T382 Integrate anonymized real ETL incidents if lawful data is available.
- [ ] T383 Add collective batch-level anomalies.
- [ ] T384 Add conditional anomalies.
- [ ] T385 Test cross-table inconsistencies.
- [ ] T386 Test schema evolution.
- [ ] T387 Test ordinary seasonal changes to estimate false alarms.
- [ ] T388 Study model aging.
- [ ] T389 Compare retraining policies.
- [ ] T390 Study the maintenance burden of domain rules.
- [ ] T391 Measure human investigation time per alert.
- [ ] T392 Evaluate anomaly explanations.
- [ ] T393 Study quality, cost, memory, and interpretability trade-offs.
- [ ] T394 Test stability by dataset size and dimensionality.
- [ ] T395 Test high-cardinality categorical variables.
- [ ] T396 Propose a complete hybrid ETL monitoring architecture.
- [ ] T397 Validate the architecture across several scenarios.

## 23. Additional repository-specific follow-up and quality gates (P1; Thesis 07)

- [ ] T398 Audit the current repository before work; mark already-satisfied tasks with linked evidence rather than duplicating implementations.
- [ ] T399 Cross-reference existing open coverage issues #77–#84 and planning issue #70.
- [ ] T400 Maintain one canonical task identifier across documentation, issues, experiments, and manuscript change logs.
- [ ] T401 Require objective acceptance evidence for closing each new issue.
- [ ] T402 Audit skipped detectors, failed runs, and denominator changes in all result summaries.
- [ ] T403 Investigate the 14 failed end-to-end measurements on seven datasets (existing issue #79).
- [ ] T404 Replay large-pool archives against the current scientific fingerprint (existing issue #82).
- [ ] T405 Assess the 94 injection-ineligible tables using appropriate alternate protocols, without relaxing eligibility after inspecting outcomes (existing issue #77).
- [ ] T406 Expand temporal coverage only when a real and defensible time variable exists (existing issue #78).
- [ ] T407 Coordinate training-cap and tuning ablations with existing issue #80.
- [ ] T408 Coordinate isolated cost measurement with existing issue #81.
- [ ] T409 Coordinate source-overlap, label-rule sensitivity, seeds, and formal inference with existing issue #83.
- [ ] T410 Coordinate independent attestation, Linux lock, and mutation-survivor review with existing issue #84.
- [ ] T411 Review branch-protection requirements without changing protection policy without owner approval.
- [ ] T412 Add automated checks that manuscript claims cannot silently become stale relative to archived artifacts.
- [ ] T413 Quantify uncertainty around fault-severity response curves and document multiple-testing implications.
- [ ] T414 Predefine failure-to-score, abstention, and detector-timeout handling in comparative summaries.
- [ ] T415 Produce a final claim-to-evidence traceability matrix linking every key conclusion to a run, table, figure, and protocol.
