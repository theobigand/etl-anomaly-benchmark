# Design decision of 2026-11-21: ETL pipeline evidence is mandatory

## Decision

A study at the unit where ETL pipelines fail, the load (batch), is part of the required scope.
Row-level outlier detection and the minority-class proxy labels of the labelled pool stay as
sensitivity and breadth evidence, but they do not support a claim about ETL pipelines by themselves.

## What changed in the plan

- Tasks T381-T387 move from the optional extension list (issue #102) to a mandatory P0 study
  (`13-pipeline-level-study.md`, new issue). Their identifiers are unchanged.
- New tasks T416-T430 cover the batch protocol, operators, baselines, pilots, the real-incident
  search, the claim ladder, the realism check and the manuscript.
- The protocol is `verification/pipeline_batch_faults.md`, written before any result.

## Claim ladder

| Evidence | Allowed wording |
|---|---|
| Real, documented ETL incidents from independent organisations | "anomaly detection in ETL pipelines" |
| Controlled batch-level faults replayed through real tables, no real incidents | "controlled batch-level data-quality faults in ETL-style loads" |
| Row-level outliers, proxy labels | "outlier detection on tables"; sensitivity evidence only |

## Principles adopted from the design review

1. The independent source is the unit of inference; batches, seeds and injected variants are not.
2. Row, window and batch detection are separate estimands and are never pooled.
3. A fair rule baseline is part of every rules-versus-learning comparison; weak rules produce
   spurious wins for learned detectors.
4. Thresholds are label-free (alert budget); a reference history that already contains faults is a
   reported sensitivity arm.
5. The realism of injected faults can be checked against natural labels only for statistical and
   temporal mechanisms; referential, unit, schema and load faults cannot be validated that way and
   are reported as controlled faults.

## Sample size

Sizes are conditional on the between-source standard deviation of paired differences, which is not
known for batch-level faults. With a two-sided paired comparison, 80 % power and alpha 0.05, the
sources needed are about 7.85 (sigma / delta)^2 (before multiplicity and clustering corrections):
87 sources for sigma 0.10 and delta 0.03, 71 for sigma 0.15 and delta 0.05. The variance pilot of
T424 replaces the assumed sigma; the final number is fixed in a dated addendum before the
confirmatory run. The target planning range from the design review is about 120 to 300 independent
source families, spread over structural strata (flat tabular, transactional and categorical, time
series, logs and event sequences, relational, nested), and is not a requirement until the pilot
fixes it.

## Not adopted yet

The review's full 18-detector core, 15-type fault taxonomy and sealed hold-out set are proposals
for the confirmatory stage. They are revisited after the variance pilot.
