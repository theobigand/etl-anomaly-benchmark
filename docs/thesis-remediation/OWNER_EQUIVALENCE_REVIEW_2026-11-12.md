# Owner equivalence review packet, focused mutation survivors (2026-11-12)

Status: **technical assessments only. No owner decision exists in this document or in the machine-readable index.** Every candidate is stored with `verdict: proposed`, an empty approver and an empty decision date. Nothing here changes `verification/mutation_equivalence.json`, the accepted denominator, or any score.

## Executive overview

The focused mutation runs of 2026-11-12 (mutmut 3.8.0, `make mutation-focus`, repository revision `1d518af` plus the test additions listed below) left 43 surviving mutants in 13 L4 modules that I assessed individually. The technical assessment is: 26 with strong equivalence evidence, 17 requiring additional verification, 0 with a meaningful behavioral difference, 0 with insufficient evidence. These categories are my reading of the evidence; they are not verdicts, and a mutant that no current test can separate is not thereby equivalent.

Before building this packet I added behavioral tests for the survivors that I could separate on the supported contract. That work removed mutants from the list rather than moving them into it: boundary comparison of a window ending exactly at the change time, naive timestamps, integer typing of time blocks, the configured split ratios, a deprecated pandas unit alias, default method sets, flushed progress lines, wrong-length Holm adjustments, and missing-score refusals. What remains is the set I could not separate that way; two families (`label_cast`, `asarray_float_detector`) may still gain a test, see the outstanding-work table.

Raw focused scores, before any exclusion: 13 of the 16 measured modules are at or above 98 and 3 are below (`research/normalise.py`, `src/etl_benchmark/load.py`, `src/etl_benchmark/quality/base.py`). A focused run is development feedback on one module; it is not a campaign result and certifies nothing.

Owner review is required because an exclusion changes the denominator of a release-gate score, and a decision binds the exact source digest, catalog digest, policy version and dependency versions of the record. Score arithmetic below is shown so the effect is visible; it is not a reason to approve.

Precedent already on record (owner decisions of 2026-11-11, `docs/thesis-remediation/EQUIVALENCE_REVIEW_PACKET_LSTM_2026-11-08.md`): four LSTM mutants accepted and five left **inconclusive**, among them `astype(None)` and `replace=None`. Several candidates below have the same shape as the inconclusive ones (None passed where a boolean or dtype is documented). I flag the resemblance; I do not infer a decision from it.

## Candidate inventory

| Module | Mutant (suffix) | Function | Category | Family | Individual decision needed |
| --- | --- | --- | --- | --- | --- |
| `research/temporal_pilot.py` | `x_block_bootstrap_ci__mutmut_38` | `block_bootstrap_ci` | Strong equivalence evidence | choice_default | yes |
| `research/temporal_pilot.py` | `x_main__mutmut_18` | `main` | Strong equivalence evidence | argparse_default_none | yes |
| `research/temporal_pilot.py` | `x_monitor_control__mutmut_101` | `monitor_control` | Strong equivalence evidence | aware_utc | yes |
| `research/temporal_pilot.py` | `x_monitor_control__mutmut_104` | `monitor_control` | Strong equivalence evidence | aware_utc | yes |
| `research/temporal_pilot.py` | `x_monitor_control__mutmut_56` | `monitor_control` | Strong equivalence evidence | aware_utc | yes |
| `research/temporal_pilot.py` | `x_monitor_control__mutmut_58` | `monitor_control` | Strong equivalence evidence | aware_utc | yes |
| `research/temporal_pilot.py` | `x_monitor_control__mutmut_61` | `monitor_control` | Strong equivalence evidence | aware_utc | yes |
| `research/temporal_pilot.py` | `x_monitor_control__mutmut_99` | `monitor_control` | Strong equivalence evidence | aware_utc | yes |
| `research/temporal_pilot.py` | `x_to_timestamps__mutmut_11` | `to_timestamps` | Additional verification required | to_numpy_dtype_none | yes |
| `research/typed_run.py` | `x_run_one__mutmut_48` | `run_one` | Additional verification required | groupby_sort_none | yes |
| `research/typed_run.py` | `x_run_one__mutmut_55` | `run_one` | Additional verification required | groupby_sort_none | yes |
| `research/pool_typed.py` | `x_load_carrier__mutmut_29` | `load_carrier` | Additional verification required | label_cast | yes |
| `research/pool_typed.py` | `x_run_reference__mutmut_33` | `run_reference` | Additional verification required | groupby_sort_none | yes |
| `research/pool_typed.py` | `x_run_reference__mutmut_45` | `run_reference` | Additional verification required | groupby_sort_none | yes |
| `research/pool_typed.py` | `x_run_severity__mutmut_28` | `run_severity` | Additional verification required | groupby_sort_none | yes |
| `research/normalise.py` | `x_clean__mutmut_34` | `clean` | Strong equivalence evidence | labels_invisible | yes |
| `research/normalise.py` | `x_clean__mutmut_35` | `clean` | Additional verification required | astype_none | yes |
| `research/normalise.py` | `x_clean__mutmut_45` | `clean` | Strong equivalence evidence | labels_invisible | yes |
| `research/normalise.py` | `x_clean__mutmut_48` | `clean` | Strong equivalence evidence | labels_invisible | yes |
| `research/normalise.py` | `x_clean__mutmut_51` | `clean` | Strong equivalence evidence | labels_invisible | yes |
| `research/normalise.py` | `x_clean__mutmut_64` | `clean` | Additional verification required | index_none | yes |
| `research/build_pool.py` | `x_main__mutmut_27` | `main` | Strong equivalence evidence | arg_type_path | yes |
| `research/build_pool.py` | `x_main__mutmut_30` | `main` | Strong equivalence evidence | arg_type_path | yes |
| `research/build_pool.py` | `x_pool_row__mutmut_38` | `pool_row` | Strong equivalence evidence | constant_labels | yes |
| `src/etl_benchmark/load.py` | `x_write_csv__mutmut_11` | `write_csv` | Additional verification required | index_none | yes |
| `src/etl_benchmark/quality/base.py` | `xǁDetectorǁscore__mutmut_1` | `score` | Additional verification required | astype_none | yes |
| `research/pool_check.py` | `x_main__mutmut_27` | `main` | Strong equivalence evidence | arg_type_path | yes |
| `research/pool_check.py` | `x_main__mutmut_30` | `main` | Strong equivalence evidence | arg_type_path | yes |
| `research/matched_alert.py` | `x_analyse__mutmut_20` | `analyse` | Strong equivalence evidence | or_true_empty_holm | yes |
| `research/matched_alert.py` | `x_compare__mutmut_43` | `compare` | Strong equivalence evidence | problems_count_only | yes |
| `research/prevalence_shift.py` | `x_contrasts__mutmut_59` | `contrasts` | Strong equivalence evidence | zip_same_source | yes |
| `research/prevalence_shift.py` | `x_contrasts__mutmut_62` | `contrasts` | Strong equivalence evidence | zip_same_source | yes |
| `research/prevalence_shift.py` | `x_contrasts__mutmut_63` | `contrasts` | Strong equivalence evidence | zip_same_source | yes |
| `research/source_clustered.py` | `x_source_id__mutmut_3` | `source_id` | Strong equivalence evidence | rpartition | yes |
| `research/alert_budget.py` | `x__counts__mutmut_50` | `_counts` | Strong equivalence evidence | f1_guard | yes |
| `research/alert_budget.py` | `x_run_method__mutmut_23` | `run_method` | Additional verification required | asarray_float_detector | yes |
| `research/alert_budget.py` | `x_run_method__mutmut_54` | `run_method` | Additional verification required | asarray_float_detector | yes |
| `research/score_shift.py` | `x_monitor_table__mutmut_39` | `monitor_table` | Strong equivalence evidence | nonneg_compare | yes |
| `research/score_shift.py` | `x_monitor_table__mutmut_48` | `monitor_table` | Strong equivalence evidence | continue_break_empty | yes |
| `research/score_shift.py` | `x_run_method__mutmut_23` | `run_method` | Additional verification required | asarray_float_detector | yes |
| `research/score_shift.py` | `x_run_method__mutmut_25` | `run_method` | Additional verification required | asarray_float_detector | yes |
| `research/score_shift.py` | `x_run_method__mutmut_39` | `run_method` | Additional verification required | asarray_float_detector | yes |
| `research/score_shift.py` | `x_run_method__mutmut_41` | `run_method` | Additional verification required | asarray_float_detector | yes |

Counts by category: Strong equivalence evidence 26; Additional verification required 17; Meaningful behavioral difference 0; Insufficient evidence 0.

## Score implications (exact integer arithmetic, hypothetical)

Policy used: `verification/mutation_policy.py::_summary`: PASS when `killed * 100 >= threshold * adjusted_eligible`, with `adjusted_eligible = eligible - accepted_equivalents`. A timeout and a survivor are both outcomes other than `killed`; a timeout is not an exclusion candidate. Only a surviving mutant with an owner record bound to the current digests can be excluded. L4 threshold: 98.

Every figure in the *Hypothetical* columns is hypothetical: it assumes the owner accepts the named group and is not an achieved result.

