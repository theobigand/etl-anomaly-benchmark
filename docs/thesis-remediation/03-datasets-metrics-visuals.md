# Thesis remediation backlog — Volume 3: Datasets, Metrics, Figures, and Tables

**Scope:** T071–T125. **Status:** open until individually verified. **P0:** mandatory scientific correction.

Keep dataset populations separate and document overlaps. Generate figures and tables from reproducible result files; do not alter archived outcomes by hand.

## 06. Dataset inventory, overlap, and selection (P0; Thesis 01)

- [x] T071 Explain the provenance of the 152-dataset pool.
- [x] T072 Describe 100 labelled problems separately: 36 ADBench and 64 UCI.
- [x] T073 Describe 58 injection-eligible tables separately: 42 UCI and 16 ADBench.
- [x] T074 Show overlap between labelled and injection-eligible populations.
- [x] T075 Add a dataset inclusion/exclusion flow diagram.
- [x] T076 Define inclusion and exclusion criteria.
- [x] T077 Verify the stated minimum-row and continuous-column eligibility criteria.
- [x] T078 Inventory the five initially identified temporal datasets.
- [x] T079 Explain why four temporal datasets were retained, if confirmed.
- [x] T080 Document the Room Occupancy exclusion.
- [x] T081 Publish a manifest with source, version, dimensions, types, labels, and license.
- [x] T082 Assign a shared source identifier to derived problems.
- [x] T083 Verify the reported 19 overlapping ADBench/UCI sources.
- [x] T084 Do not treat 100 problems as 100 independent sources.
- [x] T085 Document minority-class-to-anomaly label mapping in UCI.
- [x] T086 Do not equate semantic minority classes with ETL defects.
- [x] T087 Explain Water Quality's violation of the rare-anomaly assumption where applicable.
- [x] T088 Record prevalence in train, validation, and test.
- [ ] T089 Publish seeds and reproducible partition IDs.

Evidence for T071–T088: [dataset inventory audit](DATASET_INVENTORY_AUDIT_2026-11-07.md), derived from the pinned registry manifests and temporal evidence. T089 remains open because historical row IDs were not archived.

## 07. Metric definitions and baselines (P0; Thesis 02)

- [x] T090 Verify whether the primary metric uses average_precision_score.
- [x] T091 Rename PR-AUC to Average Precision (AP) throughout if confirmed.
- [x] T092 Correct AP headers in Tables II, III, VII, XII, XIII, XIV, XV, XX, and XXI.
- [x] T093 Correct related figure labels and captions.
- [x] T094 Define AP mathematically.
- [x] T095 Distinguish AP from trapezoidal precision-recall area.
- [x] T096 Retain ROC-AUC as complementary, not sufficient for rare anomalies.
- [ ] T097 Show anomaly prevalence alongside AP.
- [x] T098 Provide a prevalence-aware random-ranking baseline with qualifications.
- [x] T099 Separate ranking metrics from threshold-dependent metrics.

Evidence for T090, T094–T096, T098 and T099: [metric definitions and validation](METRIC_DEFINITIONS_2026-11-03.md).
T097 remains open: prevalence needs consistent display alongside AP; the issue is only partially complete.

## 08. Figures and methodological diagrams (P0; Thesis 01)

- [ ] T100 Regenerate Figure 1 from source results.
- [ ] T101 Regenerate Figure 3 from source results.
- [ ] T102 Verify every heatmap annotation against archived tables.
- [ ] T103 Export vector figures with properly embedded fonts.
- [ ] T104 Test an appropriate matplotlib PDF font setting, including pdf.fonttype=42 if effective.
- [ ] T105 Check legibility in the IEEE double-column format.
- [ ] T106 Use accessible color scales and clear legends.
- [ ] T107 Show dataset and seed counts where needed.
- [ ] T108 Explain the zero-valued per-row drift result.
- [ ] T109 Do not silently replace a negative drift result.
- [ ] T110 Keep the original drift experiment in detailed results or appendices.
- [ ] T111 Present window-level drift monitoring separately as a different task.
- [ ] T112 Add a typed-fault injection protocol diagram.
- [ ] T113 Add a dataset selection diagram.
- [ ] T114 Add a quality-versus-cost figure if space permits.

## 09. Tables and publication lineage (P0; Thesis 01)

- [ ] T115 Correct the "This paper" row of Table I.
- [ ] T116 State the final 17-detector registry in Table I.
- [ ] T117 Keep LSTM and drift pilots outside the registry count.
- [ ] T118 Clarify the three examples, 152 pool, 100 labelled problems, and 58 injection tables.
- [ ] T119 Correct AP metric headers wherever applicable.
- [ ] T120 Resolve missing neural timing cells in Tables XII and XV.
- [ ] T121 Refer to Table VI with a footnote when timings were measured separately.
- [ ] T122 Do not copy timing values from incompatible measurement conditions.
- [ ] T123 Standardize rounding, units, denominators, and symbols.
- [ ] T124 Make each table independently interpretable.
- [ ] T125 Generate tables from archived results rather than manually editing values.
