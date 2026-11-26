# Naturally labelled chronological study: protocol (issue #78)

Written and archived before any result of this study exists. It is a new study. It does not
change the archived P5 verdict, which stays on the four labelled pool tables.

## Question

The chronological conclusions rest on four labelled tables. Issue #78 asks for at least ten
labelled datasets with a verified time variable, a recorded licence and a rerun of the chronological
and decision studies with the 17 detectors. This study adds series whose anomalies are real events
recorded by their producers, not minority-class proxies and not injected faults.

## Candidate review (decisions fixed before the runs)

| Candidate | Producer | Data terms found | Decision |
|---|---|---|---|
| SKAB v0.9 | Skoltech testbed (Katser, Kozitsin) | repository GPL-3.0; Kaggle DOI 10.34740/kaggle/dsv/1693952 | integrate |
| NAB `real*` series | Numenta; third-party producers per family | repository MIT; third-party terms not individually stated | integrate, limitation recorded |
| NAB `artificial*` series | Numenta (synthetic) | MIT | excluded: synthetic, not real events |
| UCR Time Series Anomaly Archive 2021 | Keogh et al. (Hexagon-ML / UCR) | no licence or terms in the archive | not integrated: rights not verified |
| TSB-UAD, TSB-AD | Datum lab (Apache-2.0 code) | aggregates of third-party data; each source keeps its own terms | not integrated directly: members already reviewed individually (NAB) or without verifiable terms |
| NASA SMAP/MSL | NASA JPL (Hundman et al.) | archive returns 403; repository licence is NOASSERTION | not integrated |
| SMD (OmniAnomaly) | NetMan lab | repository MIT, no statement for the data | not integrated |

Rights of the data redistributed by a software repository are not the rights of the repository code.
Nothing is redistributed here: files are fetched from the pinned commit, hashed, and kept outside
the repository, as for the pool. Pinned commits: SKAB `b2c0d46c2971dcbfe71e26087b6d231998bb91c2`,
NAB `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140`.

## Series and source groups

Each file is one series (one dataset of the study). Series from the same producer are related, not
independent. Source groups, fixed here: `skab` (one testbed, 34 files), `nab_aws` (CloudWatch
metrics), `nab_adexchange`, `nab_traffic` (Minnesota DOT sensors), `nab_tweets` (Twitter mention
volume), `nab_known_cause` (one group per file: taxi counts from the NYC TLC, machine temperature,
ambient temperature, CPU utilisation of an autoscaling group, request latency, two rogue-agent
series are distinct systems and are one group each, `nab_taxi`, `nab_machine`, `nab_ambient`,
`nab_asg`, `nab_latency`, `nab_rogue`). Every uncertainty and every claim of the study is computed
over source groups, with series as the secondary view.

## Labels and their semantics

- SKAB: the `anomaly` column (collective anomaly period after an induced fault: valve closing,
  fluid leak, rotor imbalance, cavitation). Row-level, interval semantics. The `changepoint`
  column is not used.
- NAB: the windows of `labels/combined_windows.json`. A window is a tolerance interval around the
  labelled event (about ten per cent of the series, shared among events), so rows inside a window
  are labelled anomalous. Precision is therefore not comparable to point-labelled data. The point
  timestamps (`combined_labels.json`) give one to five positives per series, too few for a ranking
  metric, and are not used.

The conversion from intervals to rows is a convention, stated here, not a property of the data.

## Features

SKAB: the eight sensor columns, nothing else. NAB: univariate series, so each row gets four
causal features computed from the past only: the value, its first difference, the value minus the
mean of the previous 24 observations and the standard deviation of the previous 24 observations.
The first 24 rows are dropped and counted. Every detector receives the same table.

## Partitions and eligibility

The rows are sorted by the parsed timestamp (whether the file was in order is recorded). First 70 %
of rows fit the detectors, next 15 % calibrate thresholds (validation), last 15 % evaluate. No test
label is used to choose anything. A series is evaluated only if its test partition holds at least
20 anomalous rows, the rule already used for the pool: with fewer, a ranking metric is not defined
usefully. The ineligible series are listed with the reason and are not hidden. Eligibility depends
on a label count, so the evaluated set is not a random sample of the corpus; this is a limitation,
not a selection among detectors.

## Detectors and arms

The 17 detectors of the registry, with the training-size skips of the pool study. Chronological
arm: the partition above. Stratified arm: ten seeded stratified 70/15/15 partitions (seeds 42, 1
to 9) of the same rows, which is optimistic for autocorrelated series because neighbouring rows fall
on both sides. Prevalence-matched control as in `temporal_decision.py`.

## Hypotheses

- N1 (replication of P5 on natural labels): the chronological PR-AUC is lower than the stratified
  PR-AUC for at least two thirds of the (series, detector) pairs, and the median detector
  difference has a bootstrap interval over source groups below zero.
- N2: the detector ranking by chronological PR-AUC agrees with the ranking by stratified PR-AUC
  (Spearman correlation at least 0.8, per series, median over series).
- N3: the prevalence-matched control closes at least half of the gap between the arms in a
  majority of series (H4 of the temporal-decision study).
- N4 (exploratory, no direction fixed): rule-based, classical and neural families differ in mean
  rank; tested with paired Wilcoxon tests over source groups and Holm correction, with effect sizes.

PR-AUC is also reported as lift over prevalence, `(AP - prevalence) / (1 - prevalence)`, because
test prevalence differs strongly between series. A non-significant difference is not read as
equivalence. Results that contradict a hypothesis are reported as they are.

## Limits announced

Windows and collective periods, not points; SKAB is one testbed; NAB third-party terms unverified;
the evaluated set depends on a label-count rule; the detectors keep their default settings.

## Amendment 1 (before any result)

The decision study reads the alert rate from the labelled share of the fitting rows. Several series
hold no labelled anomaly in the first 70 % of the rows, which gives a rate of zero and an undefined
detector. For these the rate is floored at 0.01 for every series and every detector alike. It is a
prior on the alert budget, not a test label.

## Amendment 2 (before any result)

A ranking metric also needs normal rows in the evaluation partition: a series whose last 15 % is
entirely anomalous cannot be evaluated. A series is therefore evaluated only if the test partition
holds at least 20 anomalous and at least 20 normal rows.
