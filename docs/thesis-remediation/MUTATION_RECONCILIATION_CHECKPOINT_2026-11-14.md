# Mutation campaign reconciliation checkpoint, 2026-11-14

This is an incomplete, local reconciliation of commit `9ca176f0a07311b7a49f2053dc059af732333f0e`, not a fresh measurement, independent review, or certification. PR #117 remains a draft. The release and mutation workflows were skipped for that commit; the ordinary CI test, faults and slides jobs succeeded.

The archive checksum matches. Reconciliation of the 100-unit inventory against 98 archived primary verdict files (two no-mutant units have no verdict file) found 34,781 unique mutant IDs: 34,229 with exit code 1 and 552 with exit code 0. Unit counts and all 212 survivor identities in the 22 failing units agree with the archived files. The remaining 340 survivors belong to passing units. No other exit codes were recorded. These are historical verdicts with reused kills and mixed case-sensitive and case-insensitive macOS origins, not a single reproducible execution. Every current source digest matches the historical measurement.

The 212 failing-unit survivors comprise 33 existing second-packet pattern proposals, eight first-packet proposals, four previously accepted LSTM records, five previously inconclusive LSTM records, and 162 unclassified. The second-packet proposals and its unclassified entries have no overlap with the first packet; no survivor identity occurs twice in the second packet. This reconciles identity and counts only: the 162 entries have not been investigated individually and the proposed classes have not been independently validated.

## Provisional arithmetic, not decisions

All rows are L4 (98%). Missing kills use the exact integer threshold. Proposals are second packet + first packet, excluding previously decided LSTM records. Inconclusive includes the five existing LSTM inconclusive verdicts and all 162 unclassified entries; the proposals themselves remain unverified. Hypothetical scores remove all listed proposals from the denominator, without claiming any is equivalent or authorized. A yes means arithmetic could pass under that hypothetical, subject to evidence, owner decisions and official validation. A no only says the listed proposals alone cannot close the gap; it does not prove that a surviving mutant has a meaningful behavioral difference.

| Unit | Raw | Missing kills | Proposals (second + first) | Inconclusive/unclassified | Hypothetical | Pass under hypothetical |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `experiments/run_severity.py` | 320/329 (97.26%) | 3 | 2 + 0 | 7 | 97.86% | no |
| `research/injection.py` | 325/336 (96.73%) | 5 | 2 + 0 | 9 | 97.31% | no |
| `research/lstm_detector.py` | 368/377 (97.61%) | 2 | 0 + 0 | 5 | 97.61% | no |
| `research/multi_schema.py` | 1057/1093 (96.71%) | 15 | 4 + 0 | 32 | 97.06% | no |
| `research/normalise.py` | 191/197 (96.95%) | 3 | 0 + 6 | 0 | 100.00% | yes |
| `research/pool_chrono.py` | 300/316 (94.94%) | 10 | 3 + 0 | 13 | 95.85% | no |
| `research/pool_preprocessing.py` | 241/248 (97.18%) | 3 | 1 + 0 | 6 | 97.57% | no |
| `research/temporal_decision.py` | 810/836 (96.89%) | 10 | 6 + 0 | 20 | 97.59% | no |
| `research/typed_benchmark.py` | 175/180 (97.22%) | 2 | 1 + 0 | 4 | 97.77% | no |
| `research/uci_loader.py` | 180/186 (96.77%) | 3 | 1 + 0 | 5 | 97.30% | no |
| `src/etl_benchmark/load.py` | 13/14 (92.86%) | 1 | 0 + 1 | 0 | 100.00% | yes |
| `src/etl_benchmark/quality/_torch_models.py` | 58/65 (89.23%) | 6 | 0 + 0 | 7 | 89.23% | no |
| `src/etl_benchmark/quality/autoencoder.py` | 112/117 (95.73%) | 3 | 2 + 0 | 3 | 97.39% | no |
| `src/etl_benchmark/quality/base.py` | 30/31 (96.77%) | 1 | 0 + 1 | 0 | 100.00% | yes |
| `src/etl_benchmark/quality/deep.py` | 60/62 (96.77%) | 1 | 2 + 0 | 0 | 100.00% | yes |
| `src/etl_benchmark/quality/drift.py` | 119/129 (92.25%) | 8 | 0 + 0 | 10 | 92.25% | no |
| `src/etl_benchmark/quality/gx.py` | 87/98 (88.78%) | 10 | 0 + 0 | 11 | 88.78% | no |
| `src/etl_benchmark/quality/ml.py` | 239/259 (92.28%) | 15 | 1 + 0 | 19 | 92.64% | no |
| `src/etl_benchmark/quality/rules.py` | 112/119 (94.12%) | 5 | 0 + 0 | 7 | 94.12% | no |
| `src/etl_benchmark/quality/window_drift.py` | 225/233 (96.57%) | 4 | 1 + 0 | 7 | 96.98% | no |
| `src/etl_benchmark/quality/windows.py` | 54/57 (94.74%) | 2 | 1 + 0 | 2 | 96.43% | no |
| `verification/mutation_scope.py` | 240/246 (97.56%) | 2 | 6 + 0 | 0 | 100.00% | yes |

