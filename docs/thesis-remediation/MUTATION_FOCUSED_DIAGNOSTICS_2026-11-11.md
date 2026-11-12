# Focused mutation diagnostics, 2026-11-11

Status: measured diagnostic. Not a certification, not release evidence. The release gate stays
fail-closed and no threshold, module level or exclusion was changed.

## What was run

Local, per-module `mutmut run "research.<module>.*"` on macOS in the clean venv
(`~/.cache/etl-mutation-venv`, mutmut 3.8.0, pytest 9.1.1) with
`OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`. Without that variable the forked workers abort with
exit code -6 on macOS. The test selection is the one in `pyproject.toml`. Scores are raw
(`killed / eligible`): no mutant is counted as an accepted equivalence, and no new equivalence
approval was requested or invented. The five research modules added after the 2026-11-07 campaign
were not part of it, so their "before" figure is the first focused run of this session.

## Result per module

| Module | Level | Before | After | Raw after | Against L4 98 % |
| --- | --- | --- | --- | --- | --- |
| `research/pool_check.py` | L4 | 118/180 | 178/180 | 98.89 % | at or above |
| `research/alert_budget.py` | L4 | 427/780 (279 mutants had no test) | 766/780 | 98.21 % | at or above |
| `research/alert_budget_summary.py` | L4 | 0/123 (no test mapped) | 123/123 | 100 % | at or above |
| `research/matched_alert.py` | L4 | 247/322 (35 no test) | 317/322 | 98.45 % | at or above |
| `research/prevalence_shift.py` | L4 | 265/369 (61 no test) | 363/369 | 98.37 % | at or above |
| `research/score_shift.py` | L4 | 492/806 (244 no test) | 795/806 | 98.64 % | at or above |
| `research/source_clustered.py` | L4 | 286/337 | 333/337 | 98.81 % | at or above |
| `research/normalise.py` | L4 | 175/193 (2026-11-07 campaign) | 191/197 (2026-11-12) | 96.95 % | below |
| `research/paired_bootstrap.py` | L4 | 77/100 (2026-11-07 campaign) | 100/100 (2026-11-12) | 100 % | at or above |

"At or above" refers to the raw focused score of that module only. It does not certify the
module under the policy, which also requires a full-campaign record.

## What the new tests protect

- `pool_check`: manifest fields for ADBench sets, the retry schedule (four attempts, pauses of 2,
  4 and 8 seconds, final transport error propagated), no retry for a refused host, the 0.3 s pause
  per entry, exit code only 0 when every entry is `ok`, the written file format.
- `alert_budget`: precision, recall, F1, FPR and alert-rate arithmetic on a hand-computed
  confusion matrix; a score equal to the training threshold is not an alert; the exact
  `1/budget` training-row boundary; infeasible budgets keep their reason; failures and skips are
  recorded per method and never stop later detectors; checkpoint naming; the job and the command
  line (previously untested), including `--resume`, `--only`, `--cells`, worker count.
- `alert_budget_summary`: every denominator in the table header and one exact row per detector
  and budget (previously untested).
- `matched_alert`: tolerance edge, tie-break between equally close budget cells, the exact
  count of each exclusion reason accumulated over problems, that exactly three matched seeds are
  enough, that bootstrap input is one cluster per original source with the requested draws.
- `prevalence_shift`: reweighting formulas, one held-out positive or negative is enough, the
  ten-source boundary, whole-source resampling and draw forwarding.
- `score_shift`: exact transforms, seeded noise, monitor limits and band edges, stratification
  of false alarms by expected alert count, job accounting and the command line.
- `source_clustered`: the bootstrap is compared with an independent derivation of its
  definition (seed, resampling, 95 % interval, two-sided p including the zero boundary), the
  `by_problem`, `by_source` and `without_overlap` calls, and the overlap count.
- `normalise`: stratified validation and test shares for every seed, standardisation of all three
  splits with the training statistics, constant training columns.
- `paired_bootstrap`: the interval compared with an independent derivation, UTC handling of naive
  timestamps, blocks before 1970.

Each new test was checked against the real implementation and against the mutants it targets
through the mutation run above, not by construction.

## Remaining survivors (not approved as equivalent)

