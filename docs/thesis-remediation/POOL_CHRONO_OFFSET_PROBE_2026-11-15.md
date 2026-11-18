# Chronological eligibility with mixed UTC offsets

`research.pool_chrono.x_eligible__mutmut_7`, `_9` and `_10` respectively
replace `utc=True` with `None`, omit it, or set it to `False`. Source SHA-256:
`cd8b6eff471b942804223040ca94f119f2ab710479c341dfd3d2668342eff035`.
`run_dataset` accepts a timestamp series and determines whether the newest
partition has enough anomalies. Equivalent UTC instants represented using
different offsets must not be rejected when establishing that order.

The regression
`research/tests/test_pool_chrono.py::test_chronological_eligibility_normalizes_mixed_timezone_offsets`
compares eligibility for mixed-offset strings with the same instants normalized
to UTC. Each generated mutant failed with a mixed-timezone `ValueError` (RED,
exit 1); the original passed all nine pool-chronological tests (GREEN, exit 0).
A direct generated-function probe also showed the same difference with pandas
3.0.6 and 3.1.1 on macOS arm64, Python 3.11.17; see
[evidence/pool-chrono-eligible-probe-2026-11-15.py](evidence/pool-chrono-eligible-probe-2026-11-15.py)
and [output](evidence/pool-chrono-eligible-probe-2026-11-15.txt).

The focused native mutation engine run exited 0 and recorded each mutant killed
(exit code 1). Its exact command, context, source and artifact hashes, metadata,
generated source and log are recorded in
[evidence/pool-chrono-offset-focused-2026-11-15.json](evidence/pool-chrono-offset-focused-2026-11-15.json).
The run used a case-insensitive local filesystem, with tests uncommitted on
`11b7994`; it is not a full unit measurement or a fresh campaign. The execution
context does not bind every non-Python or external input.

Reproduce a RED check by setting the individual mutant identity, preloading the
generated package, and running the regression:

```sh
MUTANT_UNDER_TEST='research.pool_chrono.x_eligible__mutmut_7' \
PYTHONPATH=mutants:mutants/research:src \
~/.cache/etl-mutation-venv/bin/python -P -c 'import sys, research.pool_chrono as m, pytest; sys.modules["pool_chrono"]=m; raise SystemExit(pytest.main(["-c", "/dev/null", "--import-mode=importlib", "-p", "no:cacheprovider", "-q", "research/tests/test_pool_chrono.py::test_chronological_eligibility_normalizes_mixed_timezone_offsets"]))'
```