| Module | Killed | Total | Survived | Timeouts | Incomplete | Accepted exclusions | Raw score | Hypothetical if strong group accepted | Hypothetical if all candidates accepted | Min. exclusions to reach 98 | Focused raw arithmetic at 98 (not a certification) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `research/alert_budget.py` | 777 | 780 | 3 | 0 | 0 | 0 | 99.62 % | 777/779 = 99.74 % (meets 98) | 777/777 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/build_pool.py` | 169 | 172 | 3 | 0 | 0 | 0 | 98.26 % | 169/169 = 100.00 % (meets 98) | 169/169 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/labelled_benchmark.py` | 475 | 475 | 0 | 0 | 0 | 0 | 100.00 % | 475/475 = 100.00 % (meets 98) | 475/475 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/matched_alert.py` | 320 | 322 | 2 | 0 | 0 | 0 | 99.38 % | 320/320 = 100.00 % (meets 98) | 320/320 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/normalise.py` | 191 | 197 | 6 | 0 | 0 | 0 | 96.95 % | 191/193 = 98.96 % (meets 98) | 191/191 = 100.00 % (meets 98) | 3 | below 98 |
| `research/paired_bootstrap.py` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00 % | 100/100 = 100.00 % (meets 98) | 100/100 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/pool_check.py` | 178 | 180 | 2 | 0 | 0 | 0 | 98.89 % | 178/178 = 100.00 % (meets 98) | 178/178 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/pool_typed.py` | 521 | 525 | 4 | 0 | 0 | 0 | 99.24 % | 521/525 = 99.24 % (meets 98) | 521/521 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/prevalence_shift.py` | 366 | 369 | 3 | 0 | 0 | 0 | 99.19 % | 366/366 = 100.00 % (meets 98) | 366/366 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/score_shift.py` | 800 | 806 | 6 | 0 | 0 | 0 | 99.26 % | 800/804 = 99.50 % (meets 98) | 800/800 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/source_clustered.py` | 336 | 337 | 1 | 0 | 0 | 0 | 99.70 % | 336/336 = 100.00 % (meets 98) | 336/336 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/temporal_pilot.py` | 580 | 589 | 9 | 0 | 0 | 0 | 98.47 % | 580/581 = 99.83 % (meets 98) | 580/580 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/typed_masking.py` | 132 | 132 | 0 | 0 | 0 | 0 | 100.00 % | 132/132 = 100.00 % (meets 98) | 132/132 = 100.00 % (meets 98) | 0 | meets 98 |
| `research/typed_run.py` | 349 | 351 | 2 | 0 | 0 | 0 | 99.43 % | 349/351 = 99.43 % (meets 98) | 349/349 = 100.00 % (meets 98) | 0 | meets 98 |
| `src/etl_benchmark/load.py` | 13 | 14 | 1 | 0 | 0 | 0 | 92.86 % | 13/14 = 92.86 % (below 98) | 13/13 = 100.00 % (meets 98) | 1 | below 98 |
| `src/etl_benchmark/quality/base.py` | 30 | 31 | 1 | 0 | 0 | 0 | 96.77 % | 30/31 = 96.77 % (below 98) | 30/30 = 100.00 % (meets 98) | 1 | below 98 |

A module that reaches 98 in a focused run is not thereby compliant: the release gate also needs a full native campaign on one revision with admissible provenance, owner records bound to that revision's digests, and the campaign-level policy evaluation. The release gate stays fail-closed.

### Correction of the earlier threshold statement

The earlier measurement of `research/temporal_pilot.py` was 571 killed of 589 (17 survived, 1 timeout), source digest prefix `03e63b296112`. With six exclusions the score would have been 571/583 = 97.94 % (below 98: 57100 < 57134); with seven, 571/582 = 98.11 % (meets 98). My earlier note that six accepted equivalents would suffice was wrong and is superseded here. For `research/typed_run.py` (343 of 351) one exclusion would give 343/350 = 98.00 %, exactly 98.00 % (34300 >= 34300), which the policy accepts. Both are hypothetical, and both measurements predate the tests added for this packet.

### Timeout and incomplete outcomes

The earlier temporal-pilot timeout was `x_block_bootstrap_ci__mutmut_40` (`index = None` in the bootstrap loop): the mutant makes sklearn compute average precision for a one-row multilabel input with one column per observation, which is slow but returns different numbers. A timeout was never treated as killed. The small test `test_a_small_bootstrap_equals_its_definition_and_runs_fast` alone did not remove the timeout, because mutmut runs the older test with 4,000 rows and 200 resamples first and the mutant makes it extremely slow; that older test now uses 1,500 rows and 60 resamples (same assertions: determinism and the interval brackets the estimate), and the mutant is killed. In the first alert-budget run one mutant (`x_run_job__mutmut_28`, a case-changed dictionary key) ended with exit code 255, an incomplete outcome; it was killed in the next run of the module, so the cause was the execution environment and not a property of the mutant. Outcomes other than killed and survived in the collected runs: none. Such an outcome is neither a survivor nor killed and is never counted as either.

## Individual case records

Fields: identity; source and catalog binding; original and mutated code; outcome; existing tests; why it survived; intended observable behavior; consumers; supported inputs; dependency sensitivity; evidence for and against; uncertainty; whether further testing could separate it; next technical action; owner decision status.

### `research/temporal_pilot.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `03e63b2961126c3192fec7fbf374b434e0ab81c54a1317c3cfa99ecb732b0982`; catalog SHA-256 `cc22ccb0d5ce93621a446a2041a971e3971144d1f710ada7002d7b198b0fe32e` (589 mutants); existing tests importing the module: `tests/test_temporal_pilot.py`, `tests/test_temporal_pilot_contracts.py`.

#### `research.temporal_pilot.x_block_bootstrap_ci__mutmut_38`

- Function: `block_bootstrap_ci`; outcome: survived; category: **Strong equivalence evidence** (family `choice_default`).
- Original: `chosen = rng.choice(len(keys), size=len(keys), replace=True)`
- Mutated: `chosen = rng.choice(len(keys), size=len(keys), )`
- Change: Generator.choice(..., replace=True) written without replace.
- Why it survived: replace=True is the documented default of numpy.random.Generator.choice, so omitting it requests the same sampling.
- Observable behavior: The block indices drawn by the bootstrap, hence the resampled average precisions and the interval.
- Downstream consumers: The temporal pilot interval stored in the pilot record and quoted in the manuscript.
- Supported inputs and boundaries: Any size and seed; the draws were compared for equal seeds.
- Dependency sensitivity: numpy 2.4.6 (default replace=True). A change of that default would break the claim.
- Evidence for equivalence: Documented default; `research/tests/test_equivalence_claims_focused.py::test_generator_choice_replaces_by_default` compares both forms over seeds.
- Evidence against or limits: None found.
- Remaining uncertainty: Relies on numpy keeping the default; the pinned version is recorded.
- Could further testing separate it: No: identical arguments after default resolution, so no input separates them.
- Recommended next technical action: Owner decision. If accepted it must be bound to the numpy version.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_main__mutmut_18`

- Function: `main`; outcome: survived; category: **Strong equivalence evidence** (family `argparse_default_none`).
- Original: `parser.add_argument("--csv", type=Path, default=None)`
- Mutated: `parser.add_argument("--csv", type=Path, )`
- Change: argparse option declared without default=None.
- Why it survived: argparse gives an option with no explicit default the value None, which is what default=None states.
- Observable behavior: The parsed value of --csv when the option is absent.
- Downstream consumers: The temporal pilot command line; the value is None in both forms.
- Supported inputs and boundaries: Any command line.
- Dependency sensitivity: Python argparse (documented behavior).
- Evidence for equivalence: Documented argparse behavior; the existing command-line tests pass an absent --csv.
- Evidence against or limits: None found.
- Remaining uncertainty: None identified.
- Could further testing separate it: No: the parsed namespace is identical.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_monitor_control__mutmut_101`

- Function: `monitor_control`; outcome: survived; category: **Strong equivalence evidence** (family `aware_utc`).
- Original: `"windows_before": int((pd.to_datetime(windows["window_end"], utc=True) < change).sum()),`
- Mutated: `"windows_before": int((pd.to_datetime(windows["window_end"], ) < change).sum()),`
- Change: pd.to_datetime(window_end, utc=...) on a column that is always timezone-aware.
- Why it survived: window_end is produced by WindowDriftMonitor.evaluate from timestamps that `_times` converted with utc=True, so the column is UTC-aware and utc=None, False or omitted leaves it unchanged; the comparison with an aware change time gives the same mask.
- Observable behavior: Which windows count as before or after the change, and the counts of windows before and after.
- Downstream consumers: Control-experiment fields written to the temporal pilot record.
- Supported inputs and boundaries: Only monitor-produced windows reach this line; naive input never does.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test run on both).
- Evidence for equivalence: `src/etl_benchmark/quality/window_drift.py::_times` always passes utc=True; `research/tests/test_equivalence_claims_focused.py::test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag` over UTC, Europe/Paris and Asia/Tokyo.
- Evidence against or limits: If the monitor were changed to return naive times the original would still work and the mutants would raise; then the claim would no longer hold.
- Remaining uncertainty: Depends on the monitor module keeping aware output.
- Could further testing separate it: Not through the public path: monitor_control builds windows itself.
- Recommended next technical action: Owner decision. Binding to the window_drift source digest is advisable.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_monitor_control__mutmut_104`

- Function: `monitor_control`; outcome: survived; category: **Strong equivalence evidence** (family `aware_utc`).
- Original: `"windows_before": int((pd.to_datetime(windows["window_end"], utc=True) < change).sum()),`
- Mutated: `"windows_before": int((pd.to_datetime(windows["window_end"], utc=False) < change).sum()),`
- Change: pd.to_datetime(window_end, utc=...) on a column that is always timezone-aware.
- Why it survived: window_end is produced by WindowDriftMonitor.evaluate from timestamps that `_times` converted with utc=True, so the column is UTC-aware and utc=None, False or omitted leaves it unchanged; the comparison with an aware change time gives the same mask.
- Observable behavior: Which windows count as before or after the change, and the counts of windows before and after.
- Downstream consumers: Control-experiment fields written to the temporal pilot record.
- Supported inputs and boundaries: Only monitor-produced windows reach this line; naive input never does.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test run on both).
- Evidence for equivalence: `src/etl_benchmark/quality/window_drift.py::_times` always passes utc=True; `research/tests/test_equivalence_claims_focused.py::test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag` over UTC, Europe/Paris and Asia/Tokyo.
- Evidence against or limits: If the monitor were changed to return naive times the original would still work and the mutants would raise; then the claim would no longer hold.
- Remaining uncertainty: Depends on the monitor module keeping aware output.
- Could further testing separate it: Not through the public path: monitor_control builds windows itself.
- Recommended next technical action: Owner decision. Binding to the window_drift source digest is advisable.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_monitor_control__mutmut_56`

