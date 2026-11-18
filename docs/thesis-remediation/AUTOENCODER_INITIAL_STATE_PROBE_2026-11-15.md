# Autoencoder initial-state counterexamples

`etl_benchmark.quality.autoencoder.xǁReconstructionModelǁ__init____mutmut_4`
and `_5` initialize `threshold_` or `network_` to an empty string instead of
`None`. Source SHA-256:
`52ac93bd1898db05567278d773295458fc81847366de74b0c63770c662cbaa4d`.
The direct generated-constructor probe compared scoring and predicting before
fit, valid fit, empty input, and prediction after a fit failed because of an
invalid contamination value. Tests used Python 3.11.17, NumPy 2.4.6 and
scikit-learn 1.9.1 on macOS arm64 in both local environments.

Both mutants have observable differences on error paths. For `_5`, the direct
model's pre-fit score/predict raises `AttributeError` in both cases but the
message identifies `NoneType` versus `str`. For `_4`, after an invalid
contamination causes fitting to fail, a subsequent prediction raises a
`TypeError` on the original and NumPy `UFuncTypeError` on the mutant. The
higher-level adapter normally guards fitting and valid contamination; the
available evidence does not establish that these error details are a supported
public behavior. Both records remain **inconclusive**, not proposals or kills.
The warning-filter mutant remains a separate investigation.

The executable probe and raw output are `autoencoder-init.py.txt` and
`autoencoder-init-output.txt` under
`evidence/continuation-2026-11-15/`. Reproduce with the generated inventory:

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/autoencoder-init.py.txt
```
