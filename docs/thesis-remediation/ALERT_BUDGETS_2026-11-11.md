# Label-free alert budgets (T163, T164) - exploratory, 2026-11-11

Status: exploratory. Not promoted to the main thesis tables (T172 stays open). The original
Oracle / Label-informed protocol (training-prevalence contamination) is untouched.

## Protocol

- Deployment / Label-free: the threshold is the `1 - budget` quantile of the detector's scores on the
  unlabelled fit rows. No test label, no test score and no training prevalence is read: detectors are
  built with a constant contamination of 0.02 (`research/alert_budget.py`, `FIXED_BUILD`).
- Budgets: 0.5%, 1%, 2%, 5%, 10%. Flags are `score > threshold` (higher is more anomalous), the rule
  used by the archived 2% label-free run.
- Three numbers are kept apart: the nominal budget, the realized rate on the training scores (ties
  can lower it; `ties_at_threshold` is recorded) and the realized alert rate on held-out rows.
- A budget needs at least `1/budget` finite training scores. Otherwise that cell is recorded as
  `infeasible` (the 0.5% budget on 13 problems with fewer than 200 training rows) and is excluded
  from that cell's denominator, never counted as zero.
- Rules (z-score, IQR, Great Expectations) have no score to threshold. Their own decision is a
  separate untuned reference, never part of a budget comparison (T168 is not claimed).
- Data: the 100-problem labelled pool, 5 seeds (42, 1, 2, 3, 4), the archived stratified 70/15/15
  split of `normalise.split`. Raw scores were not archived, so detectors were refitted
  (`python research/alert_budget.py --output verification/evidence/alert_budgets/classical/runs`,
  then `research/alert_budget_summary.py`).

## Scope and denominators

Classical registry only: 8 score-based detectors and 3 rules. The six neural detectors
(about 31 CPU-hours archived fit time) are NOT run: T163/T164 are partial for them.
100 problems read, 0 failed to load, 0 failed seed runs, 32 (problem, detector) pairs skipped by the
existing size limits of LOF, k-NN and OCSVM. Exact per-cell problem and seed-run counts are in
`verification/evidence/alert_budgets/classical/summary.md` and `summary.json`.

## Independent check

On `adbench:Cardiotocography`, the 2% budget reproduces the archived label-free metrics
(precision, recall, flagged share) for every ML detector and seed: 0 mismatches. The 87 problems
first run used the code before the infeasible-budget handling; the 13 small problems were re-run
with it. The logic for feasible cells is identical.

## Findings (medians over problems of seed means; labels used only to score the flags)

- Realized alert rate tracks the nominal budget: at 1% the median is 1.05 to 1.36 times nominal,
  at 2% 1.02 to 1.20 (OCSVM and PCA drift most). Test-time drift, not ties, drives the excess.
- At 1% and 2% all ML detectors have median recall of 2% to 6% and median precision of 13% to 20%.
  Differences between detectors at a fixed budget are small relative to the spread across problems;
  no ranking is claimed.
- Rules at their own settings alert far more than a 2% budget (median alert rate z-score 11.4%,
  IQR 22.8%) except Great Expectations (1.6%, recall 3.1%). Recall of 30% and 41% for z-score and
  IQR comes with an alert volume 5 to 11 times larger.

## Limits

Medians over heterogeneous problems, no source-clustered inference (see the source-clustered
analysis), no tuning of the build contamination for the score distribution, neural detectors absent.