- Function: `monitor_control`; outcome: survived; category: **Strong equivalence evidence** (family `aware_utc`).
- Original: `after = windows[pd.to_datetime(windows["window_end"], utc=True) >= change]`
- Mutated: `after = windows[pd.to_datetime(windows["window_end"], utc=None) >= change]`
- Change: pd.to_datetime(window_end, utc=...) on a column that is always timezone-aware.
- Why it survived: window_end is produced by WindowDriftMonitor.evaluate from timestamps that `_times` converted with utc=True, so the column is UTC-aware and utc=None, False or omitted leaves it unchanged; the comparison with an aware change time gives the same mask.
- Observable behavior: Which windows count as before or after the change, and the counts of windows before and after.
- Downstream consumers: Control-experiment fields written to the temporal pilot record.
- Supported inputs and boundaries: Only monitor-produced windows reach this line; naive input never does.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test run on both).
- Evidence for equivalence: `src/etl_benchmark/quality/window_drift.py::_times` always passes utc=True; `research/tests/test_equivalence_claims_focused.py::test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag` over UTC, Europe/Paris and Asia/Tokyo.
- Evidence against or limits: If the monitor were changed to return naive times the original would still work and the mutants would raise; then the claim would no longer hold.
- Remaining uncertainty: Depends on the monitor module keeping aware output.
- Could further testing separate it: Not through the public path: monitor_control builds windows itself.
- Recommended next technical action: Owner decision. Binding to the window_drift source digest is advisable.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_monitor_control__mutmut_58`

- Function: `monitor_control`; outcome: survived; category: **Strong equivalence evidence** (family `aware_utc`).
- Original: `after = windows[pd.to_datetime(windows["window_end"], utc=True) >= change]`
- Mutated: `after = windows[pd.to_datetime(windows["window_end"], ) >= change]`
- Change: pd.to_datetime(window_end, utc=...) on a column that is always timezone-aware.
- Why it survived: window_end is produced by WindowDriftMonitor.evaluate from timestamps that `_times` converted with utc=True, so the column is UTC-aware and utc=None, False or omitted leaves it unchanged; the comparison with an aware change time gives the same mask.
- Observable behavior: Which windows count as before or after the change, and the counts of windows before and after.
- Downstream consumers: Control-experiment fields written to the temporal pilot record.
- Supported inputs and boundaries: Only monitor-produced windows reach this line; naive input never does.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test run on both).
- Evidence for equivalence: `src/etl_benchmark/quality/window_drift.py::_times` always passes utc=True; `research/tests/test_equivalence_claims_focused.py::test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag` over UTC, Europe/Paris and Asia/Tokyo.
- Evidence against or limits: If the monitor were changed to return naive times the original would still work and the mutants would raise; then the claim would no longer hold.
- Remaining uncertainty: Depends on the monitor module keeping aware output.
- Could further testing separate it: Not through the public path: monitor_control builds windows itself.
- Recommended next technical action: Owner decision. Binding to the window_drift source digest is advisable.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_monitor_control__mutmut_61`

- Function: `monitor_control`; outcome: survived; category: **Strong equivalence evidence** (family `aware_utc`).
- Original: `after = windows[pd.to_datetime(windows["window_end"], utc=True) >= change]`
- Mutated: `after = windows[pd.to_datetime(windows["window_end"], utc=False) >= change]`
- Change: pd.to_datetime(window_end, utc=...) on a column that is always timezone-aware.
- Why it survived: window_end is produced by WindowDriftMonitor.evaluate from timestamps that `_times` converted with utc=True, so the column is UTC-aware and utc=None, False or omitted leaves it unchanged; the comparison with an aware change time gives the same mask.
- Observable behavior: Which windows count as before or after the change, and the counts of windows before and after.
- Downstream consumers: Control-experiment fields written to the temporal pilot record.
- Supported inputs and boundaries: Only monitor-produced windows reach this line; naive input never does.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test run on both).
- Evidence for equivalence: `src/etl_benchmark/quality/window_drift.py::_times` always passes utc=True; `research/tests/test_equivalence_claims_focused.py::test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag` over UTC, Europe/Paris and Asia/Tokyo.
- Evidence against or limits: If the monitor were changed to return naive times the original would still work and the mutants would raise; then the claim would no longer hold.
- Remaining uncertainty: Depends on the monitor module keeping aware output.
- Could further testing separate it: Not through the public path: monitor_control builds windows itself.
- Recommended next technical action: Owner decision. Binding to the window_drift source digest is advisable.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_monitor_control__mutmut_99`

- Function: `monitor_control`; outcome: survived; category: **Strong equivalence evidence** (family `aware_utc`).
- Original: `"windows_before": int((pd.to_datetime(windows["window_end"], utc=True) < change).sum()),`
- Mutated: `"windows_before": int((pd.to_datetime(windows["window_end"], utc=None) < change).sum()),`
- Change: pd.to_datetime(window_end, utc=...) on a column that is always timezone-aware.
- Why it survived: window_end is produced by WindowDriftMonitor.evaluate from timestamps that `_times` converted with utc=True, so the column is UTC-aware and utc=None, False or omitted leaves it unchanged; the comparison with an aware change time gives the same mask.
- Observable behavior: Which windows count as before or after the change, and the counts of windows before and after.
- Downstream consumers: Control-experiment fields written to the temporal pilot record.
- Supported inputs and boundaries: Only monitor-produced windows reach this line; naive input never does.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test run on both).
- Evidence for equivalence: `src/etl_benchmark/quality/window_drift.py::_times` always passes utc=True; `research/tests/test_equivalence_claims_focused.py::test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag` over UTC, Europe/Paris and Asia/Tokyo.
- Evidence against or limits: If the monitor were changed to return naive times the original would still work and the mutants would raise; then the claim would no longer hold.
- Remaining uncertainty: Depends on the monitor module keeping aware output.
- Could further testing separate it: Not through the public path: monitor_control builds windows itself.
- Recommended next technical action: Owner decision. Binding to the window_drift source digest is advisable.
- Owner decision status: **undecided** (no record exists).

#### `research.temporal_pilot.x_to_timestamps__mutmut_11`

- Function: `to_timestamps`; outcome: survived; category: **Additional verification required** (family `to_numpy_dtype_none`).
- Original: `if not np.isfinite(values.to_numpy(dtype=float)).all() or (values < 0).any():`
- Mutated: `if not np.isfinite(values.to_numpy(dtype=None)).all() or (values < 0).any():`
- Change: to_numpy(dtype=None) after pd.to_numeric.
- Why it survived: After numeric coercion the series is numeric or nullable numeric; to_numpy(dtype=None) then returns float64 with NaN for the tested dtypes, the same as dtype=float, so the finite check refuses the same input with the same message.
- Observable behavior: Whether non-finite elapsed times are refused with the stated message.
- Downstream consumers: Every caller of to_timestamps (temporal pilot).
- Supported inputs and boundaries: int64, float64, Int64 and Float64 with missing values, numeric strings.
- Dependency sensitivity: pandas 3.0.1, 3.0.6, 3.1.1 (probe on all three; pytest on the last two).
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_to_numpy_without_a_dtype_equals_float_after_numeric_coercion`; a test that refuses a nullable column with a missing value passes with both.
- Evidence against or limits: Behavior of nullable dtypes under to_numpy is a pandas implementation detail.
- Remaining uncertainty: Other extension dtypes (for example decimal or pyarrow-backed) were not checked.
- Could further testing separate it: Possibly with pyarrow-backed numeric series; none is supported by the pipeline today.
- Recommended next technical action: Owner decision, or extend the differential test to pyarrow-backed dtypes first.
- Owner decision status: **undecided** (no record exists).

### `research/typed_run.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `8589c4634fd7ffff31536e85772f2a84b6edc2f3a59c6860e8ff916abb76beb0`; catalog SHA-256 `e3bae5fa8f6aa1c58ea06c4939ffdcc849f86461e0818291f8334b524cd93fa9` (351 mutants); existing tests importing the module: `research/tests/test_pool_typed.py`, `research/tests/test_typed_benchmark.py`, `research/tests/test_typed_masking.py`, `research/tests/test_typed_run.py`.

#### `research.typed_run.x_run_one__mutmut_48`

