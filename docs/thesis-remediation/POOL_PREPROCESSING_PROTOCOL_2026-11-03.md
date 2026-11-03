# Frozen-partition train-only preparation — 2026-11-03

Protocol identifier: `pool-train-only-v1`. Scope: #89 T062–T064, coordinated with
#90 T089 and #100 T351. Status: implementation and constructed acceptance checks;
not a confirmatory replay of the historical pool and not a replacement of its results.

The historical `normalise.clean`/`split` protocol and its archives remain unchanged.
Its full-table feature selection, vocabulary and contradictory-label row filtering
are documented limitations. A dated exploratory alternative consumes explicit frozen
row positions; it never generates or silently changes the historical partitions.

## Fixed behavior before implementation

- Input is a feature table and nonempty train/validation/test lists of zero-based row
  positions. Every row occurs exactly once. Reject non-integer, repeated, overlapping,
  incomplete and out-of-range assignments; preserve supplied order and row population.
- Reject identical feature rows across different partitions, irrespective of their
  labels. Within-partition duplicates are retained; no label-based row removal occurs.
  This validates a supplied assignment rather than making a split from future labels.
- Fit column decisions only on training rows: omit columns above 50% missingness or
  with at most one observed value. Infer numeric representation from training values
  only; booleans are categorical. Categorical columns with more than 20 observed
  training values are omitted. Record all retained, omitted and encoded columns.
- Fit numeric medians on training values. Fit the categorical vocabulary on training
  strings (missing values are distinct), with unseen categories encoded as all-zero
  blocks before scaling. Reuse the fitted training mean/scale for every partition.
- No target or labels enter preparation. The consumer removes the declared CSV target;
  training prevalence may calibrate flags as in the historical label-informed baseline.
  Evaluation labels affect metrics and recorded prevalence only, never fitted state,
  thresholds, schema, partitions or scores. Undefined binary metric cases are rejected.
- Strictly reject unusable schemas, nonfinite numeric inputs or transformed outputs.
  Never drop evaluation rows, invent categories from them or silently refit on them.
- The explicit consumer uses existing detector builders, fit caps, skip rules, pipeline
  and metrics. It records raw test scores/flags and failures. CSV loading preserves
  strings so type inference cannot learn from evaluation rows during parsing.
- CLI input requires a source-SHA-bound partition manifest with schema version 1,
  row count, seed and the three position lists. Output has a new protocol tag and
  separate run record, source hashes (including research code), versions, input hashes,
  fitted-column report and unchanged row positions. Refuse overwriting existing output.

## Acceptance and scientific boundary

Constructed tests perturb evaluation categories, missingness, extremes and labels while
holding training rows and assignments fixed. The fitted schema/statistics, transformed
training rows and detector scores must stay identical. Preserve the six-row legacy
counterexample as a negative control; do not rewrite it as a corrected historical run.
Test malformed assignments, unseen categories, constant/all-missing columns, cross-fold
duplicates, label isolation, source binding and an end-to-end CLI artifact.

The archived pool results inspect seeds but do not export row-position manifests.
Recovering/binding suitable raw populations and assignments and replaying applicable
studies remain prerequisites for T062/T063 completion. No new real-pool held-out results
will be inspected in this implementation unit; no original hypothesis is changed.
New-module coverage and constructed fault checks are separate from the existing core
verification scope. Coverage or green CI does not establish corrected scientific claims.

## Explicit use

Run from the repository root in the existing environment; no dependency upgrade is
required. The source CSV must already contain one binary target column. Supply an
independently fixed assignment for that exact file, for example:

```json
{
  "schema_version": 1,
  "input_sha256": "<full SHA-256 of the source CSV>",
  "row_count": 12,
  "seed": 42,
  "partitions": {
    "train": [0, 1, 2, 3, 4, 5, 6, 7],
    "validation": [8, 9],
    "test": [10, 11]
  }
}
```

These positions illustrate the format, not a historical assignment. Both classes
must occur in each partition. Do not derive a new assignment after inspecting
held-out outcomes or claim it reconstructs an archived split.

```bash
python -m research.pool_train_only --csv /path/table.csv \
  --partitions /path/partitions.json --label-column anomaly \
  --output experiments/results/train_only_example.json --detectors zscore isolation_forest
make verify-preprocessing
```

The result and adjacent `.record.json` retain the supplied positions, training
calibration, fitted decisions, raw test scores/flags, metric results, detector
failures/skips, input/output hashes, partition-file hash and research-source hashes.
The existing provenance record also captures core fingerprint, revision and package
versions. The research-source hashes are additional bindings because the historical
core fingerprint does not cover `research/`. Validation features are transformed
without fitting or threshold selection; this first consumer does not tune models.
Calibration remains label-informed through training prevalence and is not a
label-free deployment threshold.

The CLI rejects duplicate CSV headers before parsing, missing/invalid targets,
unusable features and invalid source assignments. It refuses occupied result or
record paths. A detector exception is preserved in the result and causes failure;
an entirely skipped selection also exits unsuccessfully. A successful constructed
run demonstrates the contract, not corrected real-pool performance.
