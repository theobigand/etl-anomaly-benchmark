# Thesis remediation backlog — Volume 5: Operational Thresholds

**Scope:** T159–T173. **Priority:** P0/P1. **Milestone:** Thesis 02.

Keep oracle and deployable regimes distinct. A threshold selected using test labels must never be described as label-free.

## 12. Threshold calibration and label-free deployment

- [ ] T159 Preserve the original prevalence-calibrated contamination protocol.
- [ ] T160 Explicitly name the original protocol Oracle / Label-informed.
- [ ] T161 Add a Deployment / Label-free protocol.
- [ ] T162 Test thresholds based on unlabeled training-score quantiles.
- [ ] T163 Test fixed alert budgets of 1% and 2%.
- [ ] T164 Compare several alert budgets.
- [ ] T165 Separate ranking metrics from thresholded classification metrics.
- [ ] T166 Do not call a target 5% test FPR label-free if setting it requires test labels.
- [ ] T167 Compare rules and ML at comparable alert constraints when feasible.
- [ ] T168 Keep mandatory business rules separate from tunable statistical thresholds.
- [ ] T169 Test threshold stability when anomaly prevalence changes.
- [ ] T170 Test stability when the score distribution changes.
- [ ] T171 Document when a fixed threshold becomes obsolete.
- [ ] T172 Promote oracle and label-free results into the main tables.
- [ ] T173 Check whether saved train/test scores permit threshold recalculation without refitting.
