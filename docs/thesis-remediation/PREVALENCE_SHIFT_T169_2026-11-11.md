# Fixed thresholds under anomaly-prevalence shift (T169) - exploratory, 2026-11-11

Code: `research/prevalence_shift.py` (L4, `research/tests/test_prevalence_shift.py`). Evidence:
`verification/evidence/alert_budgets/prevalence_shift.json` (built from the archived alert-budget cells,
2,000 source-resampled bootstrap draws, seed 2026; no refit).

## Design

The fitted model and its training-score threshold are fixed; nothing is recalibrated with held-out data.
For a budget cell the held-out true- and false-positive rates (TPR, FPR) of that fixed threshold are read
from the confusion counts. Under pure prior (label) shift, a population with prevalence pi has the
expected alert rate pi*TPR + (1-pi)*FPR, precision pi*TPR / alert rate, and unchanged recall and FPR.
Held-out labels are therefore used to build the simulated populations (and to score them), never to set
a threshold. The unit tests check the formulas, the reproduction of the observed cell at the observed
prevalence, and agreement with a 400,000-row resampled population (alert rate within 0.002, precision
within 0.02).

What this isolates: a change of the mixing proportion with the conditional score distributions of normal
rows and anomalies held fixed. Score-distribution change is excluded by construction (T170) and
real deployment drift is not represented. Prevalences 0.5%, 1%, 2%, 5%, 10% and 20%; budgets 1%, 2%,
5%; 14 score-based detectors; a per-problem seed mean, then the median over problems with an interval
that resamples original sources.

## Denominators

At the 2% budget 100 problems and 500 seed runs per detector, except k-NN and LOF (92) and OCSVM (84),
which the size limits skip. The smallest held-out class in a cell is 1 positive and 10 negatives, so the
TPR and FPR of some problems are very noisy; the reweighting inherits that sampling error. Cells infeasible
for the budget are excluded. The rules have no budget cell and are excluded.

## Findings

- Recall and FPR do not change with prevalence by construction. Alert volume and precision do.
- Alert volume: the medians of the ratio of the alert rate to the budget range, over the 14 detectors, from
  0.83 to 1.83 at a prevalence of 0.5% and from 1.15 to 2.73 at 20% for the 2% budget (1% budget: 0.86-2.02
  and 1.24-3.65; 5% budget: 0.76-1.42 and 1.09-2.05). A threshold calibrated as a 2% alert budget therefore
  alerts on 15% to 173% more rows than planned when anomalies are a fifth of the population, and, when
  anomalies are rare, alerts on 17% fewer rows (0.83) to 83% more (1.83) depending on the detector. The
  budget holds only near the prevalence and conditional score distributions where the cell was measured.
- Precision rises almost in proportion to prevalence: at the 2% budget the median precision at 20% is 14.7
  to 31.8 times that at 0.5% (Isolation Forest 0.017 to 0.304; PCA 0.011 to 0.277).
- The detectors already above their budget at the observed prevalence (Deep SVDD 1.9, autoencoder 1.4) are
  worst at every prevalence.

## Limits

Expected values, not resampled draws; the label-shift assumption is strong; the few-positive problems;
exploratory and limited to the archived pool; no claim about operational monitoring, which is T171.
