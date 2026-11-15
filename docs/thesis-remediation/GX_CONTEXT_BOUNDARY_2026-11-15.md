# GX context isolation boundary

`etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_9`
changes `gx.get_context(mode="ephemeral")` to `mode=None`. In a disposable
pre-existing GX file project, the original returns row results without
changing the project configuration. The generated mutant returns the same row
results for the probe but changes `gx/great_expectations.yml` by adding a data
source. This can modify a user's existing GX project merely by predicting.
No real project was modified during the probe or regression.

The regression creates an isolated file project, fits and invokes the public
detector, and checks that the existing project configuration is byte-identical.
It failed on the generated mutant specifically because that configuration
changed (RED, exit 1). The original and affected GX/detector test files passed
(GREEN/regression, exit 0, 42 tests):

```sh
MUTANT_UNDER_TEST='etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_9' \
PYTHONPATH=mutants/src:mutants:. ~/.cache/etl-mutation-venv/bin/python -P \
  -c 'import etl_benchmark.quality.gx, pytest; raise SystemExit(pytest.main(["-c", "/dev/null", "--import-mode=importlib", "-p", "no:cacheprovider", "-q", "tests/test_gx.py::test_gx_prediction_does_not_modify_an_existing_project"]))'
~/.cache/etl-mutation-venv/bin/python -m pytest tests/test_gx.py \
  tests/test_detector_contracts.py tests/test_detector_state_contracts.py --disable-warnings -q
```

An initial RED invocation omitted the repository root from `PYTHONPATH` and
exited 4 during conftest import; it did not test the mutant. The corrected
command above produced the expected failure.

Source SHA-256 is
`11be59dbe975d05547395263b763d37716cd9f916b284ce4147cfd87c61e3416`;
generated-source SHA-256 is
`03c4ec9748e7d655d0c142f303a962c2a157be91455e528b1988ef9e9be166a6`, retained
as `evidence/gx-generated-2026-11-15.py.gz`. The direct probe and output are
`evidence/gx-context-probe-2026-11-15.py` and `.txt`; its environment is
macOS arm64, Python 3.11.17, NumPy 2.4.6, pandas 3.1.1, GX 1.24.1 and mutmut
3.8.0. The focused native run exited 0 and recorded the mutant killed (exit code 1).
The command, context, log and metadata are in
`evidence/gx-context-focused-2026-11-15.json` and associated files. The run
used the case-insensitive local filesystem with tests uncommitted on
`bc67ad5`; it is not a full unit measurement.
