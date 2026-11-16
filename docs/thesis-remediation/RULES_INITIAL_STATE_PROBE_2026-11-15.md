# Rule-detector initial-state probes

Five historical survivors in `src/etl_benchmark/quality/rules.py`, SHA-256
`bbd2e146be1d55382a12137cdfacefa85223d535c8b9eeaf816d17e6acd49737`,
replace a private initially unset fitted field with an empty string:

- `etl_benchmark.quality.rules.xǁZScoreDetectorǁ__init____mutmut_4` and `_5`
  alter `_means` and `_stds`, respectively.
- `etl_benchmark.quality.rules.xǁIQRDetectorǁ__init____mutmut_4`, `_5` and
  `_6` alter `_lower`, `_upper` and `_scale`, respectively.

The public contract rejects prediction and scoring before a successful fit,
then computes flags and scores from learned numeric statistics. Each initial
mutation leaves at least one other guard field unset, so the original pre-fit
error still occurs. A successful fit assigns all required fields. The direct
generated-constructor probe compares score/predict before fit, successful
fitting, empty, singleton, nonnumeric, all-missing and nonfinite input, and a
failed refit. Values, error outcomes and captured warnings matched for all
five mutants in the tested cases.

The script and output are `rules-init.py.txt` and `rules-init-output.txt` under
`evidence/continuation-2026-11-15/`. The generated source SHA-256 is
`918834bc4092988d72ec899006c4dd2c7e77cd1f4ecb9a4853aab82bc556f4a2`,
preserved as `evidence/rules-generated-2026-11-15.py.gz`. Checks used macOS
arm64, Python 3.11.17, NumPy 2.4.6, scikit-learn 1.9.1 and pandas 3.0.6/3.1.1.

These are conditional owner proposals, not approvals. Confidence is medium for
tested lifecycle paths. The probe does not exhaust every supported numeric
extension dtype, dependency build or Linux, and does not force an internal
failure between fitted-field assignments. No complete current unit score is
implied. Reproduce with the generated inventory present:

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/rules-init.py.txt
```

Additional lower-bound dependency results are in [the compatibility addendum](MINIMUM_DEPENDENCY_PROBES_2026-11-16.md).
