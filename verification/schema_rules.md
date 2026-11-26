# Schema-rule baseline on the mixed-schema faults: protocol (follow-up of M2, issues #77, #95)

Written and archived before any result of this baseline exists. The mixed-schema protocol
(`typed_mixed.md`) and its archived results, including its hypothesis M2, stay unchanged. This is a
separate, explicitly documented follow-up experiment, not a redefinition of M2.

## Why

M2 expected rule detectors to miss categorical faults because they "read no categorical column".
That premise was inaccurate: the registry rule detectors (z-score, IQR, Great Expectations) read the
encoded columns, so they are not blind to categories. Their rules are still not domain constraints:
they test numeric dispersion, not allowed values, missing cells, impossible signs or valid
combinations. This follow-up gives the rule family a baseline that can express such constraints, so
that "rules versus models" is not decided by a weak rule set.

## The baseline

`schema_rules`: constraints learned from the training partition only, from the raw columns before
any encoding, with no label and no fault type. A row is flagged when it violates at least one.

- Domain: a `cat` value seen in fewer than two training rows (the encoder's definition of unseen) is
  outside the allowed set.
- Missing: a cell is missing in a column whose training missing share is at most 5 % (the share
  above which the carrier drops a column; the injected missing cells of the training partition
  would otherwise switch the rule off).
- Range: a `num` value outside Q1 - 3 IQR and Q3 + 3 IQR of the training column (far-out fences).
- Sign: a negative `num` value in a column whose training values are all non-negative.
- Combination: for ordered pairs of `cat` columns (a, b) where every level of a with at least five
  training rows maps to one level of b for at least 99 % of its rows, a row whose b differs from
  the dominant level of its a is a violation.

Thresholds are fixed here and are not tuned. Training rows hold the injected faults of their
partition, as for every detector of the study (contamination, no clean-only fit); this lowers the
power of the combination and domain rules and is reported, not corrected.

## Design

Same tables, seeds, injected layouts, partitions and test rows as `typed_mixed.py`: the baseline is
evaluated inside the same `evaluate_seed` layout, so its recall per fault type and false-positive
rate are paired with the 17 archived detectors and the duplicate transform. The share of detections
by each constraint is recorded for interpretation.

## Hypotheses

- S1: on `invalid_code` the baseline has a pooled recall of at least 0.9 in at least 80 % of the
  tables that support the type (an invalid code is outside the domain by construction).
- S2: its false-positive rate on clean test rows is at most 0.05 in at least 80 % of the tables.
- S3: on `cross_column_swap` of two `cat` columns its recall is at least that of the best of the 17
  archived detectors in at least half of the tables that support it.
- S4: on the numeric faults (`univariate_outlier`, `multivariate_outlier`, `invalid_format`) it
  does not exceed the best archived detector (it has no density model); reported per type.

Comparisons are per table and per type, the table being the unit, with the median paired
difference and a bootstrap interval over source groups. No equivalence is claimed from a
non-significant difference. A result that contradicts a hypothesis is reported as it is.

## Amendment 1 (after 71 of 86 tables, before the remaining 15)

The pairwise search of the combination rule grows with the square of the categorical columns and
cannot run on tables with hundreds of binary columns (InternetAds). It considers at most the 80
categorical columns with the most levels (ties by name). No table already run has more than 71
categorical columns, so their results are unchanged by the cap.
