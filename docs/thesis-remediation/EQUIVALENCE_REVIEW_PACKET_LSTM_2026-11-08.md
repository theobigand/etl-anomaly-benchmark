# Owner decision packet — LSTM equivalence candidates (updated 2026-11-11)

Governance: this is a sole-author thesis. The repository owner (`theobigand`) is the only authorized approver and may
approve claims that were proposed by an assistant or by themselves (`review_mode: sole_author_owner_review`, declared in
`verification/mutation_risk_policy.json`). Owner approval is **not independent peer review** and the approver identity is
recorded text, not an authenticated signature (git history and the commit author are the only attestations). AI-assisted
assessments below are supporting evidence, not authorization.

**No candidate is approved.** The proposals are in `docs/thesis-remediation/equivalence/lstm_proposals_2026-11-11.json`
(all `proposed`, approver and date empty, validated against the hosted evidence of run 42433394723). That file is never loaded by
the gate. To accept a claim, copy its record into `verification/mutation_equivalence.json` (document `version: 2`,
`review_mode: sole_author_owner_review`, `owner: theobigand`), set `verdict` to `accepted`, `approver` to `theobigand` and
`decision_date` to the ISO date of the decision. The gate then requires the record to match the current source and
module-catalog digests, the risk level, the policy version and the dependency versions of the campaign runtime
(`environment`), and it keeps the raw outcome and raw score beside the adjusted score.

Source `research/lstm_detector.py` sha256 `277375e66d...` (identical at d296f2f and later); catalog digest `aef20963dc...`
(377 mutants). Differential evidence: `research/tests/test_equivalence_claims.py` (14 tests). Candidate descriptions:
`EQUIVALENCE_CANDIDATES_LSTM_2026-11-08.md`.

## Technical assessment (assistant, confirmed against the exact mutant diffs; preliminary GPT-6 assessment agrees)

| Mutant | Diff | Assessment | Scope of the argument | Relied-on environment |
| --- | --- | --- | --- | --- |
| `_reconstruction_error__31` | `dim=-1` to `dim=+1` | ACCEPT proposed | universal: in the `last_only` branch the tensor is `error[:, -1]`, always 2-D, because windows are 3-D by construction | torch 2.15.0+cpu |
| `fit__50` | validation cap `>` to `>=` | ACCEPT proposed | universal: choosing all indices then `np.sort` is the identity, and the generator is not used afterwards | numpy 2.4.6 |
| `settings__41` | `version("torch")` to `"TORCH"` | ACCEPT proposed | universal for Python >= 3.11: distribution names are normalised (PEP 503) | torch 2.15.0+cpu |
| `settings__46` | `version("numpy")` to `"NUMPY"` | ACCEPT proposed | same | numpy 2.4.6 |
| `_reconstruction_error__35` | `.astype(float)` to `.astype(None)` | INCONCLUSIVE | environment-specific: `astype(None)` is float64 here, a library default | numpy 2.4.6 |
| `_windows__2` | same on a DataFrame | INCONCLUSIVE | environment-specific (pandas behavior) | pandas 3.1.1 |
| `fit__16` | same on a DataFrame | INCONCLUSIVE | environment-specific (pandas behavior) | pandas 3.1.1 |
| `fit__43` | `replace=False` to `replace=None` | INCONCLUSIVE | outside the documented boolean contract; falsy in the installed numpy | numpy 2.4.6 |
| `fit__55` | same | INCONCLUSIVE | same | numpy 2.4.6 |

The five INCONCLUSIVE candidates could be accepted only as environment-bound equivalences (valid while the recorded
dependency versions hold); they are not universal. Rejecting them would require a behavior no test can distinguish today,
so a REJECT would not yield a test. If you accept none, the module stays at 368/377 (97.6%) and below L4.

## Arithmetic (a consequence, not a reason to accept)

L4 needs 370 of 377. Accepting the four universal candidates gives raw 368/377 and adjusted 368/373 (98.7%); the five
environment-bound ones are not needed for that. The recommendation of the assessment is to decide each candidate on its own
argument, and the five environment-bound ones only if you are content with an equivalence that expires when pandas or numpy
change.

## Decisions requested from the owner

For each of the nine mutants: ACCEPT, REJECT, INCONCLUSIVE or leave proposed, with your date. Nothing else depends on
this decision, and no decision is assumed.
