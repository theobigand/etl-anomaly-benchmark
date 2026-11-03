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
- [ ] T045 Correct the theoretical description of COPOD.
- [ ] T046 Distinguish COPOD's theoretical formulation from scoring in the pinned PyOD version.
- [ ] T047 Inspect the pinned PyOD source before describing how ECOD/COPOD combine dimensions.
- [ ] T048 Add a complete table of all 17 detectors.
- [ ] T049 Record family, implementation origin, library version, accepted data types, preprocessing, and training caps.
- [ ] T050 Record score definition, direction, threshold, and implementation adaptations.
- [ ] T051 Document the modifications to ECOD, COPOD, DIF, and VAE.
- [ ] T052 Explain the requirement for inductive per-row scoring in ETL inference.
- [ ] T053 Test whether a row's score is invariant to other rows in the test batch where claimed.
- [ ] T054 Distinguish bug fixes from algorithm-changing adaptations.
- [ ] T055 Check neural convergence, stopping rules, epochs, and numerical failures.

Evidence for T037–T044: [rule-definition audit and validation](RULE_DEFINITIONS_2026-11-03.md).
T037/T038 were already implemented; the audit confirms them without a duplicate notation patch.

## 05. ETL preprocessing and leakage controls (P0; Thesis 01)

- [ ] T056 Document extraction, validation, transformation, imputation, encoding, fitting, scoring, and alert order.
- [ ] T057 Add a diagram of the standard ETL path.
- [ ] T058 Show the typed-fault evaluation as a separate path.
- [ ] T059 Explain that standard transformation may remove exact duplicates before detection.
- [ ] T060 Explain that injected duplicates remain available to the typed detector benchmark.
- [ ] T061 Report transform_dedup as a distinct baseline when appropriate.
- [ ] T062 Verify all preprocessing is fitted on training data only.
- [ ] T063 Verify test statistics never influence preprocessing or fitting.
- [ ] T064 Test for label leakage in preprocessing decisions.
- [ ] T065 Record columns removed, retained, or transformed.
- [ ] T066 Explain the impact of excluding text and categorical features.
- [ ] T067 Explain how median imputation affects missing-value detection.
- [ ] T068 Document normalization and scaling.
- [ ] T069 Verify consistent anomaly-score orientation.
- [ ] T070 Identify comparisons where families receive unequal input information.