Candidates that look behaviourally inert and still need an owner decision before they can be
excluded: `dtype=` coercions on arrays that are already float; `zip(..., strict=)` on lists of
equal length; `flush=` on `print`; argparse `default=` of `--methods` where every value other than
`"deep"` selects the classical family; `type=Path` on `--output` because `atomic_path` accepts a
string; column labels in `normalise.clean`, which returns arrays and not frames; `or True` after an
empty guard whose body is also safe on an empty input. They stay in the denominator.

## Finding: the minimum anomaly count is too low for the split

`research/normalise.py` sets `MIN_CLASS_COUNT = 3` with the comment that train, validation and
test each need one anomaly. A 70/15/15 stratified split needs at least six: with 3, 4 or 5
anomalies the second `train_test_split` raises scikit-learn's `ValueError`, not `NormaliseError`.
`research/build_pool.py` catches only `NormaliseError` to record an exclusion, so such a set would
stop the build instead of being excluded with a reason. No set in the archived pool has this
property, so no result is affected, and the failure is closed, not silent.

Update 2026-11-12: the guard is now `MIN_CLASS_COUNT = 6` and refuses 3 to 5 of either class with
`NormaliseError`. Evidence for six: over classes of 6 to 13 in sets of 12 to 199 rows, 10 seeds and both
class orientations, the 70/15/15 split never failed; with 3 to 5 it failed for most sizes. All 100 labelled
problems of the archived pool have a scarcer class of at least 6 rows after cleaning (smallest: Lymphography,
6), so none would have been refused and no archived result is affected. Archived manifests keep the SHA-256
of the source that produced them (guard 3); they are not restamped, and no historical result is described as
produced under the corrected guard. `test_fewer_than_six_of_either_class_is_refused_by_the_guard_not_by_scikit_learn`
replaces the test that pinned the old behaviour.

## Remaining modules

Taken from the 2026-11-07 native campaign (`risk-native-campaign-2026-11-07.json`, revision
`c8e3917`, 18,400 of 28,107 L4 mutants killed, 65.46 %), which is not re-measured here:

- 32 modules were confirmed below their threshold. The largest absolute gaps are
  `verification/real_preflight.py` (247 survivors), `verification/reproduce.py` (195),
  `verification/mutation_cache.py` (163), `verification/scaling.py` (124, L3),
  `research/typed_summary.py` (121), `research/typed_figures.py` (107),
  `verification/lock_environment.py` (99) and `research/pool_train_only.py` (98; the memory of
  the later contract tests records 325/332, so this figure is stale).
- 30 modules were incomplete because of mutants with no test (for example
  `research/paper_tables.py`, `research/pool_extension_paper.py`, `research/temporal_pilot.py`,
  `verification/claims.py`) or segfaults in native code (`verification/real_acquire.py`).
- Modules with a valid focused PASS from earlier sessions are not changed by this note: the
  focused LSTM diagnostic (raw 368/377 = 97.61 %, adjusted 368/373 = 98.66 % with four
  owner-accepted equivalences, five inconclusive mutants still eligible, no timeout).

## Not done

No full DEEP or hosted campaign was started. No result in this note changes the release verdict,
which remains FAIL until a complete campaign meets every level threshold.


## Update 2026-11-12: normalise and paired_bootstrap

Focused `mutmut run "research.<module>.*"`, raw counts, source SHA-256 of `normalise.py` 5ba131d1... and of
`paired_bootstrap.py` 87eed95e....

`paired_bootstrap`: 100/100. The five survivors and the timeout of 2026-11-11 are killed by two behaviour
tests: a missing score (in either scorer) is refused with `ValueError`, and a missing timestamp is refused
(otherwise its row would silently belong to no block and leave every resample).

`normalise`: 191/197 = 96.95 %, still below the 98 % bar. Three survivors were killed by tests that a
feature matrix of objects with `None` is read as missing values, that a non-numeric matrix is refused with
`ValueError`, and that a missing and an infinite value count as the same row in `clean` (pinned as a known
limitation, not endorsed). Six survivors remain. They are equivalence candidates, kept eligible, no approval
requested or implied; the owner decides:

