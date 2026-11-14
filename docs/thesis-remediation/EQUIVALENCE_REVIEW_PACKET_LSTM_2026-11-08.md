# Owner decisions — LSTM equivalence candidates (decided 2026-11-11)

Governance: sole-author thesis; the repository owner `theobigand` is the only authorized approver
(`review_mode: sole_author_owner_review`). These are owner approvals, **not independent peer review**, and the approver is
recorded text, not an authenticated signature. The assistant and GPT-6 assessments were supporting evidence only.

Decisions are recorded in `verification/mutation_equivalence.json` (version 2). The original proposals stay in
`docs/thesis-remediation/equivalence/lstm_proposals_2026-11-11.json` for traceability; that file is not an approval source.

Checked before applying: source `research/lstm_detector.py` sha256 `277375e66d...` and module-catalog digest `aef20963dc...`
(377 mutants) equal the values in the hosted evidence of run 42433394723 (revision d296f2f) and the current file; every
candidate is a surviving mutant in that evidence; the policy version is 2 and the module is L4.

| Mutant | Decision | Date | Justification |
| --- | --- | --- | --- |
| `_reconstruction_error__mutmut_31` | **ACCEPT** | 2026-11-11 | In the `last_only` branch the tensor is `error[:, -1]`, always 2-D (windows are 3-D by construction), so `dim=+1` and `dim=-1` are the same axis. |
| `fit__mutmut_50` | **ACCEPT** | 2026-11-11 | With window count equal to the cap, choosing every index without replacement and sorting is the identity; the generator is not used again in `fit`. |
| `settings__mutmut_41` | **ACCEPT** | 2026-11-11 | Distribution names are normalised (PEP 503), so `TORCH` equals `torch`. |
| `settings__mutmut_46` | **ACCEPT** | 2026-11-11 | Same normalisation for `numpy`. |
| `_reconstruction_error__mutmut_35` | INCONCLUSIVE | 2026-11-11 | Depends on NumPy `astype(None)` behavior; stays in the denominator. |
| `_windows__mutmut_2` | INCONCLUSIVE | 2026-11-11 | Depends on pandas `astype(None)` behavior; stays in the denominator. |
| `fit__mutmut_16` | INCONCLUSIVE | 2026-11-11 | Same. |
| `fit__mutmut_43` | INCONCLUSIVE | 2026-11-11 | `replace=None` is outside the documented boolean contract; stays in the denominator. |
| `fit__mutmut_55` | INCONCLUSIVE | 2026-11-11 | Same. |

Only the four ACCEPT records exclude a mutant, and only while all validations pass: current source and catalog digests,
risk level, policy version, a surviving mutant, and the dependency versions of the campaign runtime (`numpy 2.4.6`,
`torch 2.15.0+cpu`). The five inconclusive mutants are never excluded, counted as killed, or accepted.

## Dependency-version reconciliation

Earlier review documents cite pandas 3.0.6 (the local Conda environment, where the differential tests were first run) while the
proposal records cite pandas 3.1.1 (the hosted Linux run and the mutation environment). Both are real: the 14 differential tests in
`research/tests/test_equivalence_claims.py` pass on pandas 3.0.6 and on 3.1.1 (numpy 2.4.6 on both). The pandas-dependent
candidates (`_windows__2`, `fit__16`) are INCONCLUSIVE, so no accepted record relies on pandas. The torch version recorded for
the two accepted torch-related records (`2.15.0+cpu`) comes from the hosted install log; campaign runtimes record the torch
version from the next run onward, and a mismatch then rejects the exclusion.

## Resulting arithmetic

On the hosted evidence of run 42433394723 (366 killed of 377): raw 97.08%, and with the four accepted exclusions adjusted
366/373 = 98.12%. That is a recalculation on an older run plus the owner's decisions, not current evidence: two later tests are
expected to give 368 killed (adjusted 98.66%), which a new hosted native run must confirm. Passing L4 for this module would not
establish compliance of other modules or certification.
