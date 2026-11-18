# Preparation and information audit — 2026-11-07

## Two protocols, two statuses

The historical archives of `research.normalise.clean` filter constant columns,
mostly-missing columns and high-cardinality categorical columns, encode the
remaining categories, then remove duplicates before the split. These decisions
read the complete population, so the results remain descriptive. The report it
produces lists the dropped and encoded columns and the removed rows, but does
not repair this historical access to the evaluation rows.

The prospective path `research.pool_train_only` keeps, in every output, the
`preprocessing` report of `prepare_frozen`: retained, omitted and encoded
columns, and the medians and scale learned on the training partition. It encodes
a category unseen in the test partition as a zero block without changing the
vocabulary. It is the only path that allows a train-only comparison with frozen
partitions.

## Calibration is label-informed

The `pool_train_only` path sets the contamination passed to the detectors from
the prevalence of the anomaly label in the training partition
(`calibration.policy = train_prevalence`). That uses training labels. It is not
a label-free deployment setting, and it must not be presented as unsupervised
behaviour. In this path the evaluation labels are not used for calibration. The archived
benchmark baselines that record `calibration: train_prevalence` have the same
label-informed property; the fixed contamination of 0.02 recorded by the fixed
benchmark is the label-free variant.
The rules do not read the contamination.

## Information received by the families

| context | variables actually available | declared consequence |
| --- | --- | --- |
| comparable registry | numeric columns; text and categorical columns are ignored | numeric models and rules cannot directly detect formats, categorical domains or textual semantics |
| Great Expectations | all columns for the non-null check; numeric bounds only | its null coverage is wider, but it does not represent business rules about format or consistency |
| fault-injection carriers | four or more continuous columns, then six constructed numeric faults | this is not a comparison of categorical or textual detection |
| prospective `pool_train_only` | numeric, and categories with a training vocabulary; free text and high cardinality omitted | this representation differs from the historical registry and its results cannot replace it without a separate campaign |

For the learned models, median imputation is fitted on the training partition
before standardisation. A missing value at test time therefore becomes an
imputed numeric value and may no longer be visible as a fault; the Great
Expectations check instead keeps an explicit non-null expectation.
Standardisation uses the training mean and standard deviation only. The rules
use their own training statistics (mean/standard deviation, quartiles or
percentile bounds), without imputing an input before scoring.

## Orientation and comparison limit

The `Detector.score` contract and the registry tests require finite scores,
indexed like the input, where a larger value means a stronger anomaly. The PyOD
adapters return `decision_function`; the rules and the custom adapters follow
the same orientation. Binary thresholds remain distinct from ranking metrics.

The families therefore do not receive exactly the same information in every
path: the null rules see the nullable columns, the comparable models see only
numeric data, and the prospective path may encode categories. This asymmetry is
an explicit methodological limit, not evidence that one family is
intrinsically superior.
