# Thesis remediation backlog — Volume 2: Methods and Preprocessing

**Scope:** T037–T070. **Status:** open until individually verified. **P0:** mandatory scientific correction.

Preserve the registered protocols and sealed baselines. Check pinned library versions and source code before modifying or describing behavior.

## 04. Detector definitions and inductive scoring (P0; Thesis 01)

- [x] T037 Correct the Z-score normality notation to 3 sigma in LaTeX.
- [x] T038 Correct the IQR normality notation to approximately 2.7 sigma in LaTeX.
- [x] T039 Define Z-score mathematically and document the decision threshold.
- [x] T040 Define the IQR rule, boundaries, and alert-rate implications.
- [x] T041 Describe the existing Great Expectations baseline as a generic automated statistical rule suite.
- [x] T042 Document not-null checks and train-derived 0.1%/99.9% numerical bounds.
- [x] T043 Do not present this suite as representative of domain-informed declarative rules.
- [x] T044 Explain that train-fitted percentile bounds constitute a univariate statistical detector.
- [x] T045 Correct the theoretical description of COPOD.
- [x] T046 Distinguish COPOD's theoretical formulation from scoring in the pinned PyOD version.
- [x] T047 Inspect the pinned PyOD source before describing how ECOD/COPOD combine dimensions.
- [x] T048 Add a complete table of all 17 detectors.
- [x] T049 Record family, implementation origin, library version, accepted data types, preprocessing, and training caps.
- [x] T050 Record score definition, direction, threshold, and implementation adaptations.
- [x] T051 Document the modifications to ECOD, COPOD, DIF, and VAE.
- [x] T052 Explain the requirement for inductive per-row scoring in ETL inference.
- [x] T053 Test whether a row's score is invariant to other rows in the test batch where claimed.
- [x] T054 Distinguish bug fixes from algorithm-changing adaptations.
- [x] T055 Check neural convergence, stopping rules, epochs, and numerical failures.

Evidence for T037–T044: [rule-definition audit and validation](RULE_DEFINITIONS_2026-11-03.md).
T037/T038 were already implemented; the audit confirms them without a duplicate notation patch.

Evidence for T045–T047 and T051–T054: [pinned-source inductive detector audit](INDUCTIVE_DETECTORS_2026-11-03.md).
These are verified descriptions of existing adaptations; no equivalence to unmodified PyOD is claimed.

Evidence for T048–T050: [comparable detector inventory](../../verification/detector_inventory.md), checked against the runtime registry by `tests/test_detector_inventory.py`.

Partial evidence for T055 (reopened 2026-11-07): [neural convergence audit](NEURAL_CONVERGENCE_AUDIT_2026-11-07.md). Convergence is verified only for the typed-benchmark autoencoder; for the five other neural detectors the archives hold no convergence diagnostics. The task closes only with a prospective campaign that retains them, or an explicit not-applicable justification.

## 05. ETL preprocessing and leakage controls (P0; Thesis 01)

- [x] T056 Document extraction, validation, transformation, imputation, encoding, fitting, scoring, and alert order.
- [x] T057 Add a diagram of the standard ETL path.
- [x] T058 Show the typed-fault evaluation as a separate path.
- [x] T059 Explain that standard transformation may remove exact duplicates before detection.
- [x] T060 Explain that injected duplicates remain available to the typed detector benchmark.
- [x] T061 Report transform_dedup as a distinct baseline when appropriate.
- [ ] T062 Verify all preprocessing is fitted on training data only.
- [ ] T063 Verify test statistics never influence preprocessing or fitting.
- [x] T064 Test for label leakage in preprocessing decisions.
- [x] T065 Record columns removed, retained, or transformed.
- [x] T066 Explain the impact of excluding text and categorical features.
- [x] T067 Explain how median imputation affects missing-value detection.
- [x] T068 Document normalization and scaling.
- [x] T069 Verify consistent anomaly-score orientation.
- [x] T070 Identify comparisons where families receive unequal input information.

Evidence for T064: [constructed regressions and injected defects](POOL_PREPROCESSING_VALIDATION_2026-11-03.md),
implementation `edc3592`. The tests detect historical label-dependent filtering and
protect the explicit new path. T062/T063 remain open for historical partition
recovery and replay; testing the defect does not resolve every existing pipeline.

Status of T062/T063 (2026-11-19): the labelled pool (100 problems, 17 detectors, 5 seeds) was replayed on the train-only path and paired with the archived results ([protocol and results](POOL_TRAIN_ONLY_REPLAY_2026-11-18.md)). The corrected path is train-only by construction and tested; the historical path is not, and the replay shows its effect on AP is small for most problems and above 0.05 for 4-12%. The injection, synthetic and temporal studies were not replayed, so both items stay open.

Audit of the paths that were not replayed (2026-11-19, code read, no new run):

- Typed injection (`research/typed_run.py`, `research/injection.py`, `research/typed_benchmark.py`): the detectors are fitted on the training partition only and the contamination comes from the training partition, but the carrier is built before the split from the whole table: continuous columns, incomplete rows and duplicates removed, a seeded subsample above the row cap, only the normal class for labelled tables, and the injected magnitudes use the mean and standard deviation of the whole carrier. This defines the benchmark population and the fault, it is not detector preprocessing; it is nevertheless not train-only and a train-only variant (statistics from training rows) has not been run.
- Synthetic and multi-schema generators: the data are generated, so there is no external table to preprocess; the split is by identity group and the detectors are fitted on the training partition.
- Temporal studies: the split is chronological, the detectors are fitted on the oldest rows; the clean-row and label handling is the one of the historical normalisation.

T062 and T063 therefore stay open: the prospective labelled-pool path is train-only and replayed, the typed-injection carrier statistics are an acknowledged pre-split step, and no replay of the injection or temporal studies on a train-only carrier exists.

Evidence for T056–T061: [standard and typed ETL paths](ETL_PATHS_2026-11-07.md), aligned with `pipeline.py`, `typed_benchmark.py` and the baseline tests.

Evidence for T065–T070: [preprocessing and information audit](PREPROCESSING_INFORMATION_AUDIT_2026-11-07.md), with the historical/prospective boundary retained.

T055 (2026-11-19): closed on the evidence of [the convergence audit](NEURAL_CONVERGENCE_AUDIT_2026-11-07.md) and [the budget probe](NEURAL_BUDGET_PROBE_2026-11-19.md). PyOD 3.6.7 exposes no loss history for four of the neural detectors, so a prospective campaign retaining diagnostics is not possible; the probe replaces it with a bounded budget-sufficiency check (8 problems, 3 seeds, 3x epochs, no non-finite score). It does not show convergence: Deep SVDD scores move with the budget (median rank correlation 0.74, minimum 0.33), the autoencoder hit its iteration cap in 16 of 24 fits, and the manuscript states both limits.
