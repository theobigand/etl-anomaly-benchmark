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
- [ ] T055 Check neural convergence, stopping rules, epochs, and numerical failures.

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

Evidence for T056–T061: [standard and typed ETL paths](ETL_PATHS_2026-11-07.md), aligned with `pipeline.py`, `typed_benchmark.py` and the baseline tests.

Evidence for T065–T070: [preprocessing and information audit](PREPROCESSING_INFORMATION_AUDIT_2026-11-07.md), with the historical/prospective boundary retained.
