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

## Credit-card feature index boundary

`research.temporal_decision.x_credit_card__mutmut_12` and `_17` replace
`reset_index(drop=True)` with None or False. On the existing representative
credit-card loader fixture, each mutant inserts the original sorted row index
as an extra numerical feature; the original returns only the selected feature
columns. This changes model inputs and could introduce a spurious time/order
signal. The existing public loader regression now asserts the complete
feature-column list. It failed on each mutant (RED, exit 1) and both affected
temporal-decision test files passed on the original (GREEN/regression, exit 0;
43 tests). The test uses stand-ins for data loading and feature selection but
executes the actual loader alignment and index reset.

RED uses the preload command in the earlier section with mutant identity
`research.temporal_decision.x_credit_card__mutmut_12` or `_17` and node
`research/tests/test_temporal_decision_flow.py::test_the_credit_card_rows_follow_time_and_carry_the_label_and_utc_time`.
The original source digest and local environment match the earlier section.
The focused native run exited 0 and recorded both mutants killed (exit code
1). The command, context, log and metadata are in
`evidence/credit-index-focused-2026-11-15.json` and associated files. The
run used a case-insensitive local filesystem with the assertion uncommitted
on `e33308a`; it is not a full unit measurement.

## Mixed timezone offsets

`research.temporal_decision.x_run_frame__mutmut_15`, `_17` and `_18` change
or omit `utc=True` while parsing timestamps. The regression represents the
same instants as UTC and alternating UTC/Europe-Paris offset strings and
checks that chronological partitions and PR-AUC match. The original accepts
and normalizes both; in pandas 3.1.1 each generated mutant raises a mixed
timezones `ValueError`. Both temporal-decision test files passed on the
original (GREEN/regression, exit 0; 44 tests); each mutant failed for the
expected timezone error (RED, exit 1). The bootstrap interval is stubbed to
bound the test; chronological parsing and detector scoring run normally.

RED uses the preload command above with mutant identity
`research.temporal_decision.x_run_frame__mutmut_15`, `_17`, or `_18` and node
`research/tests/test_temporal_decision_flow.py::test_chronological_evaluation_accepts_equivalent_mixed_timezone_offsets`.
The source digest and local mutation environment match the earlier sections.
The `_15` RED check also failed with the same timezone error under the
canonical pandas 3.0.6 environment; the other two were not separately run
there. The focused native run exited 0 and recorded all three killed (exit code 1).
The command, context, log and metadata are in
`evidence/mixed-time-focused-2026-11-15.json` and associated files. It used
the case-insensitive local filesystem with the test uncommitted on `11b7994`;
these are not full unit results or additions to the historical campaign.
