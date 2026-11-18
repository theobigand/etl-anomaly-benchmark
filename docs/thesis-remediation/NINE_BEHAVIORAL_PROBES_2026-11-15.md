# Nine behavioral mutation regressions

These focused results were obtained on the local case-insensitive macOS arm64
filesystem with Python 3.11.17, pandas 3.1.1, NumPy 2.4.6 and mutmut 3.8.0.
The tests were uncommitted on `db27f56` during execution. The following public
behaviors are exercised by the named regressions:

- `research.pool_chrono.x_main__mutmut_93`: selecting only a later dataset must
  run it and write its result; `continue` changed to `break` silently omits it.
  `research/tests/test_pool_chrono_command.py::test_only_a_later_named_dataset_is_run`.
- `research.multi_schema.x_make__mutmut_{306,309,311}`: generated rows need
  distinct index labels so label-based selection identifies one row even when
  the data intentionally contain duplicate records. Omitting or disabling
  index reset produces duplicate labels.
  `research/tests/test_multi_schema.py::test_generated_rows_have_distinct_index_labels`.
- `research.temporal_decision.x_run_frame__mutmut_{11,13}`: equal timestamp
  rows retain arrival order when the chronological partitions are built;
  using the default unstable sort changes their class counts.
  `research/tests/test_temporal_decision_flow.py::test_equal_timestamps_keep_arrival_order_in_the_chronological_split`.
- `research.temporal_decision.x_credit_card__mutmut_{6,8}`: credit-card rows
  with equal timestamps retain their original order, keeping aligned features
  and labels in the sequence supplied to the later split.
  `research/tests/test_temporal_decision_flow.py::test_credit_rows_with_equal_times_keep_arrival_order`.
- `etl_benchmark.quality.window_drift.x__numeric__mutmut_18`: a mixed pair of
  finite nullable integer and floating-point columns can be fit and scored.
  Omitting conversion to float makes NumPy reject the resulting object array.
  `tests/test_window_drift_contracts.py::test_nullable_numeric_columns_can_be_scored`.

Each integrated test failed on its generated mutant for the expected behavior
(RED, exit 1); the four affected test files passed on the original (GREEN, exit
0). The native mutmut invocation then exited 0 and recorded all nine killed
(exit code 1). The [focused run record](evidence/nine-focused-native-2026-11-15.json)
contains the exact command, individual identities, source and test-tree hashes,
dependency context, generated sources, native metadata and log. Compressed
integrated RED logs are in `evidence/pending-probes-2026-11-15/`. These are not
complete unit measurements and must not be added to the historical campaign.
The test digest excludes non-Python and external inputs.
