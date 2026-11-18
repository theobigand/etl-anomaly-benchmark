# Temporal drift threshold and signed-direction probes

`etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ_row_score__mutmut_15`
changes the moved-feature threshold from strict `> 0.03` to `>= 0.03`.
With a reference sample `[-1, 0, 1]`, the sample standard deviation is one;
32 recent observations at 0.03 have mean standardized shift exactly 0.03 in
both local environments. The original scores them zero, while the mutant
scores 0.0009. The public-score regression failed on the mutant (RED, exit 1) and passed
on the original with both affected drift test files (GREEN/regression, exit 0;
32 tests). The focused native run exited 0 and recorded the mutant killed (exit code 1).
The command, context, log and metadata are in
`evidence/drift-threshold-focused-2026-11-15.json` and associated files. The
run used the case-insensitive local filesystem with tests uncommitted on
`bc67ad5`. It is not a fresh unit score.

`etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ_row_score__mutmut_33`
is separately proposed equivalent, not approved. It divides the standardized
scores by `direction` where the original multiplies. The direction is the
sign of a selected shift whose absolute value is strictly greater than 0.03;
thus for ordinary floating data it is +1 or -1, and multiplication and
division have the same magnitude and sign. The probe compared positive,
negative, unmoved, gross-outlier, short-window and missing-value cases exactly.
This does not cover every custom pandas extension dtype or future numerical
backend, and no owner or independent reviewer has approved the inference.

Both probes ran with Python 3.11.17, NumPy 2.4.6, mutmut 3.8.0 and pandas
3.0.6 or 3.1.1 on macOS arm64. Source SHA-256 is
`95380ca0f8f87a24c512ac7055357225472342065e0da676c0be46dd115fa09b`;
the generated source SHA-256 is
`921baec94e62bead4611ce5e9ce62f2a9e9c42d28adfe985788acc985f1017d7`,
retained in `evidence/drift-generated-2026-11-15.py.gz`. The executable
probe and `-conda.txt` and `-mutation.txt` outputs are in `evidence/`:

```sh
PYTHONPATH=mutants/src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/drift-boundary-probe-2026-11-15.py
PYTHONPATH=mutants/src ~/miniconda3/envs/etl-benchmark/bin/python \
  docs/thesis-remediation/evidence/drift-boundary-probe-2026-11-15.py
```

The historical raw L4 unit was 119/129 (92.25%). Hypothetically excluding
only the signed-direction proposal yields 119/128 (92.97%), still below 98%;
that is neither a current measurement nor an authorized adjusted score.

RED and GREEN commands:

```sh
MUTANT_UNDER_TEST='etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ_row_score__mutmut_15' \
PYTHONPATH=mutants/src:mutants:. ~/.cache/etl-mutation-venv/bin/python -P \
  -c 'import etl_benchmark.quality.drift, pytest; raise SystemExit(pytest.main(["-c", "/dev/null", "--import-mode=importlib", "-p", "no:cacheprovider", "-q", "tests/test_drift_contracts.py::test_a_shift_at_the_movement_threshold_is_not_scored"]))'
~/.cache/etl-mutation-venv/bin/python -m pytest tests/test_drift.py tests/test_drift_contracts.py --disable-warnings -q
```
