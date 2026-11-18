# Classical model initial-state counterexamples

Seven historical survivors in `src/etl_benchmark/quality/ml.py` (source SHA-256
`4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`)
change initial learned fields of the directly usable `TailProbabilityModel` or
`PCAReconstruction`:

- `etl_benchmark.quality.ml.xǁTailProbabilityModelǁ__init____mutmut_3` changes
  `sorted_` to `None`; pre-fit scoring changes from `IndexError` to
  `AttributeError`, and zero-feature scoring changes from zeros to an error.
- `_5` and `_6` change `sorted_` from shape `(0, 0)` to `(1, 0)` or `(0, 1)`.
  `_6` changes the pre-fit indexing error; `_5` exposes a different initial
  learned-array shape even where tested method outcomes match.
- `_7` changes `skew_sign_` to `None`; zero-feature pre-fit scoring changes
  from zeros to `TypeError`. `_9` allocates a one-element uninitialized array
  instead of an empty one, exposing a different initial learned-array shape.
- `_10` changes `threshold_` from NaN to `None`. After fitting fails on an
  invalid contamination, direct prediction returns zero flags on the original
  and raises `TypeError` on the mutant.
- `etl_benchmark.quality.ml.xǁPCAReconstructionǁ__init____mutmut_9` has the
  analogous threshold difference after failed fit.

Direct generated-constructor probes compared pre-fit score/predict, zero-feature
input, successful fit, and failed-fit prediction under Python 3.11.17, NumPy
2.4.6, SciPy 1.17.1 and pandas 3.0.6/3.1.1 on macOS arm64. Scripts and raw
outputs are `tail-init.py.txt`, `tail-init-output.txt`,
`tail-init-zero-before.py.txt` and `tail-init-zero-before-output.txt` in
`evidence/continuation-2026-11-15/`. Generated source is archived in
`evidence/pending-probes-2026-11-15/ml-generated.py.gz`.

The higher-level PyOD adapter guards pre-fit scoring and normally uses valid
contamination. The significance of direct pre-fit attributes, zero-feature
inputs and use after failed fit is not established by the supported public
contract. All seven remain **inconclusive**, rather than being proposed as
exclusions or given tests that merely encode incidental error behavior. The
separate synthetic PCA numerical instability and archived results are unchanged.
