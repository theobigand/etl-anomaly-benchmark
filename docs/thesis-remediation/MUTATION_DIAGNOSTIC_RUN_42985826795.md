# Hosted mutation diagnostic, run 42985826795 (shard 31) - 2026-11-11

Diagnostic only. It is one shard of the 45-shard plan, run on `3dbf6f5` in the Linux hosted
environment. It is not a release gate and does not certify any module other than reporting its own
outcomes. The aggregate job was skipped by design.

Evidence: `verification/evidence/mutation_diagnostics/run_42985826795_shard31/`
(`evidence-shard-31.json`, `controller-result.json`, native log and execution proof, `shard-plan.json`).

## Checks performed

- Revision in the evidence is `3dbf6f5033da1b187fe6678e6c8c5e10c7603699`; the plan digest in the
  evidence equals the digest of the downloaded `shard-plan.json`; native exit code 0; no missing mutants.
- Runtime: Linux (azure, glibc 2.39), Python 3.11.18, torch 2.15.0+cpu, numpy 2.4.6, pandas 3.1.1,
  pyod 3.6.7, scikit-learn 1.9.1, mutmut 3.8.0.
- The LSTM source digest in the proof equals the digest of the checked-out file.
- The catalog holds 377 LSTM mutants; the records cover exactly those 377 identities, once each.

## Outcomes

| Module | Killed | Survived | Timeout | Incomplete | Total |
| --- | --- | --- | --- | --- | --- |
| research/lstm_detector.py (L4) | 368 | 9 | 0 | 0 | 377 |
| research/pool_check.py | 118 | 62 | 0 | 0 | 180 |
| src/etl_benchmark/atomic.py | 6 | 0 | 0 | 0 | 6 |
| src/etl_benchmark/transform.py | 2 | 0 | 0 | 0 | 2 |

## LSTM scores (exact integers)

- The nine survivors are exactly the nine mutants of the owner decision file.
- `accepted_equivalents` accepts the four owner-accepted records against this environment (all
  four dependency bindings match) and keeps the five inconclusive ones eligible.
- Raw: 368/377 = 97.61%, below 98% (36800 < 98 x 377 = 36946).
- Adjusted: 368/373 = 98.66%, at or above 98% (36800 >= 98 x 373 = 36554).
- The expected 368/377 and 368/373 are confirmed as hosted measurements for this module.

## Limits

- Shard 31 only: the other modules, cache invalidation and interrupted-shard checks are not covered.
- pool_check.py (62 survivors, 65.6%) remains far below any threshold and needs targeted tests.
- No earlier per-mutant Linux campaign data is stored in the repository, so a comparison by mutant
  identity with earlier campaigns was not possible here.
- The owner equivalence acceptance is sole-author review, not independent peer review.
