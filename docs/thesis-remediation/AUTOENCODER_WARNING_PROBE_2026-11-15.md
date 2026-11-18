# Autoencoder warning-filter investigation

`etl_benchmark.quality.autoencoder.xǁReconstructionModelǁfit__mutmut_14`
changes a filter that suppresses only `ConvergenceWarning` into one that
suppresses every warning while the underlying MLP is fitted. A direct probe of
`ReconstructionModel` with large finite arrays found that the original emitted
numerical `RuntimeWarning`s while the mutant emitted none. At scale `1e100`
both calls returned; at `1e200` both raised `ValueError`. The same distinction
was observed in both local environments with Python 3.11.17, NumPy 2.4.6,
scikit-learn 1.9.1 and mutmut 3.8.0 on macOS arm64.

This is a real difference for those direct model inputs, but the supported
`AutoencoderDetector` normally standardizes features before fitting the model.
The probe does not establish that such inputs or warnings arise through that
public path. The record therefore remains inconclusive pending a supported-path
counterexample or a defined warning contract; no numerical-warning test was
added solely to kill the mutant. The finding does not alter any archived
scientific conclusion.

Source SHA-256 is
`52ac93bd1898db05567278d773295458fc81847366de74b0c63770c662cbaa4d`;
the generated-source SHA-256 is
`11f65351243ac1f4b5922150523207a780f540ea15ca457395c3c9879a386025`,
retained in `evidence/autoencoder-generated-2026-11-15.py.gz`. The executable
probe and both `-conda.txt` and `-mutation.txt` outputs are in `evidence/`:

```sh
PYTHONPATH=mutants/src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/autoencoder-warning-probe-2026-11-15.py
PYTHONPATH=mutants/src ~/miniconda3/envs/etl-benchmark/bin/python \
  docs/thesis-remediation/evidence/autoencoder-warning-probe-2026-11-15.py
```