- Function: `run_one`; outcome: survived; category: **Additional verification required** (family `groupby_sort_none`).
- Original: `mean = stack.groupby(level=1, sort=False).mean()`
- Mutated: `mean = stack.groupby(level=1, sort=None).mean()`
- Change: groupby(..., sort=None) in place of sort=False.
- Why it survived: pandas treats a falsy sort as not sorting, so None groups in order of appearance exactly as False does.
- Observable behavior: Order and values of the per-method means (recall, precision, severity curves).
- Downstream consumers: Typed-injection reference and severity result files, summary tables and figures.
- Supported inputs and boundaries: Series concatenated over seeds; the order of appearance was checked with unsorted labels.
- Dependency sensitivity: pandas 3.0.1, 3.0.6, 3.1.1. The parameter is documented as a bool; None is outside that contract.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_groupby_sort_none_groups_exactly_like_sort_false` over unsorted labels on pandas 3.0.6 and 3.1.1; probe on 3.0.1.
- Evidence against or limits: Passing None where a bool is documented is the same shape as the LSTM `replace=None` candidate that the owner left inconclusive on 2026-11-11.
- Remaining uncertainty: A future pandas could validate the argument as a strict bool.
- Could further testing separate it: Not by behavior on current pandas; only by a dependency matrix.
- Recommended next technical action: Owner decision, consistent with the earlier inconclusive precedent for None passed to a boolean parameter.
- Owner decision status: **undecided** (no record exists).

#### `research.typed_run.x_run_one__mutmut_55`

- Function: `run_one`; outcome: survived; category: **Additional verification required** (family `groupby_sort_none`).
- Original: `pd.concat(precisions, keys=range(len(precisions))).groupby(level=1, sort=False).mean()`
- Mutated: `pd.concat(precisions, keys=range(len(precisions))).groupby(level=1, sort=None).mean()`
- Change: groupby(..., sort=None) in place of sort=False.
- Why it survived: pandas treats a falsy sort as not sorting, so None groups in order of appearance exactly as False does.
- Observable behavior: Order and values of the per-method means (recall, precision, severity curves).
- Downstream consumers: Typed-injection reference and severity result files, summary tables and figures.
- Supported inputs and boundaries: Series concatenated over seeds; the order of appearance was checked with unsorted labels.
- Dependency sensitivity: pandas 3.0.1, 3.0.6, 3.1.1. The parameter is documented as a bool; None is outside that contract.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_groupby_sort_none_groups_exactly_like_sort_false` over unsorted labels on pandas 3.0.6 and 3.1.1; probe on 3.0.1.
- Evidence against or limits: Passing None where a bool is documented is the same shape as the LSTM `replace=None` candidate that the owner left inconclusive on 2026-11-11.
- Remaining uncertainty: A future pandas could validate the argument as a strict bool.
- Could further testing separate it: Not by behavior on current pandas; only by a dependency matrix.
- Recommended next technical action: Owner decision, consistent with the earlier inconclusive precedent for None passed to a boolean parameter.
- Owner decision status: **undecided** (no record exists).

### `research/pool_typed.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `0b477c1c51fc616596b5ed3b09841a0374f1bc26603f22a2bc7c7ee638a8bbad`; catalog SHA-256 `eaca1600c7831c2cd9e392d7b11f17facb0b34efbb907563181d17efee170623` (525 mutants); existing tests importing the module: `research/tests/test_pool_etl.py`, `research/tests/test_pool_typed.py`.

#### `research.pool_typed.x_load_carrier__mutmut_29`

- Function: `load_carrier`; outcome: survived; category: **Additional verification required** (family `label_cast`).
- Original: `features = pd.DataFrame(data["X"]).add_prefix("f")[np.asarray(data["y"]).astype(int) == 0]`
- Mutated: `features = pd.DataFrame(data["X"]).add_prefix("f")[np.asarray(data["y"]).astype(None) == 0]`
- Change: np.asarray(labels).astype(None) in place of .astype(int) before comparing with 0.
- Why it survived: NumPy resolves astype(None) to float64; for the binary labels 0/1 (as integers, booleans, floats or digit strings) the comparison with 0 is identical.
- Observable behavior: Which rows are selected as the normal class when loading a carrier.
- Downstream consumers: Pool carrier construction in the typed severity experiment.
- Supported inputs and boundaries: Binary labels only. Fractional labels differ: 0.5 is 0 under int and 0.5 under float.
- Dependency sensitivity: numpy 2.4.6.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_numpy_astype_none_agrees_with_int_for_binary_labels`.
- Evidence against or limits: `research/tests/test_equivalence_claims_focused.py::test_numpy_astype_none_differs_from_int_for_fractional_labels` shows the forms differ outside the binary contract; no validation of the label range was found at this call.
- Remaining uncertainty: Whether the loader guarantees binary labels for every registered file.
- Could further testing separate it: Yes: a test with fractional or NaN labels would separate the two if the contract is to refuse them.
- Recommended next technical action: Technical first: decide whether non-binary labels must be refused here (then add the test and keep the mutant eligible); otherwise owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.pool_typed.x_run_reference__mutmut_33`

- Function: `run_reference`; outcome: survived; category: **Additional verification required** (family `groupby_sort_none`).
- Original: `mean = pd.concat(recalls, keys=range(len(recalls))).groupby(level=1, sort=False).mean()`
- Mutated: `mean = pd.concat(recalls, keys=range(len(recalls))).groupby(level=1, sort=None).mean()`
- Change: groupby(..., sort=None) in place of sort=False.
- Why it survived: pandas treats a falsy sort as not sorting, so None groups in order of appearance exactly as False does.
- Observable behavior: Order and values of the per-method means (recall, precision, severity curves).
- Downstream consumers: Typed-injection reference and severity result files, summary tables and figures.
- Supported inputs and boundaries: Series concatenated over seeds; the order of appearance was checked with unsorted labels.
- Dependency sensitivity: pandas 3.0.1, 3.0.6, 3.1.1. The parameter is documented as a bool; None is outside that contract.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_groupby_sort_none_groups_exactly_like_sort_false` over unsorted labels on pandas 3.0.6 and 3.1.1; probe on 3.0.1.
- Evidence against or limits: Passing None where a bool is documented is the same shape as the LSTM `replace=None` candidate that the owner left inconclusive on 2026-11-11.
- Remaining uncertainty: A future pandas could validate the argument as a strict bool.
- Could further testing separate it: Not by behavior on current pandas; only by a dependency matrix.
- Recommended next technical action: Owner decision, consistent with the earlier inconclusive precedent for None passed to a boolean parameter.
- Owner decision status: **undecided** (no record exists).

#### `research.pool_typed.x_run_reference__mutmut_45`

- Function: `run_reference`; outcome: survived; category: **Additional verification required** (family `groupby_sort_none`).
- Original: `pd.concat(precisions, keys=range(len(precisions))).groupby(level=1, sort=False).mean()`
- Mutated: `pd.concat(precisions, keys=range(len(precisions))).groupby(level=1, sort=None).mean()`
- Change: groupby(..., sort=None) in place of sort=False.
- Why it survived: pandas treats a falsy sort as not sorting, so None groups in order of appearance exactly as False does.
- Observable behavior: Order and values of the per-method means (recall, precision, severity curves).
- Downstream consumers: Typed-injection reference and severity result files, summary tables and figures.
- Supported inputs and boundaries: Series concatenated over seeds; the order of appearance was checked with unsorted labels.
- Dependency sensitivity: pandas 3.0.1, 3.0.6, 3.1.1. The parameter is documented as a bool; None is outside that contract.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_groupby_sort_none_groups_exactly_like_sort_false` over unsorted labels on pandas 3.0.6 and 3.1.1; probe on 3.0.1.
- Evidence against or limits: Passing None where a bool is documented is the same shape as the LSTM `replace=None` candidate that the owner left inconclusive on 2026-11-11.
- Remaining uncertainty: A future pandas could validate the argument as a strict bool.
- Could further testing separate it: Not by behavior on current pandas; only by a dependency matrix.
- Recommended next technical action: Owner decision, consistent with the earlier inconclusive precedent for None passed to a boolean parameter.
- Owner decision status: **undecided** (no record exists).

#### `research.pool_typed.x_run_severity__mutmut_28`

- Function: `run_severity`; outcome: survived; category: **Additional verification required** (family `groupby_sort_none`).
- Original: `mean = pd.concat(frames, keys=range(len(frames))).groupby(level=1, sort=False).mean()`
- Mutated: `mean = pd.concat(frames, keys=range(len(frames))).groupby(level=1, sort=None).mean()`
- Change: groupby(..., sort=None) in place of sort=False.
- Why it survived: pandas treats a falsy sort as not sorting, so None groups in order of appearance exactly as False does.
- Observable behavior: Order and values of the per-method means (recall, precision, severity curves).
- Downstream consumers: Typed-injection reference and severity result files, summary tables and figures.
- Supported inputs and boundaries: Series concatenated over seeds; the order of appearance was checked with unsorted labels.
- Dependency sensitivity: pandas 3.0.1, 3.0.6, 3.1.1. The parameter is documented as a bool; None is outside that contract.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_groupby_sort_none_groups_exactly_like_sort_false` over unsorted labels on pandas 3.0.6 and 3.1.1; probe on 3.0.1.
- Evidence against or limits: Passing None where a bool is documented is the same shape as the LSTM `replace=None` candidate that the owner left inconclusive on 2026-11-11.
- Remaining uncertainty: A future pandas could validate the argument as a strict bool.
- Could further testing separate it: Not by behavior on current pandas; only by a dependency matrix.
- Recommended next technical action: Owner decision, consistent with the earlier inconclusive precedent for None passed to a boolean parameter.
- Owner decision status: **undecided** (no record exists).

### `research/normalise.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `5ba131d186d79c792fb64691089939fffb3a085e1f376c6b9dcd1c12bcf5155a`; catalog SHA-256 `fc5f5c3a0445d43054017cca9eb565f9765360e1590f5b7433cbc817ab36804c` (197 mutants); existing tests importing the module: `tests/test_pool_preprocessing.py`, `research/tests/test_build_pool.py`, `research/tests/test_equivalence_claims_focused.py`, `research/tests/test_label_and_cleaning_contracts.py`, `research/tests/test_labelled_contracts.py`, `research/tests/test_normalise.py`, `research/tests/test_recover_partitions.py`.

#### `research.normalise.x_clean__mutmut_34`

