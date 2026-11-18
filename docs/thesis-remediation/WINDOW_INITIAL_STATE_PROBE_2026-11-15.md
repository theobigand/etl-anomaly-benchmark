# Window monitor initial-state probes

`etl_benchmark.quality.window_drift.xǁWindowDriftMonitorǁ__init____mutmut_22`
and `_23` replace the initial private mean or scale `None` with an empty string
in `src/etl_benchmark/quality/window_drift.py`, SHA-256
`7369796bac2ada0ee25c125b383752c8d40d7f683e287767dfb6b373108ea8d7`.
The public monitor must reject evaluation before fitting and then score future
windows against fitted reference statistics. The other initially unset guard
fields still reject pre-fit evaluation; successful fitting replaces both fields.

Direct generated-constructor probes compared evaluation before fit, successful
fit and scoring, empty, singleton, missing timestamp, nonnumeric, all-missing
and nonfinite reference data, and failed refitting. Outcomes, results and
captured warnings matched for both mutants on macOS arm64, Python 3.11.17,
NumPy 2.4.6 and pandas 3.0.6/3.1.1. The executable probe and raw output are
`window-init.py.txt` and `window-init-output.txt` in
`evidence/continuation-2026-11-15/`; generated source is archived with the
nine-focused evidence.

These are conditional owner proposals, not approvals. Confidence is medium for
the tested lifecycle. Other extension dtypes, dependency versions, Linux and
internal failures between fitted-state assignments were not exhausted. The
separate mutant changing the public `reference_end` field is not included.
No complete current unit score is implied. Reproduce with:

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/window-init.py.txt
```

Additional lower-bound dependency results are in [the compatibility addendum](MINIMUM_DEPENDENCY_PROBES_2026-11-16.md).
