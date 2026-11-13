# L4 to L3 reclassification

Status: accepted by the owner in the session of 2026-11-13 (their words: accept the reclassification, add the other
possible ones, the aim of the tiers is a percentage that means something per module, not a higher global figure).
This acceptance is recorded here as context; it is not an equivalence decision and creates no approver record. The edit to the
policy file is applied only after the baseline sweeps finish, so the sweep stays bound to one policy state. Until then `verification/mutation_risk_policy.json` is unchanged. Changing a level is a governance decision
of the owner (`theobigand`, sole-author review) and must go through the policy's own digest and versioning.
The section above this line described the first proposal. Nothing here lowers a threshold: L3 stays 95 and L4 stays 98 for the files that remain in each tier.

## Why a review is useful

91 of 98 mutable files are L4, 6 are L3, 3 are L2 and none is L1. A tier that holds 93% of the files gives little
information. The criteria below are the stated basis for the proposal; see guardrail 3 on score visibility.

## Criteria (independent of mutation scores)

Keep L4 when an error would change one of: a scientific number or label, a leakage boundary (train/test, causal order),
dataset identity or integrity, or a decision of a certification or release gate.

Consider L3 when the file only renders, copies, transports or describes results that other L4 code and tests already
compute and bind, and a defect would be caught by a downstream byte, hash or value comparison.

## Proposed to move to L3 (owner decision per file)

| File | Current reason (short) | Why L3 is arguable | Residual risk if moved |
| --- | --- | --- | --- |
| `research/paper_appendix.py` | generated appendix cells keep method/type alignment | renders archived matrices into text; the values are computed elsewhere | a swapped row or column could ship; mitigated by the manuscript-sync tests |
| `research/paper_tables.py` | table extraction and manuscript replacement | same: presentation of computed values | same |
| `research/pool_extension_paper.py` | generated manuscript blocks agree with archived results | same | same |
| `research/typed_figures.py` | heatmap orientation and cells match typed results | plotting of recorded results | a transposed heatmap is a visible, checkable error |
| `verification/archive_evidence.py` | artifact copy completeness and hash refresh | copies and hashes files; integrity is re-checked by lineage and claims | a missed file; hashes still verified later |
| `verification/bundles.py` | archive allowlist and traversal prevention | transport only; traversal prevention is a security property, so review closely | path traversal is a security risk; keep L4 if you weigh that higher |
| `verification/protection.py` | read-only protection-policy description | descriptive, does not itself block anything | misreported protection state |
| `verification/refresh_profile.py` | coverage and revision determine the verification profile | reporting of a measured profile | a wrong profile is visible in the report |
| `verification/lock_environment.py` | dependency locks bind execution | tooling around locks; reproducibility is also checked by the reproduce gate | a stale lock accepted until reproduce runs |

Added at the owner's request to look for further cases (same criteria):

| File | Why L3 is arguable | Residual risk if moved |
| --- | --- | --- |
| `verification/real_preflight.py` | pre-flight checks before a REAL run; the run itself is re-verified by `verify_real` hashes and dimensions | a wrong pre-flight verdict lets a bad run start; the run is still rejected afterwards. Its campaign score was low, so check this is not the reason |
| `src/etl_benchmark/atomic.py` | file publication helper, fully killed; an incomplete write is caught by later hash checks | a truncated result file is detected later, not at write time |
| `research/typed_masking.py` | contamination diagnostics that support an explanation, not a primary result | a wrong diagnostic could mislead the explanation |

Total proposed and accepted for L3: 12 files. The remaining 79 stay L4.

## Should stay L4 (no change proposed)

Everything that computes a metric, label, split, threshold, fingerprint, or hypothesis summary
(`metrics`, `split`, `synthetic`, `injection`, all `quality/*` detectors, every `research/*` benchmark and summary
module not listed above). All dataset identity code (`build_pool`, `pool_check`, `dataset_registry`, `real_acquire`,
`fetch_cardio`, `verify_real`, `datasets`). All gate code (`release`, `evidence_schema`, `check_types`, `claims`,
`lineage`, `reproduce`, every `mutation_*`, `check_mutation`, `verification_report`, `pool_contract`, `real_preflight`).

## Not proposed, but worth your attention

- `src/etl_benchmark/atomic.py`, `transform.py`, `extract.py`: tiny and fully killed; their L4 reasons are real
  (result completeness, target alignment) so they stay.
- No file is proposed for L1. An L1 tier would only make sense for code with no scientific or gate role; none exists
  among the mutable files.

## Guardrails if you accept any of it

1. The change must be made in the policy file by you, with the policy version and digest updated by the normal tooling.
2. Moved files are then measured against 95, and the evidence for them is re-collected at the new level.
3. Do not move a file because its score is low. The criteria were applied to the written reasons, and the table gives no
   scores. Disclosure: the 2026-11-07 campaign scores of these files were already visible to the author when the list was
   drawn, so the owner should check that no entry is there only because it is hard to kill.
4. Reclassification does not touch the 43 pending equivalence candidates or any owner decision.
