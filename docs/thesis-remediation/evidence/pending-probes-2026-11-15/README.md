# Pending behavioral probes

These temporary pytest probes ran on the local macOS mutation environment with
unmodified production source at `db27f56af48eab431e965cabb74ab5ea3d96af54`.
The three tests pass on the original. `pool-only` failed on
`research.pool_chrono.x_main__mutmut_93`; `multischema-index` failed on
`research.multi_schema.x_make__mutmut_{306,309,311}`; `window-nullable` failed
on `etl_benchmark.quality.window_drift.x__numeric__mutmut_18`. The compressed
logs preserve these direct RED/GREEN checks. They have not yet been integrated
into the repository test suite or rerun through the native mutation engine;
none is counted as a verified kill. Source identities must be rechecked before
resuming. Do not mix these probes with the historical campaign.

The canonical test suite and verifier gate for `db27f56` are in progress in
`/tmp/etl-canonical-db27f56.log` and `/tmp/etl-verify-db27f56.log`. Hosted
LSTM diagnostic run 43718624552 is in progress. Its workflow concurrency can
cancel the diagnostic on a subsequent PR push; check its status before pushing.

A fourth direct probe, `temporal-ties.py.txt`, confirms that equal timestamps
retain arrival order in the original chronological split, while
`research.temporal_decision.x_run_frame__mutmut_11` and `_13` alter partition
class counts. It passed on the original and failed on both generated mutants.
It too needs an integrated regression and native engine verdict before counting.

A fifth direct probe, `credit-ties.py.txt`, verifies arrival order for equal
credit-card timestamps. It passed on the original and failed on
`research.temporal_decision.x_credit_card__mutmut_6` and `_8`. Integration and
native verdicts remain pending.

Update: the five regressions were integrated and all nine listed mutants were
verified killed by the native engine; see `../../NINE_BEHAVIORAL_PROBES_2026-11-15.md`.
The earlier pending statements describe the state before that run. The bank-case
probe is a separate conditional proposal, with no owner approval.

`ml-defaults.py.txt` is an exploratory probe only. It compares SciPy's explicit
`axis=0` with the default and Python's two NaN spellings in two installed
environments. It has not yet run the corresponding generated class methods or
produced an owner proposal. The SciPy 1.11.4 documentation specifies axis 0 as
the default: https://docs.scipy.org/doc/scipy-1.11.4/reference/generated/scipy.stats.skew.html.

The `dataloader-defaults` and `dif-defaults-mutants` probes compare the three
DIF loader-default mutants (shuffle None, omitted shuffle, omitted drop-last)
against the original in local torch 2.14.1 and 2.15.0 environments, including
empty, singleton, complete and incomplete batches and a second scoring call.
The generated source is preserved in `torch-models-generated.py.gz`. These
are still pending triage while the full checks run; they have not been approved
and have not been remeasured as a full unit or on Linux.
