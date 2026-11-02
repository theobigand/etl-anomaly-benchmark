# Thesis remediation backlog — Volume 9: Temporal Validation and Operational Cost

**Scope:** T265–T303. **Priority:** P1. **Milestone:** Thesis 05.

Distinguish temporal proof-of-concept from broad external validity. Report fitting, inference, preprocessing, and end-to-end pipeline costs separately, with measurement provenance.

## 17. Temporal validation and drift monitoring (P1; Thesis 05)

- [ ] T265 Clarify the exact temporal dataset inventory.
- [ ] T266 Verify that timestamps support a valid chronological ordering.
- [ ] T267 Document chronological train/validation/test splits.
- [ ] T268 Distinguish covariate shift, concept drift, prevalence shift, and threshold drift.
- [ ] T269 Do not mistake prevalence-driven AP changes for model improvements.
- [ ] T270 Analyze Bank Marketing explicitly.
- [ ] T271 Analyze Credit Card Fraud, including zero fraud alerts despite high ROC-AUC.
- [ ] T272 Evaluate fixed and recalibrated thresholds.
- [ ] T273 Test label-free recalibration under temporal shift.
- [ ] T274 Evaluate drift monitors at the window level.
- [ ] T275 Measure detection delay and temporal false alerts.
- [ ] T276 Test several window sizes.
- [ ] T277 Preserve the negative per-row drift result.
- [ ] T278 Do not compare per-row and distribution-change detectors as the same task.
- [ ] T279 Reassess the LSTM pilot on Credit Card Fraud.
- [ ] T280 Do not treat transactions from unrelated customers as entity sequences without IDs.
- [ ] T281 Rerun LSTM on valid sequences if a suitable dataset is available.
- [ ] T282 Otherwise classify the pilot as inconclusive.
- [ ] T283 Optionally extend the corpus to industrial streams or sensor series.
- [ ] T284 If no extension is possible, bound RQ3 to an exploratory four-dataset study.

## 18. Training, inference, memory, and pipeline cost (P1; Thesis 05)

- [ ] T285 Measure fit time separately from scoring time.
- [ ] T286 Measure preprocessing time.
- [ ] T287 Measure Great Expectations rule-execution time.
- [ ] T288 Measure throughput in rows per second.
- [ ] T289 Measure per-batch latency.
- [ ] T290 Measure peak resident memory.
- [ ] T291 Measure full ETL pipeline cost.
- [ ] T292 Separate amortized periodic training from recurring inference.
- [ ] T293 Use stable, controlled measurement conditions.
- [ ] T294 Document exact machine hardware.
- [ ] T295 Repeat cost measurements with the quality-study training cap.
- [ ] T296 Keep uncapped scaling experiments separate.
- [ ] T297 Vary dataset row count.
- [ ] T298 Vary feature dimensionality.
- [ ] T299 Vary batch size.
- [ ] T300 Report timeouts and out-of-memory failures.
- [ ] T301 Distinguish the MLP autoencoder from heavier neural architectures.
- [ ] T302 Do not generalize a few models' cost to all deep learning.
- [ ] T303 Provide a quality-versus-cost comparison.
