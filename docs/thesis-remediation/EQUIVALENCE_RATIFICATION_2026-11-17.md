# Ratification of the delegated equivalence records, 2026-11-17 (reviewed 2026-11-18, updated after the failed-fit correction)

Decision packet for the owner. The certified campaign (`verify-release` run 44303335021, revision `7c0af40`) passes
with 98 exclusions in `verification/mutation_equivalence.json`: 4 owner records of 2026-11-11 (LSTM) and 94 records of
2026-11-17 that were decided under the owner's delegation. A model review is not a human scientific approval, and these
records are sole-author decisions (`sole_author_owner_review`), not independent peer review. This file changes no
owner-governed verdict. To revoke a record, set its `verdict` to `rejected` (the validator then counts the mutant by its
actual outcome) and rerun the campaign aggregation; to keep it, do nothing. The review of 2026-11-18 (section 6) was
done by the assistant with direct probes and deterministic checks, not by an independent reviewer.

**What changed since the first version of this packet.** The review found that `PyODDetector.fit` left a half-fitted detector
when it raised. It was corrected (`5de925a`), `ml.py` was remeasured natively (248/261), and its records were rebound
(`401c7bf`). Consequences: three accepted records (`PyODDetector.__init____mutmut_4`, `_5`, `_6`) are now killed and were set back to
`proposed` with an empty approver and date, each with the technical finding; the two records that carried the "owner
judgment" label are no longer observable through a public detector (section 1). No other record changed its verdict, and
the LSTM records and the two CPU-only records are untouched.

| Basis | Records | Meaning |
| --- | ---: | --- |
| analysis | 86 | a recorded technical argument, most with a direct check |
| owner's word | 6 | equivalence neither shown nor refuted; behaviour differs only outside supported use |
| device-dependent | 2 | equivalent only on the CPU-only PyTorch build of the campaign |

Together with the 4 accepted LSTM records, 98 exclusions.

## 1. The six records on the owner's word

The records say "outside the supported use of the unit". The review checked each against the code, the public interface
(`quality/__init__.py` exports detectors only; none of these classes), the registry, and a direct probe of the original and
of the mutant on the public detectors (`evidence/final-review-2026-11-18/`). Classes: **defensible** under a stated
contract; **owner judgment** where the difference is observable through a public detector; none is demonstrably
non-equivalent within a documented supported use. Revocation consequence is the unit after revoking that record alone,
against the 98% L4 threshold (after the correction: `ml.py` is 248/252, slack 1); a failed unit fails the DEEP profile and the release gate.

| Mutant | Observable difference | Contract available | Class | Revocation consequence |
| --- | --- | --- | --- | --- |
| `_torch_models.PaddedAE1SVM.fit__mutmut_11` (`fit(X, y)` to `fit(X, None)`) | labels reach PyOD: a warning and the `n_classes_` of `predict_proba` change (3 columns against 2 in the earlier probe); nothing in the project reads either | class is in the private module `_torch_models`, not exported; `Detector.fit(df)` has no label parameter; PyOD documents `y` as ignored | defensible | `_torch_models.py` 58/60 = 96.67%, fails |
| `autoencoder.ReconstructionModel.__init____mutmut_4` (`threshold_` `None` to `""`) | after a fit that failed on invalid contamination, `predict` raises `TypeError` in the original and `UFuncTypeError` (a `TypeError` subclass) in the mutant; same flags after a valid fit | `ReconstructionModel` is not exported; caveat: the declared type is `float \| None`, which `""` violates | defensible, with the type caveat | `autoencoder.py` 112/115 = 97.39%, fails |
| `ml.TailProbabilityModel.__init____mutmut_3` (`sorted_` to `None`) | direct pre-fit scoring raises `AttributeError` instead of `IndexError`; unobservable through a public detector (`fit` assigns `sorted_` before anything reads it) | internal estimator, not exported; pre-fit use errors in both | defensible | `ml.py` 97.98%, fails |
| `ml.TailProbabilityModel.__init____mutmut_5` (`sorted_` shape `(0, 0)` to `(1, 0)`) | only the initial array shape; no method outcome differs; unobservable through a public detector | same | defensible | `ml.py` 97.98%, fails |
| `ml.TailProbabilityModel.__init____mutmut_10` (`threshold_` `nan` to `None`) | before the correction, after a failed fit `ECODDetector`/`COPODDetector.predict` returned all-False flags in the original and raised `TypeError` in the mutant. After it a failed fit leaves the detector unfitted in both, so no public detector exposes `threshold_` before a successful fit (`evidence/failed-fit-correction-2026-11-18/`, `evidence/final-review-2026-11-18/failed-fit-and-prefit-probe-output.txt` for the earlier behaviour) | `threshold_` before a fit is the declared initial state of an internal estimator; contamination range 1e-4 to 0.5 remains the documented input bound | defensible after the correction; was owner judgment | `ml.py` 248/253 = 98.02%, passes; with the next record 248/254 = 97.64%, fails |
| `ml.PCAReconstruction.__init____mutmut_9` (`threshold_` `nan` to `None`) | same, through `PCADetector` | same | same | same |

