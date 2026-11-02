# Thesis remediation backlog — Volume 7: Training Contamination and Fault Injection

**Scope:** T199–T233. **Priority:** P1. **Milestone:** Thesis 03.

All revised injections must be validated against independent ground truth. Preserve the original injection protocol and report new runs as exploratory addenda.

## 14a. Contaminated training data and robust statistics (P1; Thesis 03)

- [ ] T199 Reproduce the Z-score recall collapse on UCI tables.
- [ ] T200 Test whether sentinel values and scaling errors in training caused the collapse.
- [ ] T201 Compare the original standard Z-score.
- [ ] T202 Compare Z-score after invalid-value filtering.
- [ ] T203 Compare robust median/MAD scoring.
- [ ] T204 Optionally compare winsorized statistics.
- [ ] T205 Apply coherent training conditions to other affected detectors.
- [ ] T206 Test several levels of training contamination.
- [ ] T207 Measure both recall and false positives after filtering.
- [ ] T208 Do not use test anomaly labels to select preprocessing filters.

## 14b. Marginally controlled multivariate anomalies (P1; Thesis 03)

- [ ] T209 Generate anomalies that violate dependencies between features.
- [ ] T210 Avoid making all joint anomalies obvious univariate extremes.
- [ ] T211 Verify marginal distributions before and after injection.
- [ ] T212 Test a central-marginal-range construction, such as 10th–90th percentiles, where feasible.
- [ ] T213 Do not assume central-range constraints alone guarantee pure joint anomalies.
- [ ] T214 Add automated checks for violations of the joint relationship.
- [ ] T215 Measure univariate detector performance on the corrected injections.
- [ ] T216 Compare original and revised injections.
- [ ] T217 Preserve the historical baseline results.

## 14c. Realistic ETL fault taxonomy (P1; Thesis 03)

- [ ] T218 Inject decimal-parsing failures.
- [ ] T219 Inject data-type violations.
- [ ] T220 Inject malformed text fields.
- [ ] T221 Inject unseen categorical values.
- [ ] T222 Inject out-of-domain business values.
- [ ] T223 Inject cross-column inconsistencies.
- [ ] T224 Inject unit-conversion errors.
- [ ] T225 Inject approximate or fuzzy duplicates.
- [ ] T226 Inject primary-key and foreign-key violations.
- [ ] T227 Inject invalid dates and timezone conversions.
- [ ] T228 Inject batch-level spikes in missingness.
- [ ] T229 Inject missing or duplicated batches.
- [ ] T230 Evaluate multiple fault severities.
- [ ] T231 Evaluate multiple injection prevalences.
- [ ] T232 Automatically validate the injected ground truth.
- [ ] T233 Report simple synthetic faults separately from realistic ETL incident scenarios.
