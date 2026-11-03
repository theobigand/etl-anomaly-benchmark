# Pool preparation implementation and validation — 2026-11-03

Related work: #89 T062–T064, #100 T351, #90 partition provenance, #103 gates.
Base revision: `f5ee1bd`. This is an exploratory code unit under the
[dated contract](POOL_PREPROCESSING_PROTOCOL_2026-11-03.md), not a replay of the
pool, a new hypothesis, or a release certification.

## Ready and implementation

Audit confirmed two information-access defects in the historical pool preparation:
evaluation categories can change the encoded schema (six-row example: five versus
three features), and a conflicting evaluation label can remove a reference row.
Keep these negative controls and the old implementation and archives intact.

`research/pool_preprocessing.py` accepts features and complete frozen positions,
without labels. It validates disjointness, row coverage and cross-fold duplicates,
then fits selection, vocabulary, imputation and scaling using training rows only.
`research/pool_train_only.py` explicitly consumes a source-bound partition manifest,
excludes the target and records scores, flags, fitted decisions and failures. It
uses the existing detector builders and training-prevalence calibration; this
does not make that threshold label-free. Research-source hashes supplement the
unchanged core fingerprint. No old runner is redirected to the new path.

The existing size-skip test expected only LOF/OCSVM above 50,000 training rows,
although production already also skips KNN. Its expectation now matches existing
behavior, with exact 50,000/50,001 boundary checks. No production limit changed.

## Test-first and measured checks

- RED: `pytest tests/test_pool_preprocessing.py -k 'evaluation_values or evaluation_labels'`
  failed because the two new modules were absent. The legacy desired-invariance
  check separately failed with encoded width 5 != 3; it is retained as a negative
  control, not silently converted into a corrected historical run.
- Additional reproductions: an all-skipped CLI selection previously returned zero;
  duplicate target headers could be renamed by the CSV parser and expose a target
  alias. Named regression checks first failed, then passed after the minimal fixes.
- GREEN: `make verify-preprocessing`: 54 cases pass, 165/165 executable lines and
  64/64 branches covered across the two new research modules; three constructed
  injected defects are caught after corresponding clean controls pass.
- REGRESSION: existing normalization/builder tests and workflow tests: 66 pass.
- `make verify-faults`: all 23 historical scientific defects are caught.
- `make verify-deep`: 4,972/5,102 killed (97.45%), threshold 95%, PASS. Remaining
  outcomes: 118 survived, 10 timeout, two suspicious; none skipped or without tests.
  These remain non-killed outcomes, not proven equivalent mutants.

The core DEEP denominator remains `src/etl_benchmark` and `experiments/`. New
research modules are checked separately by coverage and constructed defects;
no mutation score is claimed for them. Their fault suite is excluded from the
inner mutation campaign for the same reason as the existing isolated fault suite,
and runs separately in the new local/CI gate.

An initial mutation campaign was interrupted during test finalization and rejected
as evidence. Its copied tests were used to reconcile cache metadata before the
stable run: 1,956 valid verdicts retained, 33 invalidated. The stable campaign
confirmed 1,956 kept and zero further resets, executed outstanding cases, and
completed without interruption. Changes to configuration had required a broader
invalidation against the older cache. Cached verdicts are reused only while valid.
The temporary launcher limited mutation concurrency to two without changing scope,
thresholds or acceptance. No dependency was installed or upgraded.

## Publication and remaining work

The paper and editable deck disclose the historical limitation and distinguish
the exploratory correction from archived outcomes. The paper builds to 23 pages;
the deck builds to 40 pages. The pool result numbers are preserved. Publication
manifest updates affect only the TeX/PDF hashes and the manifest source revision;
sealed run records are unchanged. Historical verification counts in the paper
remain explicitly attributed to their original run, not the current branch.

T062/T063 remain open: suitable source-bound historical pool assignments must be
recovered and applicable studies replayed before claiming a validated train-only
ranking. This unit supplies tests for T064/T351, not proof that all historical
research paths are now leakage-free. This unit does not claim issue-level completion.

## Final local evidence

- REGRESSION: `make verify-fast`: 1,347 passed, 30 deselected; Ruff lint/format
  checks pass. Core scope: 1,790/1,790 lines and 350/350 branches. The new research
  modules retain their separate 165-line/64-branch denominator; the routine test
  count includes their acceptance cases, not their fault suite.
- A persisted [12-row CLI example](evidence/pool-train-only-example-2026-11-03/README.md)
  runs Z-score and Isolation Forest at seed 42. Source, partition, output and all
  four research-source hashes verify. It is not a real-pool performance study.
- [Verification bundle](evidence/pool-preprocessing-verification-2026-11-03.tgz):
  raw FAST/preprocessing reports, core mutation statistics and per-mutant outcomes,
  core fault matrix, original gate/RED logs and SHA-256 member inventory. Every
  inventory entry was checked against the archived bytes. No sealed older evidence
  or record was restamped. The earlier interrupted campaign is not accepted.
- [Implementation hashes](evidence/preprocessing-implementation-2026-11-03.json)
  bind the actual source/test/configuration bytes. Core DEEP/FAULTS records retain
  their actual base revision and dirty flag because they ran before the
  implementation commit. The completed DEEP copied tests and recorded test hashes
  match the current test files; its copied new research modules match implementation
  `edc3592`. No test or source edit occurred during the accepted campaign.
- [Final deck geometry/navigation](evidence/preprocessing-slides-geometry-2026-11-03.json):
  40 slides, 1280×720 content viewport, no out-of-bounds content or footer overlap;
  next/previous navigation passes. All rendered slide contact sheets were inspected,
  with the new preparation and final tracking slides inspected at presentation size.
  Paper abstract, Methods correction and pool-results page were inspected rendered.
  Voice check passes. All 21 manuscript tables remain byte-identical to the base;
  the only changed slide table is the RQ1 interpretation, with result tables intact.
- `git diff --check`: PASS. Scientific fingerprint
  `be28a126f038edec58574f4a3a8baff294ec1994ca9b93cb7c9b6a10efbab076` and measurement
  fingerprint `9cd603c619d15e17d3cbd9d14986b6f62bdb5611a5ba78fbd4d10ae8f4d7285d`
  are unchanged. They do not cover the new research code; the additional hashes do.

REAL, archive reproduction and release certification were not rerun: this unit
does not change old scientific implementations or result values, and does not
reuse old results as corrected train-only measurements. Local pinned typing and
verifier coverage were not rerun for unchanged verifier/core code; existing CI
requires those checks in addition to FAST, the new preparation gate and FAULTS.
Integration remains pending those checks on the final branch revision. No CI
success, new certification or independent attestation is inferred from local gates.

T064 and T351 are now checked in their issue/canonical volume; all 415 identifiers
remain unique and checked total is 24. All parent issues and milestones remain
open. Next independently executable P0 work is the complete 17-detector inventory
(T048–T050), using the source audit already completed; historical pool partition
recovery/replay is a separate unresolved scientific dependency.
