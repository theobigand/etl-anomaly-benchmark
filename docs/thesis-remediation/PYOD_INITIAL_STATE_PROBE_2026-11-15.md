# PyOD adapter initial-state probes

`etl_benchmark.quality.ml.xǁPyODDetectorǁ__init____mutmut_5` and `_6` replace
the initial private imputer or scaler `None` with an empty string in
`src/etl_benchmark/quality/ml.py`, SHA-256
`4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`.
The detector contract is to reject scoring before fitting and to fit, score and
predict on valid numeric data. Initially `_model` is still `None`, so the
public scoring path rejects use before the mutated private field is consumed.
A successful fit replaces both fields before installing the fitted model.

The direct generated-constructor probe exercises score/predict before fit, a
successful ECOD fit, empty, nonnumeric and all-missing training frames, and a
failed refit. Original and each mutant produced the same public outcomes,
values, exception types/messages and captured warnings in the tested cases.
The script and output are `pyod-init.py.txt` and `pyod-init-output.txt` under
`evidence/continuation-2026-11-15/`. The generated source is archived as
`evidence/pending-probes-2026-11-15/ml-generated.py.gz`.

The probe used Python 3.11.17, NumPy 2.4.6, scikit-learn 1.9.1 and pandas
3.0.6/3.1.1 on macOS arm64. These are conditional owner proposals, not approvals.
Confidence is medium for the tested lifecycle; other estimators, dependency
builds, Linux and unsupported direct mutation of private fields were not
exhaustively tested. The separate public `feature_names_` initial-state mutant
is not included. Reproduce with the generated inventory present:

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/pyod-init.py.txt
```
