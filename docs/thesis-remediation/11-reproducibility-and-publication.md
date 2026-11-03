# Thesis remediation backlog — Volume 11: Reproducibility and Academic Integrity

**Scope:** T336–T380. **Priority:** P0. **Milestones:** Thesis 06 and Thesis 07.

Keep the existing verification/milestones.json historical evidence unchanged. New protocols and results require new versioned evidence; no historical run may be silently restamped. Licenses and institutional requirements must be verified rather than assumed.

## 20. Reproducibility, provenance, and certified release (P0; Thesis 07)

- [ ] T336 Add the exact repository URL to the manuscript.
- [ ] T337 Create an immutable release corresponding to the final paper.
- [ ] T338 Assign a permanent DOI if an archival deposit is possible.
- [ ] T339 Verify the commit matching the certified results.
- [ ] T340 Do not assume an older suggested commit hash matches the future final release.
- [ ] T341 Record exact Python, PyOD, scikit-learn, PyTorch, and Great Expectations versions.
- [ ] T342 Document processor, memory, operating system, and architecture for each environment.
- [ ] T343 Verify the Credit Card Fraud dataset SHA-256 hash.
- [ ] T344 Compare against a newly obtained authorized copy if possible.
- [ ] T345 Otherwise preserve the explicit provenance limitation.
- [ ] T346 Publish a dataset manifest.
- [ ] T347 Publish experimental configurations.
- [ ] T348 Publish random seeds and partitions.
- [ ] T349 Publish raw scores or sufficient intermediates for statistical reproduction.
- [ ] T350 Bind each result to code, configuration, and environment.
- [x] T351 Add leakage regression tests.
- [ ] T352 Add injection-generator validation tests.
- [ ] T353 Add inductive-scoring tests.
- [ ] T354 Add metric-consistency tests.
- [ ] T355 Add determinism tests where feasible.
- [ ] T356 Test no-positive datasets, constant columns, missingness, unseen categories, and small samples.
- [ ] T357 Do not present 100% test coverage as proof of scientific validity.
- [ ] T358 Preserve originally preregistered protocols and hypotheses.
- [ ] T359 Record follow-up experiments as dated exploratory addenda.
- [ ] T360 Never retroactively rewrite hypotheses after observing results.
- [ ] T361 Verify the actual make verify targets and release script before invoking them.
- [ ] T362 Run appropriate tests and checks after modifications.
- [ ] T363 Regenerate tables and figures from certified artifacts.
- [ ] T364 Validate hashes of changed artifacts.
- [ ] T365 Produce a new release consistent with the final PDF.
- [ ] T366 Provide a reduced-cost reproduction path for readers.

Evidence for T351: [pool-preparation validation](POOL_PREPROCESSING_VALIDATION_2026-11-03.md),
implementation `edc3592`, evaluation-feature/label perturbations and three injected
leakage defects. Existing core split/label contracts are retained. This check does
not certify historical pool results or complete the remaining release tasks.

## 21. Bibliography, ethics, and academic presentation (P0; Thesis 06)

- [ ] T367 Verify every bibliographic entry.
- [ ] T368 Correct incomplete or mischaracterized references.
- [ ] T369 Add recent references only after primary-source verification.
- [ ] T370 Standardize bibliography formatting.
- [ ] T371 Add code and data availability statements.
- [ ] T372 Add a funding declaration based on the actual funding situation.
- [ ] T373 Add an accurate competing-interests declaration.
- [ ] T374 Describe dataset governance.
- [ ] T375 Verify licenses before claiming all data can be freely redistributed.
- [ ] T376 Document restrictions on Kaggle and other datasets.
- [ ] T377 Describe limitations of anonymization in banking data.
- [ ] T378 Comply with applicable institutional disclosure and research-integrity policies.
- [ ] T379 Verify IEEE formatting against the master's thesis submission requirements.
- [ ] T380 Proofread the final PDF for symbols, tables, captions, equations, pagination, and references.
