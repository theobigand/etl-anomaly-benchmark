# Batch-level ETL pipeline fault detection: protocol (mandatory study, tasks T381-T387 and T416-T430)

Written and archived before any result of this study exists. It is a new study: the row-level
protocols (`typed_injection.md`, `typed_mixed.md`, `labelled_pool.md`) are unchanged and are never
pooled with it.

## Why this study is mandatory

The thesis is about ETL pipelines. In a pipeline the unit that fails is the load, not the row: a
batch arrives half-empty, twice, stale, with a column missing, in other units, or with its
dependencies broken. Row-level outlier detection and injected row faults do not measure that, and
the 100 labelled problems use minority-class proxies. A claim about ETL pipelines needs evidence at
the unit where pipelines fail. Without it, the work claims only "data-quality faults on tables".

## Question

For which pipeline fault mechanisms, and at which alert budget, does a learned detector on batch
profiles find faulty loads that a competent constraint-based rule set misses, and at what cost in
false alerts?

## Unit and sources

Unit of detection: the batch, a fixed number of consecutive rows of a real timestamped table
replayed in time order as successive loads. Unit of inference: the independent source (the table),
never the batch, the seed or the injected variant. Plumbing pilot: the eight real regularly sampled
UCI series of `chrono_injected.py` that meet its eligibility rule (same cleaning, sorting by the
parsed timestamp, trend columns removed). Eight sources are descriptive only; no ranking claim is
made on them. The sized study (variance pilot, then confirmatory run) is specified in
`docs/thesis-remediation/13-pipeline-level-study.md` and its size is set by the pilot variance, not
fixed here.

## Batches and partitions

Batch size `k = max(24, n // 100)` rows (so that a source has about 100 batches), remainder
dropped. Reference: first 40 % of the batches, fit only. Validation: next 20 %, clean, used only to
set the label-free alert threshold. Test: last 40 %. No test fault label is used to choose
anything.

## Fault operators (eight mechanisms, three severities each)

Each operator changes one test batch and records the mechanism, the severity and the columns it
touched. A test batch carries at most one fault.

| Mechanism | Pipeline meaning | Severity (low, medium, high) |
|---|---|---|
| `partial_load` | incomplete load | keep 70 %, 40 %, 10 % of the rows |
| `duplicate_load` | load applied twice | 20 %, 50 %, 100 % of the rows repeated |
| `stale_batch` | freshness failure: the batch repeats an older one | replaced by the batch 1, 3, 10 loads back, timestamps unchanged |
| `null_spike` | upstream nulls | one column, 10 %, 30 %, 100 % of values missing |
| `schema_drop` | schema change: columns missing | 1, 2, one third of the columns absent |
| `unit_change` | wrong units or conversion | one column scaled by 2, 10, 1000 |
| `distribution_shift` | upstream distribution change | one column shifted by 0.5, 1, 2 reference standard deviations |
| `silent_corruption` | dependencies broken, marginals kept | values of 1 to 3 columns permuted within the batch for 20 %, 50 %, 100 % of rows |

In each evaluation 30 % of the test batches, chosen at random with the injection seed, carry the
same mechanism and severity; the others are clean. Injection seeds: 42, 1, 2, 3, 4.

## Batch profile

For every batch, with every statistic read against the reference batches only: row count relative
to the reference median, share of exact duplicate rows, share of rows identical to the previous
batch, timestamp lag between this batch and the previous one relative to the reference lag, the
number of absent columns, and per column the null share, mean, standard deviation and the 5th, 50th
and 95th percentiles, standardised by the reference batches, plus the distance of the batch
correlation matrix to the reference one. A missing column keeps null features.

## Detectors

All are label-free and fitted on the reference batches.

- `constraint_rules`: constraints learned from the reference batches in the manner of declarative
  data-validation tools (schema present, null share, row-count range, freshness lag, duplicate
  share, column means within the range of reference batch means). The score is the largest
  normalised excess over a constraint; a score above one is a violation. No tuning on any label.
- `volume_freshness`: row count and freshness lag only, the minimal operational baseline.
- `distribution_distance`: per column Kolmogorov-Smirnov distance of the batch to the pooled
  reference, standardised by the distances of the reference batches.
- Learned detectors of the registry on the profile table: `isolation_forest`, `ecod`, `copod`,
  `hbos`, `pca`, `knn`, `lof`, default settings, contamination 0.05. Neural detectors are not run
  on fewer than 200 reference batches and are recorded as not applicable, never as a low score.
- `random`: a random scorer, the floor that every detector must beat.

## Operating point and metrics

Threshold per detector: the 95th percentile of its scores on the clean validation batches (an alert
budget of 5 % of clean batches, label-free). Per source, mechanism, severity and detector: ROC-AUC
and average precision over the test batches, recall at the threshold, and the false-alert rate on
clean test batches at the same threshold. Averages are over injection seeds first, then over
severities where a mechanism is summarised.

## Sensitivity arm

A contaminated reference: 5 % of the reference batches carry a random fault of any mechanism, not
labelled to the detectors, as in a production history that already holds faults. Reported next to
the clean-reference result.

## Hypotheses (exploratory on the pilot, eight sources)

- B1: `constraint_rules` reaches a recall of at least 0.9 at the 5 % alert budget on `partial_load`,
  `duplicate_load`, `stale_batch`, `null_spike` and `schema_drop` at medium and high severity.
- B2: `constraint_rules` finds `silent_corruption` and low-severity `distribution_shift` less often
  than the best learned detector (recall difference of at least 0.2).
- B3: no single family has the best median recall for every mechanism.
- B4: with a contaminated reference, recall falls for every detector family; the order is reported.

A result that contradicts a hypothesis is reported as it is. A non-significant difference is not
read as equivalence.

## Limits announced

Faults are injected into real tables; they are artificial and say what a detector can do against
that fault, not that it finds real incidents. Real incident evidence is a separate tier (task
T426). The pilot has eight sources from one family of tables (regularly sampled series), so it is
descriptive. Batches within a source are autocorrelated and are not independent units.