- Function: `clean`; outcome: survived; category: **Strong equivalence evidence** (family `labels_invisible`).
- Original: `pieces.append(col.astype(float).rename(name))`
- Mutated: `pieces.append(col.astype(float).rename(None))`
- Change: Column label of a cleaned feature piece (rename, dummy prefix).
- Why it survived: The labels exist only on the local `table` inside clean(); the function returns table.to_numpy() and a report of counts and original names, and the row hash uses index=False values, so labels never reach an output.
- Observable behavior: Nothing: the returned array, labels and report are unchanged.
- Downstream consumers: Pool preparation and labelled benchmark through clean().
- Supported inputs and boundaries: Numeric, boolean, categorical and constant columns.
- Dependency sensitivity: pandas get_dummies and concat (labels do not affect values or column order).
- Evidence for equivalence: Code reading (the table is local); `research/tests/test_equivalence_claims_focused.py::test_cleaning_returns_values_not_column_labels`.
- Evidence against or limits: If clean() ever returned the DataFrame or recorded feature names, the labels would become observable.
- Remaining uncertainty: Depends on clean() keeping returning an ndarray.
- Could further testing separate it: Yes, if the function starts exposing feature names: that would turn these into killable mutants.
- Recommended next technical action: Owner decision, bound to the normalise source digest.
- Owner decision status: **undecided** (no record exists).

#### `research.normalise.x_clean__mutmut_35`

- Function: `clean`; outcome: survived; category: **Additional verification required** (family `astype_none`).
- Original: `pieces.append(col.astype(float).rename(name))`
- Mutated: `pieces.append(col.astype(None).rename(name))`
- Change: astype(None) in place of astype(float).
- Why it survived: pandas and NumPy resolve astype(None) to float64, so the tested inputs give identical results.
- Observable behavior: The dtype and values of the cast column or score.
- Downstream consumers: Feature cleaning in normalise.clean and the base detector score method.
- Supported inputs and boundaries: bool, int64, float64, Int64 and Float64 with missing values, numeric strings.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test), numpy 2.4.6.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_pandas_astype_none_is_astype_float`.
- Evidence against or limits: Equality rests on how pandas interprets None as a dtype, which is not a stated contract; the owner left the similar LSTM astype(None) candidates inconclusive on 2026-11-11.
- Remaining uncertainty: Other dtypes (datetime, categorical, pyarrow) not exercised.
- Could further testing separate it: Only by a wider dtype matrix or a dependency matrix.
- Recommended next technical action: Owner decision, with the earlier inconclusive precedent in view.
- Owner decision status: **undecided** (no record exists).

#### `research.normalise.x_clean__mutmut_45`

- Function: `clean`; outcome: survived; category: **Strong equivalence evidence** (family `labels_invisible`).
- Original: `pieces.append(pd.get_dummies(col.astype(str), prefix=str(name), dtype=float))`
- Mutated: `pieces.append(pd.get_dummies(col.astype(str), prefix=None, dtype=float))`
- Change: Column label of a cleaned feature piece (rename, dummy prefix).
- Why it survived: The labels exist only on the local `table` inside clean(); the function returns table.to_numpy() and a report of counts and original names, and the row hash uses index=False values, so labels never reach an output.
- Observable behavior: Nothing: the returned array, labels and report are unchanged.
- Downstream consumers: Pool preparation and labelled benchmark through clean().
- Supported inputs and boundaries: Numeric, boolean, categorical and constant columns.
- Dependency sensitivity: pandas get_dummies and concat (labels do not affect values or column order).
- Evidence for equivalence: Code reading (the table is local); `research/tests/test_equivalence_claims_focused.py::test_cleaning_returns_values_not_column_labels`.
- Evidence against or limits: If clean() ever returned the DataFrame or recorded feature names, the labels would become observable.
- Remaining uncertainty: Depends on clean() keeping returning an ndarray.
- Could further testing separate it: Yes, if the function starts exposing feature names: that would turn these into killable mutants.
- Recommended next technical action: Owner decision, bound to the normalise source digest.
- Owner decision status: **undecided** (no record exists).

#### `research.normalise.x_clean__mutmut_48`

- Function: `clean`; outcome: survived; category: **Strong equivalence evidence** (family `labels_invisible`).
- Original: `pieces.append(pd.get_dummies(col.astype(str), prefix=str(name), dtype=float))`
- Mutated: `pieces.append(pd.get_dummies(col.astype(str), dtype=float))`
- Change: Column label of a cleaned feature piece (rename, dummy prefix).
- Why it survived: The labels exist only on the local `table` inside clean(); the function returns table.to_numpy() and a report of counts and original names, and the row hash uses index=False values, so labels never reach an output.
- Observable behavior: Nothing: the returned array, labels and report are unchanged.
- Downstream consumers: Pool preparation and labelled benchmark through clean().
- Supported inputs and boundaries: Numeric, boolean, categorical and constant columns.
- Dependency sensitivity: pandas get_dummies and concat (labels do not affect values or column order).
- Evidence for equivalence: Code reading (the table is local); `research/tests/test_equivalence_claims_focused.py::test_cleaning_returns_values_not_column_labels`.
- Evidence against or limits: If clean() ever returned the DataFrame or recorded feature names, the labels would become observable.
- Remaining uncertainty: Depends on clean() keeping returning an ndarray.
- Could further testing separate it: Yes, if the function starts exposing feature names: that would turn these into killable mutants.
- Recommended next technical action: Owner decision, bound to the normalise source digest.
- Owner decision status: **undecided** (no record exists).

#### `research.normalise.x_clean__mutmut_51`

- Function: `clean`; outcome: survived; category: **Strong equivalence evidence** (family `labels_invisible`).
- Original: `pieces.append(pd.get_dummies(col.astype(str), prefix=str(name), dtype=float))`
- Mutated: `pieces.append(pd.get_dummies(col.astype(str), prefix=str(None), dtype=float))`
- Change: Column label of a cleaned feature piece (rename, dummy prefix).
- Why it survived: The labels exist only on the local `table` inside clean(); the function returns table.to_numpy() and a report of counts and original names, and the row hash uses index=False values, so labels never reach an output.
- Observable behavior: Nothing: the returned array, labels and report are unchanged.
- Downstream consumers: Pool preparation and labelled benchmark through clean().
- Supported inputs and boundaries: Numeric, boolean, categorical and constant columns.
- Dependency sensitivity: pandas get_dummies and concat (labels do not affect values or column order).
- Evidence for equivalence: Code reading (the table is local); `research/tests/test_equivalence_claims_focused.py::test_cleaning_returns_values_not_column_labels`.
- Evidence against or limits: If clean() ever returned the DataFrame or recorded feature names, the labels would become observable.
- Remaining uncertainty: Depends on clean() keeping returning an ndarray.
- Could further testing separate it: Yes, if the function starts exposing feature names: that would turn these into killable mutants.
- Recommended next technical action: Owner decision, bound to the normalise source digest.
- Owner decision status: **undecided** (no record exists).

#### `research.normalise.x_clean__mutmut_64`

- Function: `clean`; outcome: survived; category: **Additional verification required** (family `index_none`).
- Original: `keys = pd.util.hash_pandas_object(table.fillna(np.inf), index=False)`
- Mutated: `keys = pd.util.hash_pandas_object(table.fillna(np.inf), index=None)`
- Change: index=None in place of index=False.
- Why it survived: pandas treats a falsy index flag as not writing or hashing the index.
- Observable behavior: The CSV text written, or the row hash used to find duplicates and conflicts.
- Downstream consumers: CSV exports (src/etl_benchmark/load.py) and duplicate detection in normalise.clean.
- Supported inputs and boundaries: Frames with default and non-default indexes.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1. The parameter is documented as bool.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_csv_and_row_hash_treat_a_missing_index_flag_as_false`.
- Evidence against or limits: Same shape as passing None to a boolean parameter, which the owner left inconclusive before.
- Remaining uncertainty: Future validation of the argument type.
- Could further testing separate it: Not by behavior on current pandas.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

### `research/build_pool.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `eefa0438f61e44b0bd0c7ed9a8acf7477a181477c4c8c90dc51803fa6391b3f6`; catalog SHA-256 `8376de93b7f33099e83dea80a0bdf12328a907743b11c7f2941b397e7a0bde2c` (172 mutants); existing tests importing the module: `research/tests/test_build_pool.py`, `research/tests/test_uci_loader.py`.

#### `research.build_pool.x_main__mutmut_27`

- Function: `main`; outcome: survived; category: **Strong equivalence evidence** (family `arg_type_path`).
- Original: `parser.add_argument("--output", type=Path, required=True)`
- Mutated: `parser.add_argument("--output", type=None, required=True)`
- Change: argparse --output declared with type=None or without type.
- Why it survived: Both leave --output a str, while the original converts it to Path. The value is used only as the argument of atomic_path, which starts with Path(path).
- Observable behavior: Nothing, unless another statement used a Path method on args.output; none does.
- Downstream consumers: Command line of the pool builder and the pool checker.
- Supported inputs and boundaries: Any path string.
- Dependency sensitivity: None beyond the module source.
- Evidence for equivalence: `src/etl_benchmark/atomic.py::atomic_path` converts its argument with Path(path); args.output has no other use in either main().
- Evidence against or limits: A later use of args.output as a Path (for example args.output.parent) would make the original and the mutants differ.
- Remaining uncertainty: Depends on args.output staying confined to atomic_path.
- Could further testing separate it: A spy on atomic_path asserting a Path argument would kill the mutants but would pin an internal type rather than behavior.
- Recommended next technical action: Owner decision, bound to the module digest.
- Owner decision status: **undecided** (no record exists).

#### `research.build_pool.x_main__mutmut_30`

