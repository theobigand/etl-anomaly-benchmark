# AE1SVM label forwarding counterexample

`etl_benchmark.quality._torch_models.xǁPaddedAE1SVMǁfit__mutmut_11` and `_13`
replace supplied `y` with `None` or omit it. Source SHA-256:
`77a1b57ff69e580cad700bb4ee41f069e3ac0c8489bdd714651c753c4bbdd09d`.
The project's `AE1SVMDetector` wrapper normally invokes fit without labels, but
the underlying `PaddedAE1SVM.fit(X, y=None)` exposes a label argument and
forwards it to PyOD.

A direct real-model probe fitted on three supplied label classes in torch
2.14.1 and 2.15.0 with pyod 3.6.7 on macOS arm64. The original emitted PyOD's
warning about labels in unsupervised learning and returned a 3-column
`predict_proba` result; both mutants emitted no warning and returned 2 columns.
This is an observable API difference. PyOD's own fit documentation describes
`y` as ignored and its warning says labels are not expected, so the available
evidence does not establish whether this behavior is a supported project
contract. Both cases remain **inconclusive**, not equivalent and not killed.
Do not encode the observed implementation behavior as a test solely to kill a
mutant without resolving that contract.

Probe and raw output are `ae1svm-labels.py.txt` and `ae1svm-labels-output.txt`
in `evidence/continuation-2026-11-15/`. Generated source is preserved as
`evidence/pending-probes-2026-11-15/torch-models-generated.py.gz`.

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/ae1svm-labels.py.txt
```