Why the last two were singled out, and what the correction changed. The mutant was not the defect; the original was.
`PyODDetector.fit` assigned `self._model` before the model had been fitted, so a failed fit left a detector that passed
the "not fitted" guard and, for ECOD, COPOD and PCA, flagged nothing (`threshold_` stayed `nan`; `score > nan` is false). The
registry keeps every project run inside the contamination bounds, so no archived result was affected. The fix (`5de925a`) makes a
fit that raises leave the detector as it was, with regression tests through the public API (`tests/test_detector_failed_fit.py`,
nine detectors). After it the situation that distinguished these two records can no longer be reached, so the exclusions no
longer hide a behavioural difference. They are still exclusions on the owner's word, not killed mutants: a unit test of the
initial `threshold_` would kill them but changes the test tree and needs a new campaign.

Recommendation: ACCEPT the six records on the owner's word (`PaddedAE1SVM.fit__mutmut_11`, `ReconstructionModel.__init____mutmut_4`,
`TailProbabilityModel.__init____mutmut_3`, `_5` and `_10`, `PCAReconstruction.__init____mutmut_9`). `ml.py` has slack 1: at most one
of the last two can be revoked without failing the unit.

The seventh record of the earlier packet, `PyODDetector.__init____mutmut_4` (`feature_names_` `None` to `""`), is killed by a
failed-fit test since the correction, together with `__init____mutmut_5` and `_6` (analysis-backed records of 2026-11-17). The three are back to
`proposed` with an empty approver and date and a technical finding in each record; they are ignored by the validator. The owner
can confirm this state or remove the three records.

## 2. The two device-dependent records

Technical recommendation: RETAIN strictly as exclusions bound to `torch 2.15.0+cpu`; REJECT as general equivalence.

| Mutant | Unit | Change | Slack |
| --- | --- | --- | ---: |
| `_torch_models.FitScalerDIF._deep_representation__mutmut_14` | `src/etl_benchmark/quality/_torch_models.py` | `net(batch.float().to(self.device))` to `.to(None)` | 0 |
| `_torch_models.MeanVAE.evaluating_forward__mutmut_3` | `src/etl_benchmark/quality/_torch_models.py` | `self.model.encode(batch_data.to(self.device))` to `.to(None)` | 0 |

- **Binding is enforced.** Fed the certified campaign's own records, the repository validator accepts the certified
  runtime and rejects the evidence for torch `2.15.0`, `2.14.1`, `2.15.0+cu128` and an absent torch, and equally for
  pandas 3.1.1, scipy 1.17.0, great-expectations 1.24.1 and pyod 3.6.8 (`validator-binding-probe-output.txt`).
  The rejection is of the whole campaign, not only of the record, so the exclusion cannot silently carry over to another build.
- **Equivalence is not general.** `.to(None)` keeps the tensor where it is; the public `estimator_kwargs` accept a
  `device`, and both mutants are killed on Apple MPS (`TORCH_DEVICE_MUTANTS_2026-11-15.md`). CUDA is untested. The
  software therefore supports devices on which these two lines are tested only where such a device exists; the hosted CPU
  campaign hides the difference. The exclusion records a gap in the CI host, not a property of the code.
- **Revocation.** `_torch_models.py` falls to 58/60 = 96.67% for one record and 58/61 = 95.08% for both, so the unit fails
  unless the mutants are killed.
- **Alternative to revocation.** A CPU-feasible killer exists: with `device="meta"` the original runs
  and the mutant raises `RuntimeError: Tensor on device meta is not on the expected device cpu` (checked on torch 2.14.1;
  not on 2.15.0+cpu, not added to the tests). It would remove the dependence on the build. If the owner's policy requires
  correctness on every supported device, the alternatives are that test or revocation.

## 3. Units with no slack

Revoking any single record of these eight units makes the unit fall below its threshold (certified run 44303335021). `ml.py`
(9 excluded, 248/252 = 98.41%) left the list: it now has slack 1.

| Unit | Level | Excluded | Adjusted | Analysis | Owner's word | Device |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `src/etl_benchmark/load.py` | L4 | 1 | 100.0% | 1 | 0 | 0 |
| `src/etl_benchmark/quality/_torch_models.py` | L4 | 6 | 98.31% | 3 | 1 | 2 |
| `src/etl_benchmark/quality/autoencoder.py` | L4 | 3 | 98.25% | 2 | 1 | 0 |
| `src/etl_benchmark/quality/base.py` | L4 | 1 | 100.0% | 1 | 0 | 0 |
| `src/etl_benchmark/quality/deep.py` | L4 | 1 | 98.36% | 1 | 0 | 0 |
| `src/etl_benchmark/quality/drift.py` | L4 | 7 | 98.36% | 7 | 0 | 0 |
| `src/etl_benchmark/quality/windows.py` | L4 | 2 | 98.18% | 2 | 0 | 0 |
| `verification/mutation_scope.py` | L4 | 2 | 98.36% | 2 | 0 | 0 |

