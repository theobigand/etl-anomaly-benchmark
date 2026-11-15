# Chronological pool timestamp column case probes

Three historical survivors alter only the keys supplied to `pd.to_datetime`
when assembling synthetic month timestamps for dataset 468:

- `research.pool_chrono.x_read_times__mutmut_18`: `year` becomes `YEAR`.
- `research.pool_chrono.x_read_times__mutmut_21`: `month` becomes `MONTH`.
- `research.pool_chrono.x_read_times__mutmut_25`: `day` becomes `DAY`.

The source SHA-256 is
`cd8b6eff471b942804223040ca94f119f2ab710479c341dfd3d2668342eff035`.
The contract is to return UTC timestamps ordered by month and original row
order. The local pandas implementations normalize these unit keys to lower
case before looking them up, so each replacement selects the same input data.
The executable probe directly loads the three generated mutant functions and
compares outcomes, dtypes and values to the original for repeated and reordered
months, missing/invalid months, empty input, and non-default indexes. All
comparisons matched on macOS arm64 with Python 3.11.17 and pandas 3.0.6 and
3.1.1. The evidence script and raw output are
[evidence/pool-chrono-uppercase-probe-2026-11-15.py](evidence/pool-chrono-uppercase-probe-2026-11-15.py)
and [its output](evidence/pool-chrono-uppercase-probe-2026-11-15.txt).

These are conditional proposed equivalents, not approvals. The declared
`pandas>=2.0` range is broader than the two builds tested, and no Linux replay
or complete fresh campaign has been performed. Unsupported monkeypatches and
future dependency versions are outside these observations. The owner must
assess the current complete evidence under the official policy.

Reproduce from the repository root, with the generated mutant inventory present:

```sh
PYTHONPATH=. ~/miniconda3/envs/etl-benchmark/bin/python docs/thesis-remediation/evidence/pool-chrono-uppercase-probe-2026-11-15.py
PYTHONPATH=. ~/.cache/etl-mutation-venv/bin/python docs/thesis-remediation/evidence/pool-chrono-uppercase-probe-2026-11-15.py
```
