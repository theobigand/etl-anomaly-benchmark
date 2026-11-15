# Classical model default and NaN probes

Three historical survivors in `src/etl_benchmark/quality/ml.py` (SHA-256
`4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`):

- `etl_benchmark.quality.ml.xǁTailProbabilityModelǁfit__mutmut_13` omits
  `axis=0` from `scipy.stats.skew`. The documented default in
  [SciPy 1.11.4](https://docs.scipy.org/doc/scipy-1.11.4/reference/generated/scipy.stats.skew.html)
  and the installed SciPy 1.17.1 is 0. The generated-method probe compared fit
  state and scores for skewed, constant, missing, and singleton input; the
  results and error outcomes matched.
- `etl_benchmark.quality.ml.xǁTailProbabilityModelǁ__init____mutmut_13` and
  `etl_benchmark.quality.ml.xǁPCAReconstructionǁ__init____mutmut_12` change
  `float("nan")` to `float("NAN")`. Both original and generated constructors
  produced NaNs with identical stored bytes in the tested Python build.

The direct generated-class method checks and independent default probes used
Python 3.11.17, NumPy 2.4.6 and SciPy 1.17.1 in both local environments on
macOS arm64. Their scripts and raw output are `ml-defaults.py.txt`,
`ml-defaults-output.txt`, `ml-defaults-mutants.py.txt` and
`ml-defaults-mutants-output.txt` under `evidence/pending-probes-2026-11-15/`;
the generated source is retained there as `ml-generated.py.gz`.

These are conditional owner proposals, not approvals. They do not test every
supported SciPy/Python build or Linux, do not compare warnings as an API, and
do not establish a current full-unit score. The synthetic PCA numerical
instability is a separate finding; these checks do not change its interpretation
or archived results. Run the direct probe with the generated inventory present:

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/pending-probes-2026-11-15/ml-defaults-mutants.py.txt
```

Evidence confidence: medium for the tested environments and documented SciPy
1.11.4 default; supported-version and platform coverage is incomplete. The owner
decision remains separate.
