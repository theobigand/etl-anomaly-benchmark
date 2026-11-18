# Live continuation at `eb1d679`

The verified checkpoint was committed and pushed as
`eb1d67915b639bd0ecadf1a674ac49b611dffb1e`. PR #117 remains open and draft.
The default canonical Conda pytest suite exited 0 with 4,056 passed and 23
browser tests deselected on the uncommitted predecessor worktree; after the
checkout moved, 141 affected tests passed with `PYTHONPATH=src:.`. See
`L4_CAMPAIGN_REPORT_2026-11-13.md` for logs and limitations. The moved checkout
has an old editable-install pointer; do not rebuild or relocate the live cache.

The fresh Linux diagnostic run is
https://github.com/theobigand/etl-anomaly-benchmark/actions/runs/43830854251 .
It was dispatched with `diagnostic_module=src/etl_benchmark/quality/ml.py`
and `fresh_mutants=true` at this exact head. The regenerated 45-shard plan in
`evidence/continuation-2026-11-15/shard-plan-eb1d679.json` assigns that unit to
shard 40 with `experiments/generate_synthetic.py` and
`experiments/run_severity.py`. The engine was running when last checked; do not
claim mutant verdicts until it and evidence upload complete. Workflow dispatch
uses the branch concurrency group and can cancel another run on the same ref;
do not start another diagnostic until this one finishes and evidence is saved.
The ordinary exact-head CI run is 43830818155. Its `test`, `faults`, and `slides` jobs all passed. The pull-request
release and mutation workflows were skipped.

The exact current source/catalog membership check in
`evidence/continuation-2026-11-15/catalog-membership-eb1d679.json` found all
162 identities in the current generated metadata and spans across 16 units;
this is not proof of their verdicts. Both files and this continuation are
uncommitted to avoid changing the tested branch during the running diagnostic.
Existing untracked diagnostic extracts and Cardio directories are unrelated
preserved state: do not remove or stage them indiscriminately.

The user has not authorized further independent model review or owner
exclusion approval. Do not change risk thresholds, scope, owner verdicts or the
release gate. After the shard completes, inspect its full manifest, execution
proof and native verdicts; remeasure the other affected units and rerun the
LSTM scoped validator on the then-current head. The complete 100-unit campaign,
full input-provenance binding, current-claims integrity, owner decisions,
independent review, official DEEP/release and exact-final-head CI are still
required. `ap status` reports task `t-d2faa05a` as active.

CI artifact ZIPs are saved and hash-verified under `evidence/ci-43830818155/` with exact FAST and verifier counts in its README. They are uncommitted along with this live checkpoint to avoid moving the branch during the diagnostic.
