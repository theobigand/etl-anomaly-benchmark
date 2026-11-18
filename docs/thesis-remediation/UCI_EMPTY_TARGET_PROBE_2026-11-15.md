# Empty UCI target schema

`research.uci_loader.x_split_columns__mutmut_34` and `_36` replace or omit the
`np.nan` data used to create a missing target. Source SHA-256:
`a1176cd61bd8454c9fa51da682194444feb24529dc401916e8bb94fd212ab691`.
The existing loader contract specifies an all-missing numeric target when there
is no unique target column. For an empty table, the original still returns a
float64 target aligned to the input index; both mutants instead return object
dtype. Schema consistency is relevant to callers that process empty partitions.

The regression
`research/tests/test_uci_loader.py::test_an_empty_table_without_a_target_keeps_the_numeric_target_schema`
failed on each generated mutant (RED, exit 1) and the original UCI loader test
file passed (GREEN, 13 passed). The focused native mutation run exited 0 and
recorded both mutants killed (exit code 1). Exact command, source and test-tree
digests, native metadata and log are in
`evidence/continuation-2026-11-15/empty-target-native.json` and associated
files. The run used a case-insensitive macOS filesystem and an uncommitted
test on `d4d2189`. It is not a complete unit measurement and must not be added
to the historical campaign. Earlier failed probe invocations are retained
separately and are not counted as RED evidence.
