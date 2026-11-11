# Thesis remediation backlog — Volume 5: Operational Thresholds

**Scope:** T159–T173. **Priority:** P0/P1. **Milestone:** Thesis 02.

Keep oracle and deployable regimes distinct. A threshold selected using test labels must never be described as label-free.

## 12. Threshold calibration and label-free deployment

- [x] T159 Preserve the original prevalence-calibrated contamination protocol.
- [x] T160 Explicitly name the original protocol Oracle / Label-informed.
- [x] T161 Add a Deployment / Label-free protocol.
- [x] T162 Test thresholds based on unlabeled training-score quantiles.
- [x] T163 Test fixed alert budgets of 1% and 2%.
- [x] T164 Compare several alert budgets.
- [x] T165 Separate ranking metrics from thresholded classification metrics.
- [x] T166 Do not call a target 5% test FPR label-free if setting it requires test labels.
- [x] T167 Compare rules and ML at comparable alert constraints when feasible.
- [x] T168 Keep mandatory business rules separate from tunable statistical thresholds.
- [x] T169 Test threshold stability when anomaly prevalence changes.
- [x] T170 Test stability when the score distribution changes.
- [x] T171 Document when a fixed threshold becomes obsolete.
- [ ] T172 Promote oracle and label-free results into the main tables.
- [x] T173 Check whether saved train/test scores permit threshold recalculation without refitting.

Evidence for T159-T162 and T173: the original train-prevalence protocol is archived and unchanged
(`calibration: train_prevalence`, checked by `tests/test_artifact_lineage.py`) and named label-informed in the Methods
(the threshold reads the training labels, never the test labels); the label-free preset (fixed contamination 0.02) is a separate archived
protocol; the flag threshold is the quantile of the unlabelled fit scores, and
`research/tests/test_pool_full.py` shows for every detector of the registry that the threshold read from the saved fit scores equals a
refit, so saved scores permit recalculation without refitting. T165 is supported by the ranking/threshold separation of the metric definitions (T099) and T166 by the absence of any target test-FPR threshold described as label-free in the manuscript or slides (searched). Evidence for T168: `ALERT_BUDGETS_2026-11-11.md` (section T168) and `research/tests/test_alert_budget.py::test_no_rule_is_ever_given_a_tunable_alert_budget`; the benchmark rules are generic fitted statistical rules and contain no mandatory business rule. Evidence for T163/T164: `ALERT_BUDGETS_2026-11-11.md` and `verification/evidence/alert_budgets/` (all 17 registry detectors, 100 problems, 5 seeds, budgets 0.5/1/2/5/10%, label-free thresholds, exploratory). Evidence for T167: `MATCHED_ALERT_T167_2026-11-11.md` (rules against learned detectors at comparable observed alert volume, source-clustered, exploratory). Evidence for T169: `PREVALENCE_SHIFT_T169_2026-11-11.md`; for T170 and T171: `SCORE_SHIFT_T170_T171_2026-11-11.md`; reproducibility of the neural runs: `NEURAL_REPRODUCIBILITY_2026-11-11.md`. Readiness of T172 was assessed in `EVIDENCE_CLAIM_AUDIT_2026-11-11.md`: not ready. Still open: T172 (promotion of both
regimes to the main tables).
