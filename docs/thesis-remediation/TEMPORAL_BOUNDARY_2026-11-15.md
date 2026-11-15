# Temporal prevalence boundary

For `research.temporal_decision.x_match_prevalence__mutmut_11`, source SHA-256
`f402ba92cdbd8a143608f9ce9d1ab98f68cad5b6c881318f504ab8c0380742d8`,
changing `>` to `>=` makes the all-positive case at target prevalence 1.0
raise `ZeroDivisionError`. The original returns every input index. A positive
share of 1.0 is a valid prevalence boundary, so the regression checks the
returned rows rather than internal sampling choices.

RED on the generated mutant (exit 1, expected `ZeroDivisionError`):

```sh
MUTANT_UNDER_TEST='research.temporal_decision.x_match_prevalence__mutmut_11' \
PYTHONPATH=mutants:mutants/research:src \
~/.cache/etl-mutation-venv/bin/python -P -c 'import sys, research.temporal_decision as m, pytest; sys.modules["temporal_decision"]=m; raise SystemExit(pytest.main(["-c", "/dev/null", "--import-mode=importlib", "-p", "no:cacheprovider", "-q", "research/tests/test_temporal_decision_flow.py::test_matching_a_fully_positive_population_keeps_every_row"]))'
```

GREEN and regression: `~/.cache/etl-mutation-venv/bin/python -m pytest
research/tests/test_temporal_decision_flow.py
research/tests/test_temporal_decision_contracts.py --disable-warnings -q`
exited 0 with 43 passed. The direct comparisons ran on macOS arm64, Python
3.11.17, pandas 3.1.1 and numpy 2.4.6. This is not a full unit measurement,
and the historical ledger is not altered. No benchmark implementation or
scientific archive changed. The native one-mutant run exited 0 and its metadata records this mutant as
killed (exit code 1). Its command, context, metadata and native log are
retained in `evidence/temporal-boundary-focused-2026-11-15.json` and the
associated files. The run used the case-insensitive local filesystem and
started with the regression uncommitted on `ced2975`; it is not a complete
unit remeasurement.