## 4. Reconciliation with the LSTM records

The five LSTM records of 2026-11-11 stay inconclusive and counted as survivors (`lstm_detector.py` 368/373 with the four
accepted LSTM exclusions, 2 revocable). Same-operator delegated records were compared one by one:

| LSTM record (inconclusive) | Delegated record (accepted) | Same operation | What differs |
| --- | --- | --- | --- |
| `fit__mutmut_43`, `fit__mutmut_55`: `rng.choice(n, k, replace=None)` | `injection.inject__mutmut_163`: `rng.choice(cols, size=3, replace=None)` | yes: `Generator.choice` with `replace=None` | the standard of proof only. The owner required the argument to hold across the supported dependency range; the delegated record binds numpy 2.4.6 and the validator enforces it |
| `_reconstruction_error__mutmut_35`: `ndarray.astype(None)` (float32 to float64) | `_transactions__mutmut_2`, `_66`: `ndarray.astype(None)` (int64 to float64); `Detector.score__mutmut_1` (bool or int Series) | yes: `astype(None)` | the standard of proof, and the input dtype (float32 against int or bool) |
| `_windows__mutmut_2`, `fit__mutmut_16`: `frame[columns].astype(None)` | `injection.prepare__mutmut_6`: `astype(None)` | yes | partly the input contract: the LSTM frames take arbitrary caller columns (a datetime fails in both), the delegated ones receive numeric or boolean values after upstream checks |

Conclusion: not a contradiction in the arguments but a difference of standard. The owner's decision of 2026-11-11 asked
for validity across the supported range; the delegation of 2026-11-16 asked to treat what cannot be shown to differ as
equivalent, bound to exact versions. Different input types explain only the DataFrame pair. The conservative reading is
kept: the LSTM records are not changed, and the delegated records are valid only for the bound versions. Two inconclusive
records still carry the label `{"pandas": "3.1.1"}`; the validator ignores the environment of a record that is not
accepted, so it has no effect on any count.

## 5. If you revoke

A revoked record turns its mutant back into a counted survivor. Of the 21 units with exclusions, 13 can lose at
least one record and still pass (the `Revocable` column of the closure report); the 8 units of section 3
fail at the first revocation, and a failed unit closes the aggregate: the DEEP profile fails and the gate is no longer
CERTIFIED for the next revision. The certified run of `7c0af40` and its archived report are not changed by a later revocation.

## 6. Integrity checks and remaining limits (2026-11-18)

- The 98 accepted ids of the record file equal the accepted set of the certified `deep-evidence.json` of run 44303335021
  (ledger and campaign agree: the aggregation asserts it); the equivalence document embedded in that evidence equals
  `verification/mutation_equivalence.json`; every record's `source_sha256` equals the source digest of the certified run;
  only the `ml.py` records changed since `5e57228` (rebound to the corrected source). Total: 106 records, 98 accepted,
  3 proposed, 5 inconclusive LSTM.
- Basis accounting by record text: 86 analysis, 6 owner's word, 2 device (94 delegated), plus 4 accepted and 5 inconclusive
  LSTM records.
- Dependencies. The validator compares every package a record names with the packages of the shard manifests; those include
  torch, scipy and great-expectations. The eight `gx.py` records bind great-expectations 1.24.0 and the `ml.py`
  `TailProbabilityModel.fit__mutmut_13` record binds scipy 1.17.1. Remaining limit: three `run_severity.py` records
  (`render__mutmut_24`, `_27`, `_28`) argue pixel identity under matplotlib, which is not a captured package, so the
  validator cannot enforce it (matplotlib 3.11.2 is pinned in the Linux lock).
- Review. Two earlier separate-context model reviews of the batch led to the removal of four records that a test could
  kill and to corrections of wording, bases and bindings; their texts are not archived. They are model reviews, not human approval.
  No new model review was run for the correction: it was verified by tests, a native measurement and deterministic comparisons.
- The two CPU-only records stay restricted to `torch 2.15.0+cpu`; the five inconclusive LSTM records keep their verdicts.

## 7. Recommendation in one table

| Group | Records | Recommendation |
| --- | ---: | --- |
| Supported by technical reasoning | 86 | ratify |
| On the owner's word, behaviour differs only outside the claimed use | 6 (two now unobservable after the correction) | ratify; at most one of `PCAReconstruction.__init____mutmut_9` and `TailProbabilityModel.__init____mutmut_10` can be revoked without failing `ml.py`; a test of the initial state would turn them into kills |
| Dependent on narrow environment conditions | 2 CPU-only, plus those bound to a package version | retain only as CPU-only exclusions; do not widen; or replace by a test |
| Returned to `proposed` after the correction | 3 (`PyODDetector.__init____mutmut_4`, `_5`, `_6`) | confirm the state or delete the records; they no longer exclude anything |
| LSTM records | 4 accepted, 5 inconclusive | leave as they are |
| To revoke if the contract cannot justify the exclusion | any of the above | each revocation fails its unit (sections 1, 2, 5) except where slack exists, unless a killing test is added |
