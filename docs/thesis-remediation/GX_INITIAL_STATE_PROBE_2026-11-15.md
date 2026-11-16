# Great Expectations detector initial-state probes

`etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ__init____mutmut_5` and
`_6` replace the private initial empty null-column list or bounds dictionary
with `None`. Source SHA-256:
`11be59dbe975d05547395263b763d37716cd9f916b284ce4147cfd87c61e3416`.
The public detector must reject score/predict before it has expectations and
then report actual expectation failures after fit. The unchanged zero
expectation count rejects pre-fit use; fit assigns both mutated fields before
setting a positive expectation count.

Direct generated-constructor probes covered score/predict before fit, normal
fit and validation, a no-expectation dataset, invalid quantiles and a missing
requested column. Public outputs, exception types/messages and captured
warnings matched both mutants on macOS arm64, Python 3.11.17, NumPy 2.4.6,
pandas 3.0.6/3.1.1 and Great Expectations 1.24.0/1.24.1, respectively. The
script and raw output are `gx-init.py.txt` and `gx-init-output.txt` in
`evidence/continuation-2026-11-15/`. The generated source SHA-256 is
`03c4ec9748e7d655d0c142f303a962c2a157be91455e528b1988ef9e9be166a6`,
preserved as `evidence/gx-generated-2026-11-15.py.gz`.

These are conditional owner proposals, not approvals. Confidence is medium for
the tested lifecycle and GX builds; other supported versions, failures in
unexercised fit paths, Linux and direct private-field manipulation were not
exhausted. No complete unit score is implied.

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/gx-init.py.txt
```