The four already accepted LSTM records are not new proposals and are excluded from the table’s hypothetical. If the official validator accepted all four in a compatible campaign, its hypothetical score would be 368/373 = 98.66%; this has not been established on the present machine. No owner decision is requested on any item before the underlying per-mutant evidence is checked.

## Environment and integrity

The PyTorch CPU wheel index lists `torch-2.15.0+cpu-cp311-cp311-manylinux_2_28_x86_64.whl` and the corresponding aarch64 wheel ([official index](https://download.pytorch.org/whl/cpu/torch/)). Availability in the index does not validate a campaign. The validator checks every recorded environment key for exact equality; this host cannot satisfy the Linux CPU build identifier and its Docker daemon was unavailable. No compatible validator run was made in this session. An earlier hosted Linux diagnostic at commit `3dbf6f5` did accept all four records using the official validator and reported 368/373 adjusted; it is historical evidence and does not establish validity for the current test tree. See `MUTATION_DIAGNOSTIC_RUN_42985826795.md`.

The test guards for pool-file hashing enforce termination after EOF and verify the digest; the cache graph test verifies the exact visited callers and a finite traversal. Their budgets are fixture safeguards, not production runtime guarantees. The broad autouse read budget also limits every binary read in that test module, so a future legitimate fixture larger than the budget could fail; the current fixtures are small. Focused pool, cache and owner-packet tests passed locally.

The manuscript already warns that full-rank PCA rows are not numerically robust. The historical synthetic result remains approximately 0.5645 in one recorded environment versus 0.4818 in another. The comparison changes the packaging environment as well as the numerical backend; backend sensitivity is supported but a single isolated cause is not proven. The constructor test does not resolve this discrepancy. Preserve the archive and seek owner review of interpretation; see `PCA_REPRODUCIBILITY_2026-11-12.md`.

## Remaining work

Investigate all remaining survivors by behavioral mechanism and preserve counterexamples, dependency versions, source digests and exact verdicts. Establish whether each proposal is supportable; do not reopen prior owner decisions. Remeasure changed units and then perform a fresh complete campaign with per-execution provenance. Obtain a compatible Linux validator run, independent critical review after corrections, full verification and exact-final-commit CI. Official DEEP and release checks remain unrun. Thresholds, scope, risk classifications and equivalence records have not been changed in this checkpoint.

## Targeted GX regression after the historical measurement

An index may have the same name as a data column. In the preserved generated
mutant source, `_failures_per_row__mutmut_5` (`drop=True` to `drop=None`) and
`_failures_per_row__mutmut_6` (`drop=True` to `drop=False`) raise `ValueError`
for a probe whose index and column are both named `amount`; the original
returns `[False, True]` and preserves the index. The new public-contract test
`test_gx_handles_index_named_like_a_data_column` reproduces both failures
when run with each `MUTANT_UNDER_TEST` and the generated `mutants/src` on
`PYTHONPATH` (each exits 1), and passes on the original as part of
`pytest tests/test_gx.py tests/test_detector_contracts.py tests/test_detector_state_contracts.py`
(41 passed). Ruff lint and format checks of the changed test passed. These are
two directly demonstrated behavioral differences, not a fresh native unit
measurement or two amended archived verdicts. The table above remains the
historical snapshot. The new test changes the test tree, so that snapshot
cannot be represented as a measurement of the current worktree.

GX probe environment: macOS arm64, Python 3.11.17, NumPy 2.4.6, pandas 3.1.1, Great Expectations 1.24.1, mutmut 3.8.0, pytest 9.1.1; `gx.py` SHA-256 `11be59dbe975d05547395263b763d37716cd9f916b284ce4147cfd87c61e3416`.

Independent partial review returned CHANGES_REQUIRED on the archive-file count
and the overlap wording. Both statements were corrected after the review;
the reviewer did not review those corrections or the GX regression. The
archive also contains an unrelated nested test-fixture metadata file, which
is not included in the 98 campaign files. This is not a final independent
review of the campaign.

A full `~/.cache/etl-mutation-venv/bin/python -m pytest --disable-warnings`
run on the changed test tree exited 1: 4,013 passed, 23 deselected, and one
failed after 451.65 seconds. The failing real-data Cardio reproduction test
expected `NUMERICAL` on the archive's platform but obtained `STATISTICAL`.
The same test passed in the canonical conda `etl-benchmark` environment
(1 passed in 30.24 seconds). These environments differ, including pandas
3.1.1 versus 3.0.6 and torch 2.15.0 versus 2.14.1; the cause was not isolated.
The failed run is not a full-suite pass and does not establish that all
same-platform environments reproduce the archive numerically. It is separate
from the synthetic PCA discrepancy and remains a reproducibility concern.

Subsequent preliminary triage lists all 162 formerly unclassified identities
in `evidence/unclassified-triage-2026-11-14.json`. Three have demonstrated
behavioral differences: the two GX index collisions above and
`research.multi_schema.x__per_type__mutmut_2`. For the latter, directly calling
the generated original and mutant on rows `clean`, `missing_value`, and
`duplicate`, with flags `[True, True, False]`, gives missing-value precision
0.5 and 1.0 respectively. The remaining 159 are explicitly inconclusive:
their mutation text was inspected, but no behavioral or equivalence verdict
is claimed. These are preliminary outcomes, not a substitute for completing
individual investigation and native remeasurement.

The Cardio failure was traced to differing parsed floating-point inputs in
the two pandas builds; controlled replays and limitations are documented in
`CARDIO_PANDAS_REPRODUCIBILITY_2026-11-14.md`. The initial full-suite failure
remains a failure; neither the test nor the archive was changed.

A subsequent complete native rerun of the 98 GX mutants finished with exit 0
on the default case-insensitive macOS filesystem: 89 killed and nine survived
(90.82%; eight more kills needed at L4/98%). Both index-collision mutants
changed from survived to killed. The retained per-mutant metadata and run
environment are in `evidence/gx-focused-2026-11-14.json`. The historical
case-sensitive unit was 87/98; this later run used a different filesystem and
test tree and must not be spliced into the historical aggregate. The run
preceded the subsequent multi-schema test addition.

The multi-schema precision difference now has the regression
`test_per_type_precision_uses_clean_rows_and_excludes_other_anomaly_types`.
Against the generated mutant the test failed with precision 1.0 rather than
0.5; against the original, the affected GX and multi-schema test files passed
(43 tests). This direct check is not a full multi-schema unit remeasurement.
The native engine subsequently reran that one multi-schema mutant and recorded
a kill with exit status 0; see `evidence/multi-schema-focused-2026-11-14.json`.
This is still not a complete multi-schema unit measurement.

The historical Linux diagnostic's `research/lstm_detector.py` has the same
SHA-256 as the current source (`277375e66d1edc6ed94c5ffc4b1074c113e86c6095c7dc2b20d3058cb006da18`),
but mutation policy code and risk-policy content changed after that diagnostic.
The old validator outcome therefore remains historical, not exact-current-head
verification.

The complete suite was also run on the changed test tree with
`~/miniconda3/envs/etl-benchmark/bin/python -m pytest --disable-warnings`:
4,015 passed, 23 deselected, exit 0 in 540.47 seconds. This canonical
conda result does not erase the mutation-environment Cardio failure above.
Repository-wide Ruff lint and format checks passed after the test changes.

## Current Linux diagnostic routing

The current 45-shard plan generated from the unchanged risk policy and shard
weights assigns `research/lstm_detector.py` to shard 33. The existing
`run:mutation-shard-diagnostic` workflow hardcodes shard 31, which currently
contains `research/dataset_registry.py`, `research/normalise.py`, and
`src/etl_benchmark/quality/windows.py`. Triggering that diagnostic on this
revision would not exercise LSTM. A full sharded campaign would run the
relevant shard but has not been launched while the remaining triage and
measurement gaps are open. The historical Linux validation cited above is
not changed or promoted to current-head evidence.

The first newly authorized independent review call ended with a provider
usage-limit error after partial observations. It produced no final review
verdict and is not independent approval. One further model-review call remains
within the owner's two-call budget.

The second and final authorized independent review returned PASS for the
bounded checkpoint. It independently reconciled the historical inventory and
packet partition, focused GX and multi-schema results, score arithmetic,
Cardio and PCA interpretation, Linux shard routing, and unchanged release
controls. It did not certify the campaign. It noted two non-blocking
provenance limits: the test-tree hash excludes non-Python files and caches,
and the compact multi-schema artifact lacks an explicit HEAD and native-log
digest. A later tie-ordering regression and its results were added after that
review and are outside its scope. The remaining inconclusive survivors,
current-head Linux LSTM validation, fresh campaign, DEEP, release and
exact-final-commit CI remain open.

After the bounded independent review, two `research.pool_chrono` survivors
(`x_eligible__mutmut_3` and `_5`) were shown to change chronological
eligibility when all timestamps tie. The original keeps input order and finds
30 positives in the test partition; both mutants find only two and exclude
the data in the tested environment. The regression failed against both
mutants and passed with the original (17 affected tests passed). A native
focused two-mutant run recorded both kills; see
`evidence/pool-chrono-focused-2026-11-14.json`. It is not a complete unit
rerun. The preliminary 162-record triage now contains five focused kills and
157 inconclusive entries. These later changes were not covered by the bounded
independent review, which assessed the earlier three-kill snapshot.

Verification details for the post-review pool regression:

- RED: with `MUTANT_UNDER_TEST` set separately to
  `research.pool_chrono.x_eligible__mutmut_3` and
  `research.pool_chrono.x_eligible__mutmut_5`, run pytest with generated
  `research.pool_chrono` preloaded as `pool_chrono`, `-c /dev/null`,
  `--import-mode=importlib`, `-p no:cacheprovider`, and the node
  `research/tests/test_pool_chrono_contracts.py::test_eligibility_preserves_input_order_when_timestamps_tie`;
  both exited 1 with the expected wrong eligibility result. The local logs are
  `/tmp/etl-pool-tie-red.log` and `/tmp/etl-pool-tie-red5.log`.
- GREEN and REGRESSION: `~/.cache/etl-mutation-venv/bin/python -m pytest
  research/tests/test_pool_chrono_contracts.py research/tests/test_pool_chrono.py
  --disable-warnings` exited 0, 17 passed. The native focused command and
  exact mutant identities are recorded in the pool-focused JSON, with exit 0.
- `~/.cache/etl-mutation-venv/bin/ruff check .`, `ruff format --check .`,
  `git diff --check`, policy-file comparisons and the 162-ID/source-digest
  reconciliation all passed after this test was added. The canonical full
  suite is rerun on the new test tree before publication of this checkpoint.

After adding the pool tie-order regression, the complete canonical conda suite
was rerun: `~/miniconda3/envs/etl-benchmark/bin/python -m pytest
--disable-warnings` exited 0 with 4,016 passed and 23 deselected in 463.35
seconds. This later test and its evidence postdate the bounded review. The
separate mutation-environment Cardio failure remains unresolved as a numerical
reproduction failure.

Two further regressions were added after the bounded review. A numeric carrier
whose index shares a feature name must still be injectable: mutants
`research.injection.x_inject__mutmut_21` and `_27` instead raise `ValueError`.
For multi-schema H4, a mean Spearman agreement exactly equal to 0.7 supports
the preregistered inclusive threshold; mutant
`research.multi_schema.x_hypotheses__mutmut_91` rejects it. The three RED
checks exited 1 for those behavioral differences; the affected original-code
suite exited 0 with 36 passed. A native focused run killed all three (exit 0),
with exact identities, source and test-tree digests and environment in
`evidence/injection-h4-focused-2026-11-14.json`. The 162-record preliminary
triage now contains eight focused kills and 154 inconclusive entries. These
focused runs are not complete unit or campaign measurements and postdate the
bounded independent review.

For the injection and H4 additions, RED used pytest with the generated module
preloaded as `injection` or `multi_schema`, respectively, and
`MUTANT_UNDER_TEST` set to each exact identity in the focused JSON. The nodes
were `research/tests/test_injection_contracts.py::test_injection_accepts_an_index_named_like_a_carrier_feature`
and `research/tests/test_multi_schema_contracts.py::test_h4_includes_the_exact_rank_agreement_threshold`.
Each exited 1 for the stated difference (local logs `/tmp/etl-injection-red.log`,
`/tmp/etl-injection-red27.log`, `/tmp/etl-h4-red.log`). GREEN and REGRESSION:
`~/.cache/etl-mutation-venv/bin/python -m pytest
research/tests/test_multi_schema_contracts.py research/tests/test_injection_contracts.py
--disable-warnings` exited 0, 36 passed. The focused native command and exit
status are recorded in the focused JSON. The complete canonical suite is being
rerun on this later test tree.

After the injection and H4 regressions, the complete canonical suite
`~/miniconda3/envs/etl-benchmark/bin/python -m pytest --disable-warnings`
exited 0 with 4,018 passed and 23 deselected in 707.39 seconds. These later
changes and this run postdate the bounded independent review; the
mutation-environment Cardio failure remains recorded separately.

## Diagnostic routing checkpoint

The diagnostic route now looks up a requested module in the validated generated
45-shard plan. The PR diagnostic label selects `research/lstm_detector.py`; a
manual dispatch can specify `diagnostic_module`. An absent module or a damaged
plan fails the plan job; a diagnostic never runs the aggregate. The current
plan locates LSTM in shard 33, but that index must be recomputed for each plan.
This routing change is verification infrastructure and requires independent
review; the authorized independent-review budget is exhausted. It is not a
Linux validator result or certification. The change does not alter manuscript
or slide scientific claims, so no publication artifact update is warranted.

The repository's `environment.yml` specifies `pandas>=2.0`, not an exact
pandas version or build, and therefore does not by itself reproduce the
observed canonical parsing. The canonical conda environment and the saved
Cardio diagnostics remain evidence for the particular successful replay; no
parser pin or scientific conclusion has been changed. Synthetic PCA remains
a separate numerical-instability investigation.