| Mutant | Change | Why it looks inert |
| --- | --- | --- |
| `x_clean__mutmut_34` | `.rename(name)` becomes `.rename(None)` | column names never reach the returned array or the report |
| `x_clean__mutmut_35` | `.astype(float)` becomes `.astype(None)` | pandas converts every numeric dtype to float64 either way (checked for int64, uint8, float32, bool, Int64) |
| `x_clean__mutmut_45`, `_48`, `_51` | dummy-column prefix removed or `None` | only the dummy column labels change |
| `x_clean__mutmut_64` | `index=False` becomes `index=None` | both falsy in `hash_pandas_object` |

Not claimed: module compliance, or any change to the release verdict. `normalise` stays below the bar unless
three of the six are accepted as equivalent (194/197 would pass).

### build_pool (2026-11-12)

`research/build_pool.py` (SHA-256 eefa0438...): 169/172 = 98.26 % raw focused (the 2026-11-07 campaign had 57/172;
86 `main` mutants had no test). New `research/tests/test_build_pool.py` pins the recorded fields, the carrier and
label refusals with their reasons, the skipped-detector rule, the fixed eligibility seed, the failure bookkeeping,
the pauses and the required arguments. Three survivors remain, all equivalence candidates kept eligible, no approval
requested: `x_pool_row__mutmut_38` (the carrier is cleaned with an all-ones instead of an all-zeros label vector; a
constant label never creates a conflict), `x_main__mutmut_27` and `_30` (`--output` read as a string instead of a
`Path`; `atomic_path` converts it).

### load and quality.base (2026-11-12)

`src/etl_benchmark/load.py`: 13/14 = 92.86 % (unchanged from the campaign; the survivor `x_write_csv__mutmut_11`,
`index=False` to `index=None`, writes the same file because `None` is falsy). `src/etl_benchmark/quality/base.py`:
30/31 = 96.77 %, up from 30/31 at the campaign only after a new test (nullable integer features with missing values
are accepted as numeric) killed `x_numeric_features__mutmut_16`; the survivor `Detector.score` `astype(float)` to
`astype(None)` yields float64 either way. Both survivors are equivalence candidates kept eligible, no approval
requested. Neither module reaches 98 % unless the owner accepts them: with the candidate removed they would be 13/13
and 30/30.

### Typed injection and temporal modules (2026-11-12)

Raw focused scores after new contract tests (`research/tests/test_typed_masking.py`, `test_typed_run.py`,
`test_pool_typed.py`, `test_labelled_contracts.py`, `tests/test_temporal_pilot_contracts.py`):

| Module | Killed / total | Raw | Campaign 2026-11-07 |
| --- | --- | --- | --- |
| `research/typed_masking.py` | 132/132 | 100 % | 27/132 |
| `research/pool_typed.py` | 517/525 | 98.48 % | 26/525 |
| `research/labelled_benchmark.py` | 471/475 | 99.16 % | 112/475 |
| `research/typed_run.py` | 342/351 | 97.44 % | 27/351 |
| `research/temporal_pilot.py` | 542/586 | 92.49 % | 20/586 |

The tests derive expected values independently (a z-score and a percentile bootstrap recomputed in the test),
check the exact arguments each stubbed call receives (fitted on the train part, scored on the test part, fixed
seeds), the recorded fields and failure reasons, file names (case-sensitive), the sorted order of outputs and the
command lines.

Survivors, kept eligible, no approval requested. Most are equivalence candidates of five kinds: `groupby(sort=None)`
for `sort=False` (same order); `astype(None)` for `astype(int)` or `astype(float)` on already numeric data;
`utc=True` removed where the column is already timezone-aware; argparse defaults that coincide with the
fallback (`--methods` default `None` for `"classical"`); and log-message wording in `temporal_pilot`. The
remaining `temporal_pilot` survivors (44) are mostly `features` column-name and `main`/`run` argument mutants not yet
pinned; the module is below the bar and stays a priority.

Finding, source not changed: `temporal_pilot.to_timestamps` refuses NaN, negative and non-numeric elapsed times but
not an infinite one, although its message says "finite". The module hash is bound to the archived pilot record
(`tests/test_temporal_pilot.py`), so a fix needs a new record; no historical result is affected because the file has
finite times.

Practical trap: after adding a test file, delete `mutants/mutmut-stats.json` before a focused run; otherwise mutmut
maps no test to functions that only the new file exercises and reports them as `no tests`.