- Function: `main`; outcome: survived; category: **Strong equivalence evidence** (family `arg_type_path`).
- Original: `parser.add_argument("--output", type=Path, required=True)`
- Mutated: `parser.add_argument("--output", required=True)`
- Change: argparse --output declared with type=None or without type.
- Why it survived: Both leave --output a str, while the original converts it to Path. The value is used only as the argument of atomic_path, which starts with Path(path).
- Observable behavior: Nothing, unless another statement used a Path method on args.output; none does.
- Downstream consumers: Command line of the pool builder and the pool checker.
- Supported inputs and boundaries: Any path string.
- Dependency sensitivity: None beyond the module source.
- Evidence for equivalence: `src/etl_benchmark/atomic.py::atomic_path` converts its argument with Path(path); args.output has no other use in either main().
- Evidence against or limits: A later use of args.output as a Path (for example args.output.parent) would make the original and the mutants differ.
- Remaining uncertainty: Depends on args.output staying confined to atomic_path.
- Could further testing separate it: A spy on atomic_path asserting a Path argument would kill the mutants but would pin an internal type rather than behavior.
- Recommended next technical action: Owner decision, bound to the module digest.
- Owner decision status: **undecided** (no record exists).

#### `research.build_pool.x_pool_row__mutmut_38`

- Function: `pool_row`; outcome: survived; category: **Strong equivalence evidence** (family `constant_labels`).
- Original: `_, _, report = nm.clean(features, [0] * len(features))`
- Mutated: `_, _, report = nm.clean(features, [1] * len(features))`
- Change: clean(features, [1] * n) in place of [0] * n.
- Why it survived: The label vector is constant, so within every group of identical rows the number of distinct labels is 1 whichever constant is used: no conflict is found and the report is identical; the returned labels are discarded.
- Observable behavior: The carrier report (rows, duplicates, features), identical in both forms.
- Downstream consumers: The carrier section of the pool inventory.
- Supported inputs and boundaries: Any feature frame.
- Dependency sensitivity: None.
- Evidence for equivalence: Proof from the definition of conflicting rows; `research/tests/test_equivalence_claims_focused.py::test_constant_label_vectors_give_the_same_cleaning` over four random frames.
- Evidence against or limits: None found.
- Remaining uncertainty: None identified.
- Could further testing separate it: No: the two inputs are indistinguishable by every output.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

### `src/etl_benchmark/load.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `bc450a2553f333662bb447de1c7cd9aabb274b2f608b8e57ad80e48321b9c98e`; catalog SHA-256 `cc261ce7827925bd34d67f62212c84c83724a60a6d486133bda58616d471f706` (14 mutants); existing tests importing the module: `tests/test_atomic_publication.py`, `tests/test_claims_provenance.py`, `tests/test_pipeline_contracts.py`, `tests/test_robustness.py`.

#### `etl_benchmark.load.x_write_csv__mutmut_11`

- Function: `write_csv`; outcome: survived; category: **Additional verification required** (family `index_none`).
- Original: `df.to_csv(partial, index=False)`
- Mutated: `df.to_csv(partial, index=None)`
- Change: index=None in place of index=False.
- Why it survived: pandas treats a falsy index flag as not writing or hashing the index.
- Observable behavior: The CSV text written, or the row hash used to find duplicates and conflicts.
- Downstream consumers: CSV exports (src/etl_benchmark/load.py) and duplicate detection in normalise.clean.
- Supported inputs and boundaries: Frames with default and non-default indexes.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1. The parameter is documented as bool.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_csv_and_row_hash_treat_a_missing_index_flag_as_false`.
- Evidence against or limits: Same shape as passing None to a boolean parameter, which the owner left inconclusive before.
- Remaining uncertainty: Future validation of the argument type.
- Could further testing separate it: Not by behavior on current pandas.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

### `src/etl_benchmark/quality/base.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `9efc8a6a410b92d81f4ee09f9d001f8adad62a779250b3b552db9878f9de28ff`; catalog SHA-256 `fa09c2c86ed2f77bf715f144b9d29023ff9fb101061b5bf7aea7e0c05f8fe55f` (31 mutants); existing tests importing the module: `tests/test_detector_contracts.py`, `tests/test_detector_protocol.py`.

#### `etl_benchmark.quality.base.xǁDetectorǁscore__mutmut_1`

- Function: `score`; outcome: survived; category: **Additional verification required** (family `astype_none`).
- Original: `return self.predict(df).astype(float)`
- Mutated: `return self.predict(df).astype(None)`
- Change: astype(None) in place of astype(float).
- Why it survived: pandas and NumPy resolve astype(None) to float64, so the tested inputs give identical results.
- Observable behavior: The dtype and values of the cast column or score.
- Downstream consumers: Feature cleaning in normalise.clean and the base detector score method.
- Supported inputs and boundaries: bool, int64, float64, Int64 and Float64 with missing values, numeric strings.
- Dependency sensitivity: pandas 3.0.6 and 3.1.1 (differential test), numpy 2.4.6.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_pandas_astype_none_is_astype_float`.
- Evidence against or limits: Equality rests on how pandas interprets None as a dtype, which is not a stated contract; the owner left the similar LSTM astype(None) candidates inconclusive on 2026-11-11.
- Remaining uncertainty: Other dtypes (datetime, categorical, pyarrow) not exercised.
- Could further testing separate it: Only by a wider dtype matrix or a dependency matrix.
- Recommended next technical action: Owner decision, with the earlier inconclusive precedent in view.
- Owner decision status: **undecided** (no record exists).

### `research/pool_check.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `5981ee3fea87f589524072ba00084682547a2435ea816bf62b92da414f776c96`; catalog SHA-256 `51febc8d6bdafe700609429ec61428d80f9f5008eea7b190d2ec2a12732504fd` (180 mutants); existing tests importing the module: `research/tests/test_pool_check.py`.

#### `research.pool_check.x_main__mutmut_27`

- Function: `main`; outcome: survived; category: **Strong equivalence evidence** (family `arg_type_path`).
- Original: `parser.add_argument("--output", type=Path, required=True)`
- Mutated: `parser.add_argument("--output", type=None, required=True)`
- Change: argparse --output declared with type=None or without type.
- Why it survived: Both leave --output a str, while the original converts it to Path. The value is used only as the argument of atomic_path, which starts with Path(path).
- Observable behavior: Nothing, unless another statement used a Path method on args.output; none does.
- Downstream consumers: Command line of the pool builder and the pool checker.
- Supported inputs and boundaries: Any path string.
- Dependency sensitivity: None beyond the module source.
- Evidence for equivalence: `src/etl_benchmark/atomic.py::atomic_path` converts its argument with Path(path); args.output has no other use in either main().
- Evidence against or limits: A later use of args.output as a Path (for example args.output.parent) would make the original and the mutants differ.
- Remaining uncertainty: Depends on args.output staying confined to atomic_path.
- Could further testing separate it: A spy on atomic_path asserting a Path argument would kill the mutants but would pin an internal type rather than behavior.
- Recommended next technical action: Owner decision, bound to the module digest.
- Owner decision status: **undecided** (no record exists).

#### `research.pool_check.x_main__mutmut_30`

- Function: `main`; outcome: survived; category: **Strong equivalence evidence** (family `arg_type_path`).
- Original: `parser.add_argument("--output", type=Path, required=True)`
- Mutated: `parser.add_argument("--output", required=True)`
- Change: argparse --output declared with type=None or without type.
- Why it survived: Both leave --output a str, while the original converts it to Path. The value is used only as the argument of atomic_path, which starts with Path(path).
- Observable behavior: Nothing, unless another statement used a Path method on args.output; none does.
- Downstream consumers: Command line of the pool builder and the pool checker.
- Supported inputs and boundaries: Any path string.
- Dependency sensitivity: None beyond the module source.
- Evidence for equivalence: `src/etl_benchmark/atomic.py::atomic_path` converts its argument with Path(path); args.output has no other use in either main().
- Evidence against or limits: A later use of args.output as a Path (for example args.output.parent) would make the original and the mutants differ.
- Remaining uncertainty: Depends on args.output staying confined to atomic_path.
- Could further testing separate it: A spy on atomic_path asserting a Path argument would kill the mutants but would pin an internal type rather than behavior.
- Recommended next technical action: Owner decision, bound to the module digest.
- Owner decision status: **undecided** (no record exists).

### `research/matched_alert.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `dac27eab8804462e153242158a3cea09c965809de189a9f398e4ee33a27657b3`; catalog SHA-256 `c9283ec7191fcbd76aa0c4e2684ab77b25b989ff5317a5ba27f8621388d1f2b5` (322 mutants); existing tests importing the module: `research/tests/test_matched_alert.py`.

#### `research.matched_alert.x_analyse__mutmut_20`

- Function: `analyse`; outcome: survived; category: **Strong equivalence evidence** (family `or_true_empty_holm`).
- Original: `adjusted = holm([e[metric]["p_two_sided"] for e in scored]) if scored else []`
- Mutated: `adjusted = holm([e[metric]["p_two_sided"] for e in scored]) if (scored) or True else []`
- Change: `if scored else []` replaced by `if (scored) or True else []`.
- Why it survived: With nothing scored the mutant calls holm([]), which returns []; the zip loop then has nothing to pair.
- Observable behavior: The adjusted p-values written to each comparison entry.
- Downstream consumers: Matched-alert analysis file.
- Supported inputs and boundaries: An empty family of comparisons.
- Dependency sensitivity: None.
- Evidence for equivalence: holm([]) is [] by construction (empty argsort); `research/tests/test_equivalence_claims_focused.py::test_holm_of_nothing_is_nothing`.
- Evidence against or limits: None found.
- Remaining uncertainty: Holm would have to raise on empty input for the claim to fail.
- Could further testing separate it: No.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.matched_alert.x_compare__mutmut_43`

- Function: `compare`; outcome: survived; category: **Strong equivalence evidence** (family `problems_count_only`).
- Original: `problems.append(run["problem"])`
- Mutated: `problems.append(None)`
- Change: problems.append(None) in place of problems.append(run['problem']).
- Why it survived: The list `problems` is read only for len(problems) and for its truthiness; its elements are never used, so None and the problem name are indistinguishable.
- Observable behavior: The count of problems and whether any problem is present.
- Downstream consumers: Matched-alert comparison entries.
- Supported inputs and boundaries: Any runs.
- Dependency sensitivity: None.
- Evidence for equivalence: Code reading of compare(): `sources` carries the identities; `problems` is used as `len(problems)` and `if problems:`.
- Evidence against or limits: A later use of the elements would make the original differ.
- Remaining uncertainty: Depends on the function staying this way.
- Could further testing separate it: No, unless the elements start being used.
- Recommended next technical action: Owner decision. A cleaner alternative is to replace the list by a counter, which removes the mutant.
- Owner decision status: **undecided** (no record exists).

### `research/prevalence_shift.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `d89afbf352b0ca891de4dfbd1a6507b20e48f55745752d0e6f715ee3943567b3`; catalog SHA-256 `61b828c5c6044a1711dc3686b43952467fcd16a4fed09a8e5c3bca9c1834e734` (369 mutants); existing tests importing the module: `research/tests/test_prevalence_shift.py`.

