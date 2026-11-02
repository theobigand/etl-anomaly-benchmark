# Historical issue triage and consolidation

**Reviewed:** 2026-11-02. **Scope:** the nine issues left open from the earlier thesis plan (#70 and #77–#84). The original completed issues (#63–#69 and #71–#76) remain closed and are not reopened.

The historical issues are retained as evidence of specific acceptance criteria. A parent roadmap issue is a coordination point, not proof that its linked historical work is complete. The `origin:historical` label identifies carry-over work. All eight unresolved issues retain their original descriptions and their own closure conditions.

## Disposition matrix

| Historical issue | Decision | Priority | Milestone | Grouped under | Rationale |
| --- | --- | --- | --- | --- | --- |
| [#70](https://github.com/theobigand/etl-anomaly-benchmark/issues/70) — IMRaD calendar and scope gates | **Closed — completed** | — | — | [#99](https://github.com/theobigand/etl-anomaly-benchmark/issues/99), [#103](https://github.com/theobigand/etl-anomaly-benchmark/issues/103) | The progress comment after PR #76 records completion of the original M2 S1 gates. The historical scope decision is preserved; current work uses the new roadmap. |
| [#77](https://github.com/theobigand/etl-anomaly-benchmark/issues/77) — 94 injection-ineligible tables | **Open — optional extension** | P2 | Thesis 08 | [#96](https://github.com/theobigand/etl-anomaly-benchmark/issues/96), [#95](https://github.com/theobigand/etl-anomaly-benchmark/issues/95), [#102](https://github.com/theobigand/etl-anomaly-benchmark/issues/102) | Mixed and categorical fault protocols require new eligibility criteria; do not imply the original 58-table study covers the excluded 94. |
| [#78](https://github.com/theobigand/etl-anomaly-benchmark/issues/78) — ten chronological datasets | **Open — optional extension** | P2 | Thesis 08 | [#98](https://github.com/theobigand/etl-anomaly-benchmark/issues/98), [#102](https://github.com/theobigand/etl-anomaly-benchmark/issues/102) | Valid time variables, labels, and dataset rights are prerequisites; the original temporal limitation must remain explicit until then. |
| [#79](https://github.com/theobigand/etl-anomaly-benchmark/issues/79) — 14 failed ETL measurements | **Open — important validation** | P1 | Thesis 03 | [#95](https://github.com/theobigand/etl-anomaly-benchmark/issues/95), [#103](https://github.com/theobigand/etl-anomaly-benchmark/issues/103) | Repair categorical/reader/all-missing feature failures with tests; retain failure accounting and comparable denominators. |
| [#80](https://github.com/theobigand/etl-anomaly-benchmark/issues/80) — fit caps and tuning | **Open — important experiment** | P1 | Thesis 04 | [#97](https://github.com/theobigand/etl-anomaly-benchmark/issues/97) | The original out-of-the-box results are preserved; a new prespecified equal-budget ablation tests sensitivity. |
| [#81](https://github.com/theobigand/etl-anomaly-benchmark/issues/81) — isolated real-data timings | **Open — important experiment** | P1 | Thesis 05 | [#98](https://github.com/theobigand/etl-anomaly-benchmark/issues/98) | Concurrent timings are not isolated latency measurements; controlled reruns are required for stronger operational claims. |
| [#82](https://github.com/theobigand/etl-anomaly-benchmark/issues/82) — scientific fingerprint replay | **Open — required validation** | P0 | Thesis 07 | [#100](https://github.com/theobigand/etl-anomaly-benchmark/issues/100), [#103](https://github.com/theobigand/etl-anomaly-benchmark/issues/103) | Archived runs carrying an older fingerprint require a clean replay or explicitly justified provenance policy, not manual restamping. |
| [#83](https://github.com/theobigand/etl-anomaly-benchmark/issues/83) — labels, twin sources, seeds, tests | **Open — required validation** | P0 | Thesis 02 | [#93](https://github.com/theobigand/etl-anomaly-benchmark/issues/93), [#90](https://github.com/theobigand/etl-anomaly-benchmark/issues/90) | Paired, source-aware inference and label-rule sensitivity affect the validity of ranking claims. The ten-seed target remains recorded in the original issue. |
| [#84](https://github.com/theobigand/etl-anomaly-benchmark/issues/84) — attestation, Linux lock, mutations | **Open — important validation** | P1 | Thesis 07 | [#100](https://github.com/theobigand/etl-anomaly-benchmark/issues/100), [#103](https://github.com/theobigand/etl-anomaly-benchmark/issues/103) | Independent attestation and full neural-environment reproducibility are not demonstrated by the existing local certification alone. |

## Grouping policy

- The roadmap issues (#88–#103) coordinate thematic work; the historical issues remain distinct **implementation or evidence deliverables**.
- A linked issue is not closed merely because a broad parent checklist contains a similar item.
- The owner may close a historical issue as **completed** only when its specific acceptance criteria are supported by reproducible evidence.
- If the scope is formally cut, document the rationale and remaining manuscript limitation before closing it as **not planned**. Do not silently remove unsupported conclusions.
- The optional P2 issues (#77 and #78) do not block the minimum thesis release, provided their limitations are stated accurately.
- The P0 issues (#82 and #83) are release/claim validity gates, not optional extensions.
- The P1 issues (#79–#81 and #84) remain visible and prioritized; the release decision must explain any unresolved limitation.

## Evidence and historical decisions

The original progress comment on #70 records that the dataset registry (#66), deep rows (#64), typed injection (#65), multi-schema generator (#67), temporal decision study (#63), Related Work (#68), and IMRaD draft (#69) were completed after PR #76. This justifies closing the **historical planning issue**, not the newer scientific remediation backlog.

Existing verified work should be linked rather than repeated. Keep the historical research protocols, sealed archives, negative findings, and original issue bodies unchanged. Follow-up experiments must use dated protocol addenda.

## Automation

[tracking.json](tracking.json) is the source for the historical issue labels, milestones, and thematic links. The [roadmap synchronization workflow](../../.github/workflows/thesis-roadmap-sync.yml) checks the 415-task inventory, applies labels and milestones to the 24 open roadmap/historical issues, and labels the one closed historical planning issue without reopening it. The workflow does not change issue bodies, run experiments, or close issues.
