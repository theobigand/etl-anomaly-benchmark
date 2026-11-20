Tracks #116 (risk-tiered mutation policy), with documentation work for #89, #90 and #91.

## Scope
- Prospective L1 80 / L2 90 / L3 95 / L4 98 mutation policy: classification of 92 production modules, per-module and per-level arithmetic, native-catalog adapter, execution-bound cache, managed controller, version-2 release policy.
- Methods and metric documentation: detector inventory, convergence limits, standard versus typed ETL paths, preprocessing information limits, dataset inventory, AP terminology.
- Corrections found in review: `[project]` change that invalidated the scientific fingerprint, one uncovered branch in the mutation gate CLI, one grammar error in the manuscript.

## Risk
High (evidence acceptance and certification). Historical 95% results keep their original criterion.

## Evidence
- Fast suite: 100% line and branch coverage of `src/etl_benchmark` and `experiments` (1800 lines, 354 branches); verifier coverage 2789 lines and 1078 branches, both 100%. `research/tests` (245 tests) now run by default.
- Faults gate: 23 of 23 deliberate defects detected locally (control copy fixed to include `verification/`).
- First complete native mutation campaign (revision c8e3917): 19,248 of 29,811 killed; L4 65.5% against 98%; gate FAIL. 27 modules pass their own threshold, 32 fail, 30 incomplete. Record and archive under `docs/thesis-remediation/evidence/`.
- Release gate returns REJECTED, as intended: no passing current four-level campaign.
- Corrections found along the way: fingerprint-invalidating `[project]` edit, uncovered gate branch, clean-checkout `mutants/` directory, mutmut/pytest pin, native `fnmatch` scope semantics, sandbox test selection, flat research imports, dataset overlap figure (15 unique labelled sources; 19 across the full UCI pool), English technical audits, T055/T088 reopened.

## Open
Merge is not requested: L1-L4 compliance is not met (hosted sharded campaign at 20342c2: L4 65.1%, L3 49.2%, FAIL), so #116 stays open. Remaining: tests for 7,252 uncovered and 3,891 surviving mutants, execution binding for shards (their evidence is capped at INCOMPLETE), hosted cache reuse, independent review, no accepted equivalents yet. To rerun the hosted campaign, add the label `run:mutation-shards`.

## Rollback
Revert the merge commit; no sealed archive is modified.

