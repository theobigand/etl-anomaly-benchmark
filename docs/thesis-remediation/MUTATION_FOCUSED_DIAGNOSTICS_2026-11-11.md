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
| `research/normalise.py` | L4 | 175/193 (2026-11-07 campaign) | 188/197 | 95.43 % | below |
| `research/paired_bootstrap.py` | L4 | 77/100 (2026-11-07 campaign) | 94/100 (5 survived, 1 timeout) | 94.00 % | below |

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

The guard was left unchanged on purpose: archived evidence manifests record the SHA-256 of
`research/normalise.py` (for example `verification/evidence/alert_budgets/neural/manifest.json`),
and a change would break that linkage for a fix that only changes an exception type. The current
behaviour is pinned by `test_known_limitation_three_to_five_anomalies_pass_the_guard_but_fail_the_stratified_split`.
Decision for the owner: raise the constant to 6 (or catch the `ValueError`) together with a
regenerated manifest, or keep it and document it.

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
