# Pool preprocessing lower-bound compatibility probes

Three historical survivors in `research/pool_preprocessing.py` (source
SHA-256 `edf8ac28b2824c76840c8e4cad47fe3fee1f1ac84a5b38ad341e968dee9e8dc0`)
previously lacked evidence for the declared lower dependency range:

- `research.pool_preprocessing.x__categorical__mutmut_2` passes `dtype=None`
  instead of `dtype=object` to a string-array conversion.
- `research.pool_preprocessing.x__categorical__mutmut_4` omits that dtype.
- `research.pool_preprocessing.x_prepare_frozen__mutmut_93` runs `nanmedian`
  even when there are no numeric columns rather than constructing an empty
  median array.

The [earlier probe](POOL_NUMERIC_EQUIVALENCE_PROBE_2026-11-15.md) recorded
matching generated-function results in the two newer local environments but
left these cases inconclusive. An isolated `uv run --no-project` environment
was created with the declared lower bounds NumPy 1.24.4, pandas 2.0.3, SciPy
1.11.4 and scikit-learn 1.3.2; no project dependency or lock file changed.
The same generated-function probe passed there for numeric, categorical-only,
duplicate and invalid-partition cases, including matching warnings. A separate
probe using pandas Python and PyArrow 14.0.2 string storage compared missing,
Unicode, empty and mixed values. Both categorical mutants matched values and
object dtype under both storage backends.

Commands and raw output are preserved as `pool-minimum-probe.log.gz` and
`pool-string-storage-output.txt` in `evidence/continuation-2026-11-15/`; the
latter's executable source is `pool-string-storage.py.txt`. The generated
source SHA-256 was
`cbeabfdae48053ea69948b38802c4bf0f3dd9175a4289cd23e0b53806b641cc5`,
and is retained in the prior pool evidence. Reproduce the main probe with:

```sh
PYTHONPATH=mutants/research:src uv run --no-project --python ~/miniconda3/envs/etl-benchmark/bin/python --with 'numpy==1.24.4' --with 'pandas==2.0.3' --with 'scipy==1.11.4' --with 'scikit-learn==1.3.2' --with 'mutmut==3.8.0' python -P docs/thesis-remediation/evidence/pool-numeric-probe-2026-11-15.py
```

These are conditional owner proposals, not approvals. Confidence is medium
across the tested builds and storage backends; other supported releases,
third-party string dtypes, Linux and a full current unit measurement remain
untested. No hypothetical score is authorized by this analysis.
