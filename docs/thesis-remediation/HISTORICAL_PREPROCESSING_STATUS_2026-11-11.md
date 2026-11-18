# Historical preprocessing and partition status (T062, T063, T089) - 2026-11-11

Nothing here changes a historical protocol or restamps an archived result. T062 and T063 stay open.

## 1. Historical results whose limitation must be disclosed (done, not a closure)

The archived pool studies (100 labelled problems: 36 ADBench, 64 UCI; five seeds; 17 detectors) use
`research.normalise.clean` before the split. It filters constant, mostly-missing and high-cardinality columns,
encodes categories, removes duplicates and drops rows with conflicting labels over the whole table. Median
imputation and standardization are fitted on the training partition only (`normalise.split`), but the preceding
decisions can read evaluation values and, for conflicting duplicates, labels. Constructed regressions show the
information access (a column count changes when only evaluation categories change; a duplicate's label can
remove a reference row). The effect on dataset-level AP has not been measured. The manuscript (Methods, Threats,
Conclusion) and slides 8B and 20 already state that the pool results are descriptive and need train-only
revalidation; this pass added no claim to the contrary and kept those statements.

## 2. Corrected implementation, verified prospectively

`research.pool_train_only` with `research.pool_preprocessing.prepare_frozen` consumes source-bound frozen
partitions, fits column selection, vocabulary, medians and scale on training rows, rejects cross-partition
duplicates and excludes labels from preparation. It is verified by constructed negative controls and defect
injection (T064, T351, `POOL_PREPROCESSING_VALIDATION_2026-11-03.md`). Partitions were recomputed and
replay-validated against all 500 archived Z-score problem-seed results (T088, T089, `PARTITION_RECOVERY_2026-11-08.md`).
This verifies the corrected path, not the historical numbers.

## 3. Work that genuinely requires recomputation (not done here)

To close T062 and T063 for the pool studies, the studies must be replayed on the train-only path over the frozen
partitions: raw (uncleaned) tables for the 100 problems, `prepare_frozen` per seed, the same detectors and metrics,
and a paired comparison with the archived AP per problem and seed, with source-clustered uncertainty. The 64 UCI
problems are where cleaning decisions bite; the 36 ADBench files are numeric but can still lose or merge rows.
Cost: the classical detectors are about 3.3 CPU-hours at archived timings; the neural ones about 31 CPU-hours, and
should use the single-thread configuration proposed in `NEURAL_REPRODUCIBILITY_2026-11-11.md`. This is a new
experiment with its own protocol note, and its numbers would replace nothing historical.

## Why T062 and T063 are not closed

A documented limitation and a verified corrected path do not show that the historical experiments were fitted on
training data only; they show the opposite for the pre-split steps. The tasks need the replay in section 3, or an
explicit decision by the owner to accept the pool results as permanently descriptive, which would be a change of
the task definition and is not taken here.
