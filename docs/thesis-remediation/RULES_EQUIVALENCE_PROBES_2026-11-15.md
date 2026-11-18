# Rule detector training-flag probes

Two formerly inconclusive mutants are proposed equivalents for owner review;
neither is approved, excluded from official scores, nor independently reviewed.

- `etl_benchmark.quality.rules.xǁZScoreDetectorǁ_zscores__mutmut_8`
- `etl_benchmark.quality.rules.xǁIQRDetectorǁ_exceedance__mutmut_9`

Both change the call to `numeric_features` from `training=False` to
`training=None`. The observable contract is that a fitted detector checks
numeric prediction data, rejects missing, nonnumeric or infinite features,
and computes its score or flags, while prediction may contain missing values.
The only use of `training` in that helper is a truth-value condition guarding
the rejection of entirely missing training columns. Both values are false in
Python, so that condition is skipped in either call; all preceding checks and
subsequent computations receive the same input. This structural argument is
conditional on the recorded `numeric_features` implementation, and does not
claim equivalence if callers replace that helper dynamically.

The individual mutant source digest is
`bbd2e146be1d55382a12137cdfacefa85223d535c8b9eeaf816d17e6acd49737`;
the helper source digest is
`9efc8a6a410b92d81f4ee09f9d001f8adad62a779250b3b552db9878f9de28ff`.
The generated mutant module SHA-256 is
`918834bc4092988d72ec899006c4dd2c7e77cd1f4ecb9a4853aab82bc556f4a2`;
a compressed copy is in `evidence/rules-generated-2026-11-15.py.gz`.

A direct comparison against each generated mutant examined ordinary values,
an all-NaN prediction row, infinity, a missing column, nonnumeric values and
an empty frame. Each resulting DataFrame or exception type and message matched
its original. This searches boundaries but is not an exhaustive input search;
the false-valued branch condition supplies the broader source-level argument.
The probe ran on macOS arm64, Python 3.11.17, numpy 2.4.6, pandas 3.1.1 and
mutmut 3.8.0. No separate dependency environment was exercised. The command
and its output are preserved in `evidence/rules-training-probe-2026-11-15.py`
and `.txt`:

```sh
PYTHONPATH=mutants/src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/rules-training-probe-2026-11-15.py
```

Recreate the generated module from the retained compressed copy or the native
engine and verify its SHA-256 before comparison. The historical unit result is
112/119 (94.12%) at L4, threshold 98%. Hypothetically excluding both proposed
mutants would yield 112/117 (95.73%), still below threshold. That arithmetic
uses the historical measurement, is not a fresh unit result and does not change
the authorized score. Confidence in the source-level equivalence is high for
the recorded implementation; owner review and a current complete measurement
remain necessary. The other five historical `rules.py` survivors and all other
unresolved cases require separate investigation.

The same mechanism also applies to the separately tracked
`etl_benchmark.quality.ml.xǁPyODDetectorǁ_matrix__mutmut_11`. Its source digest
is `4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`;
the generated module digest is
`7fb6810432676164f022092e34f924a43b6405ab06f263e11a9e3e3143974fbe`,
retained as `evidence/ml-generated-2026-11-15.py.gz`. The same probe fits an
ECOD detector and compares the original and mutant preparation for the six
cases, including successful arrays and matching failures. It uses the same
helper source digest, and records scikit-learn and pyod versions in its output.
This is another unapproved proposal. The historical `quality/ml.py` raw result
was 239/259 (92.28%) at L4. Excluding this proposal alone hypothetically gives
239/258 (92.64%), still below 98%; it is not a fresh measurement or an owner
verdict. The earlier owner packet's separate proposal is not counted in that
calculation. The remaining survivors require separate investigation.

A further proposed equivalent is
`etl_benchmark.quality.ml.xǁTailProbabilityModelǁdecision_function__mutmut_26`,
which omits `side="left"` from `numpy.searchsorted`. Both the
[NumPy 1.24 documentation](https://numpy.org/doc/1.24/reference/generated/numpy.searchsorted.html)
and the [2.4 documentation](https://numpy.org/doc/2.4/reference/generated/numpy.searchsorted.html)
specify `left` as the default; the former is the lower bound in the project's
environment specification and the latter is the tested version. The same
`ml.py` and generated-module digests above apply. Direct original/mutant calls
matched for tied values and out-of-range values, an empty batch and nonfinite
values. The documented default is the principal argument; the three examples
are boundary probes, not a proof of every supported environment. The probe
used numpy 2.4.6; no other numpy runtime was exercised. Replacing the library
function dynamically is outside this conclusion. This is unapproved, and no
previous owner verdict is changed. Considering this and the newly proposed
training-flag mutant together, the historical unit's hypothetical score is
239/257 (93.00%); it remains below L4's 98% and is not an official result.
