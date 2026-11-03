# Constructed frozen-partition example

This 12-row fixture illustrates `pool-train-only-v1` at implementation `edc3592`.
It is not a real-pool experiment or evidence of detector ranking. The source,
source-bound positions, result and original run record are retained together.
The target is `anomaly`; retained numerical/categorical features and training-only
statistics appear in `result.json`. Seed: 42. Detectors: Z-score and Isolation
Forest. The record binds runtime versions, code and input/output hashes.

From the repository root, choose a new output path:

```bash
python -m research.pool_train_only \
  --csv docs/thesis-remediation/evidence/pool-train-only-example-2026-11-03/raw.csv \
  --partitions docs/thesis-remediation/evidence/pool-train-only-example-2026-11-03/partitions.json \
  --label-column anomaly --detectors zscore isolation_forest \
  --output /tmp/pool-train-only-example-result.json
```

Outputs are intentionally not overwritten. The archived record has
`worktree_dirty: true`; it was produced after the implementation commit with
documentation/evidence edits present. Its research-source hashes match committed
implementation bytes. The referenced existing environment lock is retained as
recorded; observed package versions are also listed, without a claim of a newly
captured complete environment lock or cross-platform identical floating-point
results. No archived record is edited after generation.
