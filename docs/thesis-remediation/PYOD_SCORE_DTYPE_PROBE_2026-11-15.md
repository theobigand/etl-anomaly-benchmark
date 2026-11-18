# PyOD adapter score dtype probes

`etl_benchmark.quality.ml.xǁPyODDetectorǁscore__mutmut_6` and `_9` replace
or omit `dtype=float` when constructing the returned score series. Source
SHA-256: `4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`.
The public score contract is an index-aligned continuous anomaly score.

The direct generated-method probe fitted each of the eight currently exposed
classical adapters (ECOD, COPOD, HBOS, Isolation Forest, LOF, One-Class SVM,
KNN and PCA) and compared original and mutant score series for float32 and
float64 inputs containing missing values, anomalies and duplicate index
labels. Values, dtype, index and captured warnings matched in all tested
cases. The script and raw output are `pyod-score-dtype.py.txt` and
`pyod-score-dtype-output.txt` under `evidence/continuation-2026-11-15/`;
generated source is preserved as
`evidence/pending-probes-2026-11-15/ml-generated.py.gz`.

The tests used Python 3.11.17, NumPy 2.4.6, scikit-learn 1.9.1, pyod 3.6.7 and
pandas 3.0.6/3.1.1 on macOS arm64. These are conditional owner proposals, not
approvals. Confidence is medium for the current adapters and tested builds;
custom subclasses, other versions, Linux and estimators returning non-float64
scores are not exhausted. The distinct fit/input-matrix dtype mutants have
actual anomaly-decision counterexamples and are not included here.

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/pyod-score-dtype.py.txt
```