#### `research.prevalence_shift.x_contrasts__mutmut_59`

- Function: `contrasts`; outcome: survived; category: **Strong equivalence evidence** (family `zip_same_source`).
- Original: `m: float(np.mean([a[m] - b[m] for a, b in zip(moved, observed, strict=True)]))`
- Mutated: `m: float(np.mean([a[m] - b[m] for a, b in zip(moved, observed, strict=None)]))`
- Change: zip(moved, observed, strict=...) over two lists built from the same cells.
- Why it survived: `moved` and `observed` are comprehensions over the same `cells` list, so their lengths are equal by construction; strict only changes behavior if the lengths differ.
- Observable behavior: Nothing under the construction; strict=True is a defensive assertion.
- Downstream consumers: Prevalence-shift contrasts.
- Supported inputs and boundaries: Any cells.
- Dependency sensitivity: Python zip(strict=...) semantics.
- Evidence for equivalence: Code reading: both lists iterate `cells` once.
- Evidence against or limits: None found.
- Remaining uncertainty: None under the present code.
- Could further testing separate it: Only by replacing the comprehensions with an injected list, which would change the code under test.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.prevalence_shift.x_contrasts__mutmut_62`

- Function: `contrasts`; outcome: survived; category: **Strong equivalence evidence** (family `zip_same_source`).
- Original: `m: float(np.mean([a[m] - b[m] for a, b in zip(moved, observed, strict=True)]))`
- Mutated: `m: float(np.mean([a[m] - b[m] for a, b in zip(moved, observed, )]))`
- Change: zip(moved, observed, strict=...) over two lists built from the same cells.
- Why it survived: `moved` and `observed` are comprehensions over the same `cells` list, so their lengths are equal by construction; strict only changes behavior if the lengths differ.
- Observable behavior: Nothing under the construction; strict=True is a defensive assertion.
- Downstream consumers: Prevalence-shift contrasts.
- Supported inputs and boundaries: Any cells.
- Dependency sensitivity: Python zip(strict=...) semantics.
- Evidence for equivalence: Code reading: both lists iterate `cells` once.
- Evidence against or limits: None found.
- Remaining uncertainty: None under the present code.
- Could further testing separate it: Only by replacing the comprehensions with an injected list, which would change the code under test.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.prevalence_shift.x_contrasts__mutmut_63`

- Function: `contrasts`; outcome: survived; category: **Strong equivalence evidence** (family `zip_same_source`).
- Original: `m: float(np.mean([a[m] - b[m] for a, b in zip(moved, observed, strict=True)]))`
- Mutated: `m: float(np.mean([a[m] - b[m] for a, b in zip(moved, observed, strict=False)]))`
- Change: zip(moved, observed, strict=...) over two lists built from the same cells.
- Why it survived: `moved` and `observed` are comprehensions over the same `cells` list, so their lengths are equal by construction; strict only changes behavior if the lengths differ.
- Observable behavior: Nothing under the construction; strict=True is a defensive assertion.
- Downstream consumers: Prevalence-shift contrasts.
- Supported inputs and boundaries: Any cells.
- Dependency sensitivity: Python zip(strict=...) semantics.
- Evidence for equivalence: Code reading: both lists iterate `cells` once.
- Evidence against or limits: None found.
- Remaining uncertainty: None under the present code.
- Could further testing separate it: Only by replacing the comprehensions with an injected list, which would change the code under test.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

### `research/source_clustered.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `a9bf13c575ea6e33c6055a9da5f23ee5f9c71ff1e0329815343a821008764352`; catalog SHA-256 `01a659dc95eb8fb1b996b8453229f9d186132d5da6c781ddf32faca74ce850da` (337 mutants); existing tests importing the module: `research/tests/test_equivalence_claims_focused.py`, `research/tests/test_source_clustered.py`.

#### `research.source_clustered.x_source_id__mutmut_3`

- Function: `source_id`; outcome: survived; category: **Strong equivalence evidence** (family `rpartition`).
- Original: `kind, _, name = problem.partition(":")`
- Mutated: `kind, _, name = problem.rpartition(":")`
- Change: problem.rpartition(':') in place of partition(':').
- Why it survived: The branch that changes the result needs kind == 'adbench' and a name found in UCI_SOURCES, whose keys contain no colon; for such strings both splits agree, and for every other string both fall through to the problem itself.
- Observable behavior: The source identity returned for a problem name.
- Downstream consumers: All source-clustered analyses.
- Supported inputs and boundaries: All problem names including several colons and no colon.
- Dependency sensitivity: The UCI_SOURCES keys must stay colon-free.
- Evidence for equivalence: `research/tests/test_equivalence_claims_focused.py::test_source_ids_do_not_depend_on_which_colon_splits_the_problem_name` includes a key check.
- Evidence against or limits: A source key with a colon would separate them.
- Remaining uncertainty: Depends on the registry content (asserted by the test).
- Could further testing separate it: No.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

### `research/alert_budget.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `0da6a79ece4e6cbd8066eb2474f653ba69eb2247caeeb0f77e3cf9b48be5a7e9`; catalog SHA-256 `915d24939fd557d28c76bc48d060bab0edc0af26309281c6bbfb5b3b375a6d8d` (780 mutants); existing tests importing the module: `research/tests/test_alert_budget.py`, `research/tests/test_alert_budget_summary.py`.

#### `research.alert_budget.x__counts__mutmut_50`

- Function: `_counts`; outcome: survived; category: **Strong equivalence evidence** (family `f1_guard`).
- Original: `"f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0,`
- Mutated: `"f1": 2 * tp / (2 * tp + fp + fn) if (tp) or True else 0.0,`
- Change: `if tp else 0.0` replaced by `if (tp) or True else 0.0`.
- Why it survived: With tp == 0 the numerator is 0 and, since recall (evaluated earlier in the same literal) already raised when tp + fn == 0, the denominator fp + fn is positive: the value is 0.0 in both forms.
- Observable behavior: The f1 field of a budget cell.
- Downstream consumers: Alert-budget result files.
- Supported inputs and boundaries: Any confusion counts for which the function does not already raise.
- Dependency sensitivity: None.
- Evidence for equivalence: Dictionary literals evaluate in order: the recall line raises ZeroDivisionError when tp + fn == 0 before f1 is reached.
- Evidence against or limits: Reordering of the literal's fields would change this.
- Remaining uncertainty: Depends on the field order.
- Could further testing separate it: No at present.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.alert_budget.x_run_method__mutmut_23`

- Function: `run_method`; outcome: survived; category: **Additional verification required** (family `asarray_float_detector`).
- Original: `scores = result.scores.to_numpy(dtype=float)`
- Mutated: `scores = result.scores.to_numpy(dtype=None)`
- Change: np.asarray / to_numpy of detector output with dtype=None or without dtype.
- Why it survived: Detector scores are float Series, flags are boolean Series; converting a float or boolean array to its own dtype leaves it unchanged.
- Observable behavior: The dtype of scores used for ROC and PR statistics and thresholds; differs only for non-float output.
- Downstream consumers: Alert-budget and score-shift runs.
- Supported inputs and boundaries: Float and boolean detector output.
- Dependency sensitivity: Detector contract (scores are floats).
- Evidence for equivalence: Detectors in the registry return float scores; the existing run tests use float stubs.
- Evidence against or limits: A detector returning integers, objects or missing values would reach the metric functions with a different dtype.
- Remaining uncertainty: Whether every registered detector, including future ones, returns float.
- Could further testing separate it: Yes: a stub detector returning integer or object scores would separate the forms if the contract is to coerce them.
- Recommended next technical action: Technical first: add a stub-based test for non-float scores; if the behavior is deliberately unspecified, owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.alert_budget.x_run_method__mutmut_54`

- Function: `run_method`; outcome: survived; category: **Additional verification required** (family `asarray_float_detector`).
- Original: `row["rule"] = _counts(y, result.flags.to_numpy(dtype=bool))`
- Mutated: `row["rule"] = _counts(y, result.flags.to_numpy(dtype=None))`
- Change: np.asarray / to_numpy of detector output with dtype=None or without dtype.
- Why it survived: Detector scores are float Series, flags are boolean Series; converting a float or boolean array to its own dtype leaves it unchanged.
- Observable behavior: The dtype of scores used for ROC and PR statistics and thresholds; differs only for non-float output.
- Downstream consumers: Alert-budget and score-shift runs.
- Supported inputs and boundaries: Float and boolean detector output.
- Dependency sensitivity: Detector contract (scores are floats).
- Evidence for equivalence: Detectors in the registry return float scores; the existing run tests use float stubs.
- Evidence against or limits: A detector returning integers, objects or missing values would reach the metric functions with a different dtype.
- Remaining uncertainty: Whether every registered detector, including future ones, returns float.
- Could further testing separate it: Yes: a stub detector returning integer or object scores would separate the forms if the contract is to coerce them.
- Recommended next technical action: Technical first: add a stub-based test for non-float scores; if the behavior is deliberately unspecified, owner decision.
- Owner decision status: **undecided** (no record exists).

