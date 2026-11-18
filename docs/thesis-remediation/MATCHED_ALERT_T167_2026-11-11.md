# Rules against learned detectors at comparable alert volume (T167) - exploratory, 2026-11-11

Status: exploratory, not promoted to the main tables (T172 open). Code: `research/matched_alert.py`
(L4, `research/tests/test_matched_alert.py`). Evidence: `verification/evidence/alert_budgets/matched_alert.json`
built from the archived classical and neural alert-budget cells (no refit).

## Why a matched comparison is only approximate

A rule keeps its own decision contract and alert volume (T168); it has no score to threshold, and no
threshold was invented for it. The learned detectors are calibrated on training scores only, so their
realized held-out alert rate differs from the nominal budget. Exact equality of alert volume is therefore
not attainable without using test information. Instead, for each rule, learned detector, problem and
seed, the archived budget cell (0.5%, 1%, 2%, 5%, 10%) whose realized held-out alert rate is closest to
the rule's is paired with it, and the pair is kept only if the two rates differ by less than a factor of
1.5. The choice of cell uses realized alert rates, never a label; the thresholds stay training-calibrated.
This is an evaluation-time construct, not a deployment procedure.

## Method

Differences (learned minus rule) in precision and recall are averaged over the eligible seeds of a
problem (at least 3 of 5), then compared with a bootstrap that resamples original sources
(`source_clustered.source_id`, 10,000 draws, seed 2026), with Holm adjustment over the 42 comparisons of
each metric. 100 problems read; each comparison states its problems, seed runs and the seed runs
excluded (unpaired, rule without alerts, no cell within tolerance, fewer than 3 eligible seeds).

## Results

- Match quality: across comparisons the quartiles of the ratio of the learned to the rule alert rate lie
  between 0.76 and 1.22 (median about 1.0).
- Eligible problems: 39 to 69 for z-score and Great Expectations, only 14 to 35 for IQR. IQR alerts on a
  median 22.8% of rows, beyond the largest budget (10%), so it can be matched only on the problems where
  it alerts less. These results describe those problems and do not represent IQR in general.
- Most differences are small and their intervals include zero. Four of 84 remain below 0.05 after
  Holm adjustment, all against learned detectors: z-score exceeds the autoencoder in recall (-0.079) and
  precision (-0.044), Deep SVDD in precision (-0.078) and PCA in recall (-0.085) at comparable alert volume.
- Great Expectations is level with every learned detector after adjustment.
- Hence at comparable alert volume a generic fitted rule is not generally worse than a learned
  detector, and for some learned detectors it is better. This is exploratory and says nothing about
  domain-informed rules, which the benchmark does not contain. No ranking of learned detectors is claimed.

## Limits

Matching on realized alert rate, a coarse five-point grid, the 1.5 tolerance and the 3-seed minimum are
analysis choices fixed before looking at the differences but not tuned to them; the sensitivity to them was
not explored. Neural AE1SVM and LUNAR results depend on the thread setting (see ALERT_BUDGETS_2026-11-11.md).
