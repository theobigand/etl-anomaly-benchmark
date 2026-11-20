# Typed injection on mixed-schema and small tables: protocol (issue #77)

This protocol is written and archived before any detector result of the mixed-schema study exists.
It extends `typed_injection.md`, which stays unchanged and keeps governing the 58 tables it
already covers. Results of the two protocols are reported side by side and never pooled.

## Question

The numeric protocol accepts a table only with at least 3,000 rows and four continuous columns, and
it knows no categorical fault. Of the 152 catalog tables, 94 were therefore never measured by a
detector-quality experiment with a known fault. Do the per-type detector profiles of the numeric
protocol carry over to tables with categorical and discrete columns and to smaller tables?

## Carrier

The unlabelled feature table (identifier and target columns removed as in the labelled study; for a
labelled set only normal-class rows, for ADBench only label 0). A column is dropped when it is
constant, all missing, more than 5 % missing, or identifier-like text (more than 50 levels and more
than half of the rows unique). Remaining rows are complete cases without exact duplicates, capped
at 20,000 rows (seed 0). A numeric column with at least 10 distinct values is `num`; every other
column is `cat` (text, booleans and numeric codes).

Eligibility: at least 3 usable columns and, in tier A, at least 500 rows, or in tier B, 200 to 499
rows. Tables with fewer than 200 rows are not eligible: six groups of faults cannot be split 70/15/15
with a usable test partition. They keep their other roles and are reported as such.

## Faults

Each fault group holds `k` rows. Tier A: `k = max(round(0.03 n), 15)`; tier B: `k = 8`. Statistics
(mean, standard deviation, quantiles, level sets, frequencies) come from the training partition's
clean rows only, as in the train-only replay. A type is injected only when the schema supports it;
unsupported types are recorded as absent, not as zero.

- `missing_value`: one or two cells, any column, set to missing.
- `duplicate`: exact copy of a clean row.
- `univariate_outlier` (needs a `num` column): one column at mean plus or minus u standard
  deviations, u in [6, 12], times severity.
- `multivariate_outlier` (needs two `num` columns): the most correlated pair receives the 97 % and
  3 % quantiles, violating the correlation while each marginal stays in range.
- `invalid_format` (needs a non-negative `num` column): sign change, sentinel -999 or scale error
  by 1,000.
- `invalid_code` (needs a `cat` column): the value is replaced by a code outside the column's
  domain (`__INVALID_<n>__`).
- `cross_column_swap` (needs two columns of one kind whose domains differ): the values of the two
  columns are exchanged. For `num` the medians must differ by at least the summed inter-quartile
  ranges; for `cat` the Jaccard overlap of the level sets must be at most 0.5. The pair with the
  smallest overlap is used.
- `distribution_shift`: in the most recent 10 % of the arrival order, up to three `num` columns are
  shifted by 1.5 standard deviations times severity and up to three `cat` columns are redrawn
  uniformly over their training levels (a prevalence shift of valid values).

These faults are artificial. A detected fault demonstrates sensitivity to that fault, not
detection of naturally occurring errors.

## Encoding and detection

Detectors need numeric input. A `cat` column with at most 20 training levels is one-hot encoded; a
column with more levels is frequency encoded. The encoder is fitted on the training partition
(unsupervised, labels unused). Unseen and missing values encode to all zeros and frequency zero.
`num` columns stay raw with missing cells preserved, as in the numeric protocol. Identity-grouped
70/15/15 split, detectors fitted on training with the training fault prevalence as contamination,
recall per type on the test partition against clean rows only, the same 11 classical and 6
neural detectors, false-positive rate on clean test rows.

Seeds: tier A uses 42, 1, 2, 3, 4. Tier B uses 20 seeds (42, 1 to 19) and pools the test counts,
because one partition holds only one or two rows per type.

## Hypotheses

- M1: for `num`-only schemas the per-type recall ranking agrees with the numeric protocol.
- M2: categorical faults (`invalid_code`, `cross_column_swap` on `cat`) are found by the density and
  distance detectors, and missed by the rule detectors, which read no categorical column.
- M3: tier B profiles are noisier but not systematically different from tier A.

A result that contradicts a hypothesis is reported as it is. No table is removed after a result.
