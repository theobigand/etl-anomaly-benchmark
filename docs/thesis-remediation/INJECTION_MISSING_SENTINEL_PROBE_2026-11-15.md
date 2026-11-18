# Injection missing sentinel counterexample

`research.injection.x_inject__mutmut_90`, source SHA-256
`cdfc81d98e3470ccdf5f7930d7e987b1bdad3545e060552f3a3bb1d170d8cb39`,
changes an injected `np.nan` to `None`. Direct generated-function comparisons
of float64 and nullable Float64 carrier frames matched values, dtypes, missing
sentinel types and captured warnings for the tested sizes and seeds. Integer
frames raised the same errors in both versions in the tested pandas builds.

A numeric carrier stored with object dtype is a counterexample: both functions
run, but the returned missing sentinel types differ, and the frame/warning
comparison detects a difference. `prepare` normally produces float64 carrier
columns, while `inject` also accepts a caller-supplied frame. Both sentinels
are missing under pandas, and this probe has not established a supported
consumer that relies on their exact Python identity. The case remains
**inconclusive**; it is neither an equivalence proposal nor a verified kill.
Do not add an assertion solely to encode an unestablished sentinel contract.

The generated-function probe and raw output are `injection-null.py.txt` and
`injection-null-output.txt` under `evidence/continuation-2026-11-15/`. They
cover macOS arm64, Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6/3.1.1. The
actual generated source is archived in
`evidence/injection-generated-2026-11-15.py.gz`. Reproduce with:

```sh
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/injection-null.py.txt
```
