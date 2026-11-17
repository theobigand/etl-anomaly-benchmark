# Ratification of the delegated equivalence records, 2026-11-17

Decision packet for the owner. The final mutation campaign (run 44045848118) passes with 101 exclusions in
`verification/mutation_equivalence.json`: 4 owner records of 2026-11-11 (LSTM) and 97 records of 2026-11-17
that were decided under the owner's delegation. A model review is not a human scientific approval, and these
records are sole-author decisions (`sole_author_owner_review`), not independent peer review. Nothing in this
file changes a record. To revoke a record, set its `verdict` to `rejected` (the validator then counts the
mutant by its actual outcome) and rerun the campaign aggregation; to keep it, do nothing.

| Basis | Records | Meaning |
| --- | ---: | --- |
| analysis | 88 | a recorded technical argument, most with a direct check (with the 2 device records below, the 90 analysis-backed records of the closure report) |
| owner's word | 7 | equivalence neither shown nor refuted; behaviour differs only outside supported use |
| device-dependent | 2 | equivalent only on the CPU-only PyTorch build of the campaign |

## 1. The seven records on the owner's word

Technical recommendation: ACCEPT all seven as exclusions that do not hide a defect in supported use. Their
units need this number of owner-word records, together with the analysis-backed ones, to reach the threshold. They
were taken in identifier order among the survivors not shown equivalent, so another set of the same size would give
the same compliance; revoking any one of them fails its unit because the units have no slack.

| Mutant | Unit | Change | Why it is not shown equivalent | Slack | Recommendation |
| --- | --- | --- | --- | ---: | --- |
| `_torch_models.PaddedAE1SVM.fit__mutmut_11` | `src/etl_benchmark/quality/_torch_models.py` | `return super().fit(X, y)  →  return super().fit(X, None)` | differs only when a caller passes labels `y`; the only caller never does | 0 | ACCEPT, caveat: unsupported-state difference |
| `autoencoder.ReconstructionModel.__init____mutmut_4` | `src/etl_benchmark/quality/autoencoder.py` | `self.threshold_: float \| None = None  →  self.threshold_: float \| None = ""` | initial `threshold_` read before fitting, or after a failed fit | 0 | ACCEPT, caveat: unsupported-state difference |
| `ml.PCAReconstruction.__init____mutmut_9` | `src/etl_benchmark/quality/ml.py` | `self.threshold_ = float("nan")  →  self.threshold_ = None` | initial `threshold_` read before fitting, or after a failed fit | 0 | ACCEPT, caveat: unsupported-state difference |
| `ml.PyODDetector.__init____mutmut_4` | `src/etl_benchmark/quality/ml.py` | `self.feature_names_: list[str] \| None = None  →  self.feature_names_: list[str] \| None = ""` | initial `feature_names_` read before fitting | 0 | ACCEPT, caveat: unsupported-state difference |
| `ml.TailProbabilityModel.__init____mutmut_10` | `src/etl_benchmark/quality/ml.py` | `self.threshold_ = float("nan")  →  self.threshold_ = None` | initial learned array/threshold read before fitting, or after a failed fit | 0 | ACCEPT, caveat: unsupported-state difference |
| `ml.TailProbabilityModel.__init____mutmut_3` | `src/etl_benchmark/quality/ml.py` | `self.sorted_ = np.empty((0, 0))  →  self.sorted_ = None` | initial learned array/threshold read before fitting, or after a failed fit | 0 | ACCEPT, caveat: unsupported-state difference |
| `ml.TailProbabilityModel.__init____mutmut_5` | `src/etl_benchmark/quality/ml.py` | `self.sorted_ = np.empty((0, 0))  →  self.sorted_ = np.empty((1, 0))` | initial learned array/threshold read before fitting, or after a failed fit | 0 | ACCEPT, caveat: unsupported-state difference |

## 2. The two device-dependent records

Technical recommendation: ACCEPT only as environment-bound exclusions; REJECT as general equivalence. Passing
`None` to `.to()` changes nothing on a CPU-only build but selects no device where one exists, which the public
`estimator_kwargs` allow. Both are killed on an Apple MPS device. They bind `torch 2.15.0+cpu` and are rejected
by the validator on any other build.

| Mutant | Unit | Change | Slack |
| --- | --- | --- | ---: |
| `_torch_models.FitScalerDIF._deep_representation__mutmut_14` | `src/etl_benchmark/quality/_torch_models.py` | `reduced.append(net(batch.float().to(self.device)))  →  reduced.append(net(batch.float().to(None)))` | 0 |
| `_torch_models.MeanVAE.evaluating_forward__mutmut_3` | `src/etl_benchmark/quality/_torch_models.py` | `mu, _ = self.model.encode(batch_data.to(self.device))  →  mu, _ = self.model.encode(batch_data.to(None))` | 0 |

## 3. Units with no slack

Revoking any single record of these units makes the unit fall below its threshold. Recommendation: ACCEPT each
analysis-backed record; the owner-word and device records of these units are those of sections 1 and 2.

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

## 4. Records whose reasoning needs your attention

- **Contradiction with the LSTM records.** The 2026-11-11 records keep `replace=None` and `astype(None)` as
  inconclusive, noting that the argument does not hold across the supported dependency range, while the
  delegated records accept the same operators on arguments verified on pandas 3.0.6 and 3.1.1 and numpy 2.4.6.
  The LSTM choice is the more conservative. Recommendation: leave the LSTM records as they are; the delegated
  ones bind the verified versions, so they cannot silently outlive a dependency change.
- **Unbound dependencies.** The eight `gx.py` records rely on Great Expectations 1.24.x behaviour and one
  `ml.py` record on `scipy.stats.skew`; the campaign environment record does not capture those versions, so the
  validator cannot enforce them. Recommendation: ACCEPT, with the limit stated in each record.
- **Review.** Two separate-context model reviews of the batch led to the removal of four records that a test
  could kill and to corrections of wording, bases and environment bindings. Their texts are not archived.

## 5. If you revoke

A revoked record turns its mutant back into a counted survivor. Of the 21 units with exclusions, 12 can lose at
least one record and still pass (see the `Revocable` column of the closure report); the 9 units of section 3
fail at the first revocation, and a failed unit closes the aggregate. The release gate is closed regardless.
