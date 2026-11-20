# 13. Mandatory batch-level ETL pipeline study

**Scope:** T381-T387 (promoted from optional) and T416-T430 (new). **Priority:** P0. **Milestone:** Thesis 03.
**Protocol:** [pipeline_batch_faults.md](../../verification/pipeline_batch_faults.md). **Decision record:**
[DESIGN_DECISION_2026-11-21.md](DESIGN_DECISION_2026-11-21.md).

The thesis claims to be about ETL pipelines, so a study at the unit where pipelines fail, the load
(batch), is required, not optional. T001-T415 keep their identifiers; tasks T381-T387 keep theirs and
are tracked here as mandatory instead of in the optional list of `12-extensions-and-gates.md`.

## Promoted from the optional list (same identifiers)

- [ ] T381 Build a semi-realistic ETL dataset with complete business constraints.
- [ ] T382 Integrate anonymized real ETL incidents if lawful data is available (see T426).
- [ ] T383 Add collective batch-level anomalies.
- [ ] T384 Add conditional anomalies.
- [ ] T385 Test cross-table inconsistencies.
- [ ] T386 Test schema evolution.
- [ ] T387 Test ordinary seasonal changes to estimate false alarms.

## New tasks

- [ ] T416 Preregister the batch-level protocol before any result (`verification/pipeline_batch_faults.md`).
- [ ] T417 Define the batch as the unit of detection and its profile features; keep row-level and batch-level estimands separate.
- [ ] T418 Implement the eight batch fault operators with per-batch ground truth and three severities.
- [ ] T419 Provide a competent constraint-based batch rule baseline (schema, volume, freshness, null, duplicate) built without labels.
- [ ] T420 Run learned detectors on batch profiles; record not-applicable cases (too few reference batches) as such.
- [ ] T421 Use a label-free alert-budget operating point; report false alerts per clean batch; no oracle thresholds.
- [ ] T422 Add the contaminated-reference sensitivity arm.
- [ ] T423 Run the plumbing pilot on the eight real series (descriptive, no ranking claim).
- [ ] T424 Run a variance pilot of 24 to 48 sources at batch level; estimate the between-source SD, the source-by-detector variance and the within-source ICC; then fix the sample size in a dated addendum before the confirmatory run.
- [ ] T425 Add relational sources (two or more tables with keys) and the referential-integrity operator.
- [ ] T426 Search for real ETL incident data or a partner; check the licence before any download; record the outcome even if none exists.
- [ ] T427 Tie the title, abstract and conclusion to the evidence tier: "ETL pipelines" without qualification only with real incident evidence; otherwise "controlled batch-level data-quality faults in ETL-style loads".
- [ ] T428 Check realism where natural labels exist: natural chronological series aggregated to batches against injected faults of the same mechanism; report agreement and the families it cannot cover.
- [ ] T429 Update the manuscript, slides, coverage generator and evidence index together once results exist.
- [ ] T430 Account for source families (lineage) in the coverage matrix for the batch study; never count batches, seeds or injected variants as sources.

## Acceptance criteria

- [ ] Protocol dated before the first result; the variance-pilot addendum dated before the confirmatory run.
- [ ] Every mechanism of the protocol has a measured result or a justified not-applicable record.
- [ ] Unit of inference stated beside every claim, with the number of independent sources.
- [ ] Claim wording follows the evidence tier of T427.
- [ ] Original protocols, hypotheses and sealed evidence remain intact.
