# Thesis remediation backlog — Volume 1: Abstract, Introduction, and Related Work

**Scope:** T001–T036. **Status:** open until individually verified. **P0:** mandatory scientific correction.

Preserve original hypotheses, negative results, sealed artifacts, and source provenance. Verify each observation against the current paper and code before making changes. Do not invent citations, measurements, or outcomes. All added studies must have dated protocols and reproducible evidence.

## 01. Abstract and headline claims (P0; Thesis 01)

- [ ] T001 Remove the claim that detector families are interchangeable.
- [ ] T002 State that no detector dominates uniformly across evaluated datasets.
- [ ] T003 Do not treat overlapping confidence intervals as evidence of equivalence.
- [ ] T004 Use Average Precision (AP), not PR-AUC, if the implementation computes average_precision_score.
- [ ] T005 Limit neural-model conclusions to the tested out-of-the-box CPU configuration.
- [ ] T006 State the 20,000-row training cap wherever it applies.
- [ ] T007 Qualify type-specific findings by numeric-only ML preprocessing and generic Great Expectations rules.
- [ ] T008 Distinguish the 100 labelled problems from the 58 typed-injection tables.
- [ ] T009 Report the 17-detector registry accurately: three rules, eight classical, six neural.
- [ ] T010 Keep the LSTM and drift pilots outside the 17-detector registry.
- [ ] T011 Replace general neural-cost claims with architecture-specific conclusions.
- [ ] T012 Rewrite the abstract after corrected analyses; remove superseded claims.

## 02. Introduction and research questions (P0; Thesis 01)

- [ ] T013 Define the ETL data-quality problem precisely.
- [ ] T014 Distinguish statistical outliers from actual data-quality defects.
- [ ] T015 Explain limitations of rules, statistics, classical ML, and deep learning.
- [ ] T016 State the specific gap addressed in prior research.
- [ ] T017 Present the 17 detectors as one coherent experimental registry.
- [ ] T018 Remove chronological Git-commit narratives about registry expansion.
- [ ] T019 Clarify research questions RQ1 through RQ4.
- [ ] T020 Map each research question to protocols and metrics.
- [ ] T021 State the demonstrated contributions: operational comparison, typed faults, thresholds, temporal shift, and cost.
- [ ] T022 Do not present dataset count as the principal novelty.
- [ ] T023 Define whether the setting covers batch ETL, streaming, or both.
- [ ] T024 Define deployability: label access, thresholding, cost, stability, maintenance, and false positives.
- [ ] T025 Review whether the title reflects ETL data-quality evaluation accurately.

## 03. Related work and source verification (P0; Thesis 01)

- [ ] T026 Read the full Agyemang (2024) article before describing its methods and limitations.
- [ ] T027 Remove "I read the abstract only".
- [ ] T028 Correct "not stated in the abstract" in Table I.
- [ ] T029 Review verified 2025–2026 tabular anomaly-detection benchmarks.
- [ ] T030 Verify the proposed MacrOData reference, publication, authors, dataset counts, and conclusions before citing it.
- [ ] T031 Verify the proposed 2025 enterprise-ETL autoencoder reference and its actual scope.
- [ ] T032 Compare prior studies on detector families, datasets, faults, rules, drift, costs, and reproducibility.
- [ ] T033 Explain the added value over ADBench and generic outlier benchmarks.
- [ ] T034 Separate statistical outlier detection, data-quality validation, drift monitoring, and ETL integration.
- [ ] T035 Check every bibliographic claim against the complete primary source.
- [ ] T036 Remove unsupported comparisons based only on abstracts or secondary descriptions.