### `research/score_shift.py`

Binding at build time: the working-tree source equals the digest below.

Source SHA-256 `a96e39bb1b80cbaacd00d31f8986a3f2cda350564d316be002dc589c9d801ef6`; catalog SHA-256 `05a61a82954d6dc47534f6c49b48f613289103a591aeae75e53a0f1455774852` (806 mutants); existing tests importing the module: `research/tests/test_score_shift.py`.

#### `research.score_shift.x_monitor_table__mutmut_39`

- Function: `monitor_table`; outcome: survived; category: **Strong equivalence evidence** (family `nonneg_compare`).
- Original: `"precision": base[key]["precision"] > 0`
- Mutated: `"precision": base[key]["precision"] >= 0`
- Change: base precision > 0 replaced by >= 0 in the precision-collapse flag.
- Why it survived: When the base precision is 0 the second operand is `now < PRECISION_FLOOR * 0`, i.e. `now < 0`, which is false for a precision in [0, 1]; so the flag is false in both forms.
- Observable behavior: The precision_collapse share per scenario.
- Downstream consumers: Score-shift monitor table.
- Supported inputs and boundaries: Precision values in [0, 1].
- Dependency sensitivity: Precision is a rate (non-negative).
- Evidence for equivalence: Arithmetic on the guarded comparison; `_counts` defines precision as a rate with 0.0 when undefined.
- Evidence against or limits: Negative precision input would separate them but is outside the data contract.
- Remaining uncertainty: None under the contract.
- Could further testing separate it: Only with out-of-contract negative precision.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.score_shift.x_monitor_table__mutmut_48`

- Function: `monitor_table`; outcome: survived; category: **Strong equivalence evidence** (family `continue_break_empty`).
- Original: `continue`
- Mutated: `break`
- Change: `continue` replaced by `break` when a scenario has no rows.
- Why it survived: The rows of every scenario come from the same fits, so a scenario has no rows only when there are no fits, and then every scenario is empty.
- Observable behavior: The scenarios present in the monitor table.
- Downstream consumers: Score-shift monitor table.
- Supported inputs and boundaries: Runs with and without fits.
- Dependency sensitivity: None.
- Evidence for equivalence: Code reading of monitor_table(): `rows` depends on `_fits(runs)` and the scenario key; a missing scenario key raises KeyError instead of producing an empty list.
- Evidence against or limits: A scenario that is absent from some fits is a KeyError in both forms, not an empty row list.
- Remaining uncertainty: None identified.
- Could further testing separate it: No.
- Recommended next technical action: Owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.score_shift.x_run_method__mutmut_23`

- Function: `run_method`; outcome: survived; category: **Additional verification required** (family `asarray_float_detector`).
- Original: `scores = np.asarray(detector.score(test), dtype=float)`
- Mutated: `scores = np.asarray(detector.score(test), dtype=None)`
- Change: np.asarray / to_numpy of detector output with dtype=None or without dtype.
- Why it survived: Detector scores are float Series, flags are boolean Series; converting a float or boolean array to its own dtype leaves it unchanged.
- Observable behavior: The dtype of scores used for ROC and PR statistics and thresholds; differs only for non-float output.
- Downstream consumers: Alert-budget and score-shift runs.
- Supported inputs and boundaries: Float and boolean detector output.
- Dependency sensitivity: Detector contract (scores are floats).
- Evidence for equivalence: Detectors in the registry return float scores; the existing run tests use float stubs.
- Evidence against or limits: A detector returning integers, objects or missing values would reach the metric functions with a different dtype.
- Remaining uncertainty: Whether every registered detector, including future ones, returns float.
- Could further testing separate it: Yes: a stub detector returning integer or object scores would separate the forms if the contract is to coerce them.
- Recommended next technical action: Technical first: add a stub-based test for non-float scores; if the behavior is deliberately unspecified, owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.score_shift.x_run_method__mutmut_25`

- Function: `run_method`; outcome: survived; category: **Additional verification required** (family `asarray_float_detector`).
- Original: `scores = np.asarray(detector.score(test), dtype=float)`
- Mutated: `scores = np.asarray(detector.score(test), )`
- Change: np.asarray / to_numpy of detector output with dtype=None or without dtype.
- Why it survived: Detector scores are float Series, flags are boolean Series; converting a float or boolean array to its own dtype leaves it unchanged.
- Observable behavior: The dtype of scores used for ROC and PR statistics and thresholds; differs only for non-float output.
- Downstream consumers: Alert-budget and score-shift runs.
- Supported inputs and boundaries: Float and boolean detector output.
- Dependency sensitivity: Detector contract (scores are floats).
- Evidence for equivalence: Detectors in the registry return float scores; the existing run tests use float stubs.
- Evidence against or limits: A detector returning integers, objects or missing values would reach the metric functions with a different dtype.
- Remaining uncertainty: Whether every registered detector, including future ones, returns float.
- Could further testing separate it: Yes: a stub detector returning integer or object scores would separate the forms if the contract is to coerce them.
- Recommended next technical action: Technical first: add a stub-based test for non-float scores; if the behavior is deliberately unspecified, owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.score_shift.x_run_method__mutmut_39`

- Function: `run_method`; outcome: survived; category: **Additional verification required** (family `asarray_float_detector`).
- Original: `eval_scores = np.asarray(detector.score(moved), dtype=float)`
- Mutated: `eval_scores = np.asarray(detector.score(moved), dtype=None)`
- Change: np.asarray / to_numpy of detector output with dtype=None or without dtype.
- Why it survived: Detector scores are float Series, flags are boolean Series; converting a float or boolean array to its own dtype leaves it unchanged.
- Observable behavior: The dtype of scores used for ROC and PR statistics and thresholds; differs only for non-float output.
- Downstream consumers: Alert-budget and score-shift runs.
- Supported inputs and boundaries: Float and boolean detector output.
- Dependency sensitivity: Detector contract (scores are floats).
- Evidence for equivalence: Detectors in the registry return float scores; the existing run tests use float stubs.
- Evidence against or limits: A detector returning integers, objects or missing values would reach the metric functions with a different dtype.
- Remaining uncertainty: Whether every registered detector, including future ones, returns float.
- Could further testing separate it: Yes: a stub detector returning integer or object scores would separate the forms if the contract is to coerce them.
- Recommended next technical action: Technical first: add a stub-based test for non-float scores; if the behavior is deliberately unspecified, owner decision.
- Owner decision status: **undecided** (no record exists).

#### `research.score_shift.x_run_method__mutmut_41`

- Function: `run_method`; outcome: survived; category: **Additional verification required** (family `asarray_float_detector`).
- Original: `eval_scores = np.asarray(detector.score(moved), dtype=float)`
- Mutated: `eval_scores = np.asarray(detector.score(moved), )`
- Change: np.asarray / to_numpy of detector output with dtype=None or without dtype.
- Why it survived: Detector scores are float Series, flags are boolean Series; converting a float or boolean array to its own dtype leaves it unchanged.
- Observable behavior: The dtype of scores used for ROC and PR statistics and thresholds; differs only for non-float output.
- Downstream consumers: Alert-budget and score-shift runs.
- Supported inputs and boundaries: Float and boolean detector output.
- Dependency sensitivity: Detector contract (scores are floats).
- Evidence for equivalence: Detectors in the registry return float scores; the existing run tests use float stubs.
- Evidence against or limits: A detector returning integers, objects or missing values would reach the metric functions with a different dtype.
- Remaining uncertainty: Whether every registered detector, including future ones, returns float.
- Could further testing separate it: Yes: a stub detector returning integer or object scores would separate the forms if the contract is to coerce them.
- Recommended next technical action: Technical first: add a stub-based test for non-float scores; if the behavior is deliberately unspecified, owner decision.
- Owner decision status: **undecided** (no record exists).

## Decision instructions

The owner decides each mutant individually by editing `verification/mutation_equivalence.json` (version 2) using the existing schema; the file under `docs/thesis-remediation/equivalence/owner_review_candidates_2026-11-12.json` is only the list of proposals and is never read as an approval source. For each decision set `verdict` to `accepted`, `rejected` or `inconclusive`, set `approver` to the owner login, set `decision_date`, and keep `source_sha256`, `catalog_sha256`, `policy_version` and `environment` exactly as in the proposal. A record stays valid only while the module source digest, catalog digest, risk level, policy version, the dependency versions in `environment` and the survival of the mutant all match; a changed source invalidates it. Leaving a candidate without a record keeps it in the denominator, the same as `inconclusive`. I have not prefilled any verdict, date or approver.

## Outstanding work

| Class | Items |
| --- | --- |
| Could still gain a behavioral test | 7 mutants in families `label_cast` (label range at the carrier loader) and `asarray_float_detector` (non-float detector output): `x_load_carrier__mutmut_29`, `x_run_method__mutmut_23`, `x_run_method__mutmut_54`, `x_run_method__mutmut_23`, `x_run_method__mutmut_25`, `x_run_method__mutmut_39`, `x_run_method__mutmut_41` |
| Need more evidence (dependency matrix or wider dtypes) | 17 mutants in the Additional-verification category |
| Await owner judgment | all 43 candidates |
| Timeouts / incomplete | none in the collected runs |
| Modules still below 98 in focused runs | see the score table (raw result column) |
| Missing or stale evidence | 9 L4 modules absent from the 2026-11-07 campaign; 56 campaign modules below 98 (`MUTATION_L4_INVENTORY.md`); the temporal pilot source differs from the revision that produced the archived record |

## Validation of this packet

`tests/test_owner_review_packet.py` checks that every candidate id exists in the collected catalog, that the digests match the current source files and the catalog, that the arithmetic in this document matches the policy function, that no record carries an approver or a date, and that the proposals are never counted by `accepted_equivalents`.

