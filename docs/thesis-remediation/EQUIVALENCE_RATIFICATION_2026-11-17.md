# Ratification of the delegated equivalence records, 2026-11-17 (reviewed 2026-11-18)

Decision packet for the owner. The certified campaign (`verify-release` run 44253806652, revision `5e57228`) passes
with 101 exclusions in `verification/mutation_equivalence.json`: 4 owner records of 2026-11-11 (LSTM) and 97 records of
2026-11-17 that were decided under the owner's delegation. A model review is not a human scientific approval, and these
records are sole-author decisions (`sole_author_owner_review`), not independent peer review. Nothing in this file
changes a record. To revoke a record, set its `verdict` to `rejected` (the validator then counts the mutant by its
actual outcome) and rerun the campaign aggregation; to keep it, do nothing. The review of 2026-11-18 (section 6) was
done by the assistant with direct probes and deterministic checks, not by an independent reviewer.

| Basis | Records | Meaning |
| --- | ---: | --- |
| analysis | 88 | a recorded technical argument, most with a direct check (with the 2 device records below, the 90 analysis-backed records of the closure report) |
| owner's word | 7 | equivalence neither shown nor refuted; behaviour differs only outside supported use |
| device-dependent | 2 | equivalent only on the CPU-only PyTorch build of the campaign |

## 1. The seven records on the owner's word

The records say "outside the supported use of the unit". The review checked each against the code, the public interface
(`quality/__init__.py` exports detectors only; none of these classes), the registry, and a direct probe of the original and
of the mutant on the public detectors (`evidence/final-review-2026-11-18/`). Classes: **defensible** under a stated
contract; **owner judgment** where the difference is observable through a public detector; none is demonstrably
non-equivalent within a documented supported use. Revocation consequence is the unit after revoking that record alone,
against the 98% L4 threshold; a failed unit fails the DEEP profile and the release gate.

| Mutant | Observable difference | Contract available | Class | Revocation consequence |
| --- | --- | --- | --- | --- |
| `_torch_models.PaddedAE1SVM.fit__mutmut_11` (`fit(X, y)` to `fit(X, None)`) | labels reach PyOD: a warning and the `n_classes_` of `predict_proba` change (3 columns against 2 in the earlier probe); nothing in the project reads either | class is in the private module `_torch_models`, not exported; `Detector.fit(df)` has no label parameter; PyOD documents `y` as ignored | defensible | `_torch_models.py` 58/60 = 96.67%, fails |
| `autoencoder.ReconstructionModel.__init____mutmut_4` (`threshold_` `None` to `""`) | after a fit that failed on invalid contamination, `predict` raises `TypeError` in the original and `UFuncTypeError` (a `TypeError` subclass) in the mutant; same flags after a valid fit | `ReconstructionModel` is not exported; caveat: the declared type is `float \| None`, which `""` violates | defensible, with the type caveat | `autoencoder.py` 112/115 = 97.39%, fails |
| `ml.PyODDetector.__init____mutmut_4` (`feature_names_` `None` to `""`) | only the attribute read before a fit or after a fit that failed before assigning it; scoring stops at the "not fitted" guard in both; `deep.py` reads it as `feature_names_ or []`, identical for both | no pre-fit contract; caveat: declared type `list[str] \| None` | defensible, with the type caveat | `ml.py` 243/248 = 97.98%, fails |
| `ml.TailProbabilityModel.__init____mutmut_3` (`sorted_` to `None`) | direct pre-fit scoring raises `AttributeError` instead of `IndexError`; unobservable through a public detector (`fit` assigns `sorted_` before anything reads it) | internal estimator, not exported; pre-fit use errors in both | defensible | `ml.py` 97.98%, fails |
| `ml.TailProbabilityModel.__init____mutmut_5` (`sorted_` shape `(0, 0)` to `(1, 0)`) | only the initial array shape; no method outcome differs; unobservable through a public detector | same | defensible | `ml.py` 97.98%, fails |
| `ml.TailProbabilityModel.__init____mutmut_10` (`threshold_` `nan` to `None`) | **after a failed fit, `ECODDetector`/`COPODDetector.predict` returns all-False flags in the original and raises `TypeError` in the mutant** (probe output: `failed-fit-and-prefit-probe-output.txt`) | contamination range 1e-4 to 0.5 is a documented input bound (`config.ML_CONTAMINATION_BOUNDS`, `registry.clip_contamination`); use after a caught failure is documented neither as supported nor as unsupported; the "not fitted" guard shows the intent that an unfitted detector refuses to score | owner judgment | `ml.py` 97.98%, fails; with the next record 243/249 = 97.59% |
| `ml.PCAReconstruction.__init____mutmut_9` (`threshold_` `nan` to `None`) | same, through `PCADetector` | same | owner judgment | same |

