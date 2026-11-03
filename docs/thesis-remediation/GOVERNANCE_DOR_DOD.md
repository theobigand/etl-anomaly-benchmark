# Research governance, DoR/DoD, and verification reporting

**Status:** Planned follow-up work, not implemented or independently verified by this document.
**Scope:** Four issue-tracked tasks (#109–#112) concerning the existing ETL anomaly-benchmark thesis. These tasks are **in addition to** the unchanged T001–T415 checklist. They are not a new research question, detector family, or substitute for the required scientific corrections.

## Ownership and issue index

| Issue | Deliverable | Priority | Milestone | Main links |
| --- | --- | --- | --- | --- |
| [#109](https://github.com/theobigand/etl-anomaly-benchmark/issues/109) | Formalize experiment and code-change Definition of Ready / Definition of Done | P1 | Thesis 07 | #100, #103 |
| [#110](https://github.com/theobigand/etl-anomaly-benchmark/issues/110) | Audit and document test layers, quality gates, their actual results and limitations | P1 | Thesis 07 | #100, #103, #83, #84 |
| [#111](https://github.com/theobigand/etl-anomaly-benchmark/issues/111) | Reconcile evidence lineage, certification semantics, trust boundaries and release governance | P1 | Thesis 07 | #100, #103, #82, #84 |
| [#112](https://github.com/theobigand/etl-anomaly-benchmark/issues/112) | Integrate documented methods into Methods and Appendices A/B of the existing IMRaD paper | P1 | Thesis 06 | #99, #100, #101, #103 |

The existing authoritative documents are [verification/README.md](../../verification/README.md), [verification/certification.md](../../verification/certification.md), [verification/release_policy.json](../../verification/release_policy.json), [verification/milestones.json](../../verification/milestones.json), [paper/main.tex](../../paper/main.tex), and the test and workflow configuration. This document does not override them. First verify the current implementations, revisions, and archived evidence; do not assume a test count or release status applies to the latest commit.

## 1. Definition of Ready

### A. Research experiment

- [ ] Research question, scope, confirmatory hypotheses, negative or null outcomes, and intended contribution are stated.
- [ ] Dataset selection, exclusions, original sources, licences, checksums, target/label meaning and known source overlap are recorded.
- [ ] Statistical unit, independently sampled sources, sample size, train/validation/test splits, seeds, and repetition policy are fixed.
- [ ] Baselines, input-information access, preprocessing, detector scoring, thresholds, anomaly types, metrics and missing-run rules are fixed.
- [ ] Leakage threats, label access, future information, source duplicates and schema limitations have a mitigation or an explicit limitation.
- [ ] Paired and source-aware uncertainty/decision protocol is specified, with computing and resource limits.
- [ ] The dated protocol and evidence/archival plan precede evaluation on held-out outcomes; post-hoc analyses are distinguished as exploratory.
- [ ] Success criteria, applicability of verification gates, and accountable author review are defined.

### B. Scientific code change

- [ ] Expected behavior, scientific meaning, change scope and impact on existing claims are stated.
- [ ] Named minimal regression test and pre-fix failure are specified, ideally on small generated data without full research files.
- [ ] Relevant interfaces, scientific fingerprint, tests, archived runs, reports and release checks are identified.
- [ ] A justification for any policy exception is prepared (docs, formatting, characterized refactors or temporary exploration must remain distinct from behavior changes).

## 2. Definition of Done

### A. Research experiment

- [ ] Protocol version, datasets, configuration, code revision, environment, splits, seeds and all applicable results have traceable provenance.
- [ ] Failed/skipped runs, exclusions, detector non-convergence, negative hypotheses and unexpected outcomes are retained and reported without changing denominators silently.
- [ ] Correct metrics, threshold semantics, paired/source-aware uncertainty, sensitivity checks and label-access controls are independently reviewed against the intended scope.
- [ ] Tables, figures, manuscript claims and intermediate artifacts reconcile with archived raw results; integrity hashes and fingerprints are checked.
- [ ] Remaining uncertainties, missing gates, data rights, resource limits, portability constraints and reproducibility limits are documented.
- [ ] An issue is closed only with linked evidence or an explicitly reasoned not-applicable/scope-cut decision.

### B. Scientific code change

- [ ] The regression test first fails for the expected reason and then passes with the same assertion.
- [ ] Relevant lint, test, coverage, mutation, deliberate-fault, real-data, verification-tool, typing, reproduction and release checks are selected by change impact; not every gate is automatically necessary for a documentation change.
- [ ] When the scientific fingerprint or published evidence is affected, the archives and derived outputs are replayed/revalidated; old sealed artifacts are not hand-restamped.
- [ ] Manuscript claims and published tables are updated only after new traceable measurements.
- [ ] Unresolved gaps and justified exceptions are recorded; a green gate cannot automatically close a scientific question.

The existing ready/done policy in [verification/README.md](../../verification/README.md) is the baseline; issue #109 must reconcile it before creating new normative language.

## 3. Verification-layer matrix to audit

| Layer | Existing control / target | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| Regression, property, scientific contracts | Unit, detector, split, metric, time/leakage and adverse-schema tests | Tested behaviors under the checked cases | Validity of all hypotheses or untested populations |
| FAST | Ruff, tests, measured line and branch coverage; exact scope to verify | Code exercised by the tested suite | Every possible bug is detected |
| DEEP | Mutation campaign, eligible scope and required >=95% killed fraction | Sensitivity of tests to specified code mutations | No remaining defects or proof that all mutants are equivalent |
| FAULTS | Historically 23 deliberate scientific defects, each caught by a named test | Detection of specific dangerous scientific mistakes | Coverage of every leakage/statistical error |
| REAL | Full research data checks and SHA-256 manifests | Data identity and selected data invariants | Generalization to other datasets |
| TOOLS / TYPES | Verifier coverage and checked static typing | Tested verifier behavior and a bounded type policy | Correctness of results outside tested contracts |
| REPRODUCTION | Controlled replay, relevant environment lock and comparisons | Bounded reproducibility under recorded conditions | Universal cross-platform identical results |
| CI / RELEASE | Workflow artifacts and release-policy decision | Consistency of required evidence for the given revision | Independent attestation, scientific validity, or complete ETL operating cost |

Issue #110 must reconcile this planned matrix against **the current actual source**, not assume these are always executed or green. Existing published historical evidence cites a local run at commit `d4304c5b`, with 1,292 routine tests, full line/branch coverage on its measured scopes, 4,980/5,102 mutants killed (97.61%), and 23 scientific defects detected. Verify these values against their exact archive if using them in the paper. Never present them as measurements of the current head.

## 4. Release and evidence governance to audit

- [ ] Define the full claim → figure/table → run → dated protocol → dataset/source manifest → code/config/environment revision → evidence-digest chain.
- [ ] Validate release verdicts from underlying raw evidence rather than pass labels; identify the cases yielding `CERTIFIED`, `INCOMPLETE` and `REJECTED`.
- [ ] State the checks designated **required**, **optional**, **deferred**, or **not applicable** in the actual versioned release policy.
- [ ] Explain why a changed scientific fingerprint invalidates/requires reconciliation of prior sealed results, while recording the treatment of non-scientific edits.
- [ ] Describe the local research-data and hosted CI trust boundaries, as well as any pinned-version/OS differences.
- [ ] Preserve both passing and failing outcomes, historically recorded milestones M00–M13, unreviewed mutants, incomplete archive replays and unresolved independent attestation.
- [ ] Explicitly distinguish a code-evidence certification from independent third-party attestation, hypothesis correctness, external validity and throughput claims.
- [ ] Do not silently change branch protections, release requirements or existing signed/reviewed evidence.

Coordinate #111 with existing #82, #84, #100 and #103.

## 5. IMRaD integration

Use existing sections rather than creating an unrelated governance study.

| Section | Content to integrate | Presentation boundary |
| --- | --- | --- |
| **Methods — Verification and reproducibility** | Concise statement of experiment and code DoR/DoD, prospective protocols, applicability-based gates, data/source tracking, claim-evidence linkage | Roughly one short paragraph or similarly compact space |
| **Appendix A — Verification design** | Lifecycle diagram/table (Ready → Implement/Run → Checks → Evidence → Done → Report), test-layer matrix, policies and trust boundaries | Technical details primarily retained in repository |
| **Appendix B — Verification outcomes** | Actual measured historical results with revisions, denominators, environments, remaining survivors and deferred controls | Never confuse older measurements with the current release |
| **Discussion / limitations (only if necessary)** | Difference between code reliability and inferential validity, source/label dependence, unaudited evidence and lack of independent attestation | No independent research question unless governance effectiveness was itself evaluated |

The original paper asks RQ1–RQ4 about detector comparisons, anomaly types, thresholds/temporal behavior and cost. Present reproducibility/governance as a **secondary methodological contribution**: explicit controls and an auditable experimental pipeline. Do not claim that DoR/DoD or passing tests prove improved detector quality, statistical correctness or a novel scientific result. An example where deliberately introduced scientific faults exposed weaknesses in an earlier test suite may be presented *only with exact existing evidence and accurate scope*.

Follow the required IEEE/institutional page budget, keep existing negative findings, preserve original hypotheses, and ensure every manuscript number and certification statement is evidence-backed before publication.

## Crosswalk to the established roadmap

- T336–T366 and [#100](https://github.com/theobigand/etl-anomaly-benchmark/issues/100): provenance, dataset manifests, locks, tests, reproduction, integrity and final release.
- T357–T360: never equate coverage with scientific validity; preserve preregistration and exploratory addenda.
- T398–T415 and [#103](https://github.com/theobigand/etl-anomaly-benchmark/issues/103): avoid duplicate work, acceptance evidence, quality-gate coordination and claim-to-evidence matrix.
- [#99](https://github.com/theobigand/etl-anomaly-benchmark/issues/99) and [#101](https://github.com/theobigand/etl-anomaly-benchmark/issues/101): IMRaD, bibliography and submission-quality control.
- [#82](https://github.com/theobigand/etl-anomaly-benchmark/issues/82), [#83](https://github.com/theobigand/etl-anomaly-benchmark/issues/83), [#84](https://github.com/theobigand/etl-anomaly-benchmark/issues/84): archived fingerprint replay, statistical-source concerns and independent release attestation.

**Completion rule:** these additional tasks remain open until their concrete criteria are evidenced. The existence of this file and of #109–#112 does not mark any of them complete. Do not modify experimental code or the paper as part of backlog organization.