Why the last two differ from the rest. The mutant is not the defect; the original is. `PyODDetector.fit` assigns
`self._model` before the model has been fitted, so a failed fit leaves a detector that passes the "not fitted" guard
and, for ECOD, COPOD and PCA, flags nothing (`threshold_` stays `nan`; `score > nan` is false). The PyOD-native
detectors reject the same contamination at fit and then report "not fitted". The registry keeps every project run inside
the contamination bounds, so no archived result is affected, and no behaviour was changed.

Technical recommendation: ACCEPT the five defensible records. For the last two, accept only if the owner takes the
contamination bounds as the documented precondition of these detectors; otherwise fix the cause (assign `_model` after a
successful fit, or validate the contamination in the constructor). The fix changes `ml.py`, so its twelve records must be
rebound, the test-first regression test is written then, and the DEEP profile is rerun; it was not applied here because it
would invalidate the certified evidence and exceeds the closing scope. Slack of every unit involved is 0.

A cheap, legitimate test also exists for the two typed-attribute records (`threshold_ is None`, `feature_names_ is None`
before a fit, which is the declared initial state); it would turn two exclusions into kills. Not added, for the same reason.

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

Revoking any single record of these units makes the unit fall below its threshold (certified run).

| Unit | Level | Excluded | Adjusted | Analysis | Owner's word | Device |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `src/etl_benchmark/load.py` | L4 | 1 | 100.0% | 1 | 0 | 0 |
| `src/etl_benchmark/quality/_torch_models.py` | L4 | 6 | 98.31% | 3 | 1 | 2 |
| `src/etl_benchmark/quality/autoencoder.py` | L4 | 3 | 98.25% | 2 | 1 | 0 |
| `src/etl_benchmark/quality/base.py` | L4 | 1 | 100.0% | 1 | 0 | 0 |
| `src/etl_benchmark/quality/deep.py` | L4 | 1 | 98.36% | 1 | 0 | 0 |
| `src/etl_benchmark/quality/drift.py` | L4 | 7 | 98.36% | 7 | 0 | 0 |
| `src/etl_benchmark/quality/ml.py` | L4 | 12 | 98.38% | 7 | 5 | 0 |
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

A revoked record turns its mutant back into a counted survivor. Of the 21 units with exclusions, 12 can lose at
least one record and still pass (the `Revocable` column of the closure report); the 9 units of section 3
fail at the first revocation, and a failed unit closes the aggregate: the DEEP profile fails and the gate is no longer
CERTIFIED for the next revision. The certified run of `5e57228` and its archived report are not changed by a later revocation.

## 6. Integrity checks and remaining limits (2026-11-18)

- The 101 accepted ids of the record file equal the accepted set of the certified `deep-evidence.json`; the equivalence
  document embedded in that evidence equals `verification/mutation_equivalence.json` byte for byte; every record's
  `source_sha256` equals the source digest of the certified run; the 21 units are unchanged since `5e57228`.
- Basis accounting by record text: 88 analysis, 7 owner's word, 2 device (97 delegated), plus 4 accepted and 5
  inconclusive LSTM records, 106 records in all.
- Dependencies. The validator compares every package a record names with the packages of the shard manifests; those now
  include torch, scipy and great-expectations (the 2026-11-17 note that the validator could not enforce scipy or
  great-expectations no longer applies). The eight `gx.py` records bind great-expectations 1.24.0 and the `ml.py`
  `TailProbabilityModel.fit__mutmut_13` record binds scipy 1.17.1. Remaining limit: three `run_severity.py` records
  (`render__mutmut_24`, `_27`, `_28`) argue pixel identity under matplotlib, which is not a captured package, so the
  validator cannot enforce it (matplotlib 3.11.2 is pinned in the Linux lock).
- Review. Two earlier separate-context model reviews of the batch led to the removal of four records that a test could
  kill and to corrections of wording, bases and bindings; their texts are not archived. They are model reviews, not human approval.

## 7. Recommendation in one table

| Group | Records | Recommendation |
| --- | ---: | --- |
| Supported by technical reasoning | 88 + 5 defensible of the 7 | ratify |
| Dependent on narrow environment conditions | 2 CPU-only, plus those bound to a package version | retain only as CPU-only exclusions; do not widen; or replace by a test |
| Behaviour differs only outside the claimed use | the same 5 | ratify; two of them also benefit from a test of the declared initial state |
| Needing the owner's judgment | `PCAReconstruction.__init____mutmut_9`, `TailProbabilityModel.__init____mutmut_10` | decide whether the contamination range is the documented precondition; else fix the cause |
| To revoke if the contract cannot justify the exclusion | any of the above | each revocation fails its unit (section 1, 2, 5) unless the cause is fixed or a killing test is added |
