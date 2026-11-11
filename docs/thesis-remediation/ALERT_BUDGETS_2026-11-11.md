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

All 17 detectors of the registry: 8 classical score-based detectors, 6 neural detectors and 3 rules.
The classical run (`verification/evidence/alert_budgets/classical`) and the neural run
(`.../neural`) are separate, unmodified records.

- Classical: 100 problems, 0 failed to load, 0 failed seed runs, 32 (problem, detector) pairs
  skipped by the existing size limits of LOF, k-NN and OCSVM.
- Neural: 100 problems x 6 detectors x 5 seeds = 3,000 seed runs, 0 failed, 0 skipped. 15,000
  budget cells, of which 450 are infeasible (0.5% on the 13 problems with fewer than 200 training
  rows, 1% on the 2 with fewer than 100). Per-cell problem and seed-run counts are in each
  `summary.md` / `summary.json`.

## Reproduction

`python research/alert_budget.py --output <dir>/runs` (classical) and
`research/run_alert_budget_neural.sh <python> 2 4` (neural: 2 workers, 4 threads each, resumable,
checkpoints in `neural/cells` (local only; `runs/` holds the same rows), fingerprints in `neural/manifest.json`, run at a clean `ae994808`
with numpy 2.4.6, pandas 3.0.6, pyod 3.6.7, scikit-learn 1.9.1, torch 2.14.1), then
`research/alert_budget_summary.py <dir>/runs --json ... --markdown ...`. Raw scores were not
archived, so the detectors were refitted once per problem, detector and seed; no refit per budget.
The neural scores are the fit-time and inference scores of the same model (equal on the fit rows:
Spearman 1, maximum difference 0, higher is more anomalous).

## Checks

- Classical, `adbench:Cardiotocography`: the 2% budget reproduces the archived label-free metrics
  exactly (0 mismatches). The first 87 problems ran before the infeasible-budget handling was added;
  the other 13 were re-run with it; feasible cells are computed identically.
- Neural, archive-independent invariants on all 15,000 cells: confusion counts sum to the test rows,
  the alert rate equals (tp+fp)/rows, thresholds decrease and test alert rates increase with the
  budget, the realized fit rate never exceeds the nominal budget by more than one row, and a cell is
  infeasible exactly when the fit rows are fewer than 1/budget. 0 violations.
- Neural, against the archived 2% results (3,000 runs): autoencoder, DIF and VAE agree exactly.
  AE1SVM differs in 314 of 500 runs, LUNAR in 187 and Deep SVDD in 5. This is numerical
  nondeterminism of those models, not the threshold rule: contamination does not affect their
  training (identical scores at contamination 0.02 and at the prevalence), they are repeatable
  within one setup, but their held-out scores change with the PyTorch thread count. On one fit of
  `adbench:breastw` the 2% alert rate of AE1SVM was 4.4% with 1 or 4 threads and 2.9% with 10;
  LUNAR varied by up to 2.7e-3 in score and Deep SVDD by 1e-7 without changing any alert. Results
  for AE1SVM and LUNAR therefore hold for the recorded setup (4 threads) and are not bit-reproducible
  across thread counts or against the earlier archive.

## Findings (medians over problems of seed means; labels used only to score the flags)

- Classical: the held-out alert rate is 1.05 to 1.36 times the nominal budget at 1% and 1.02 to
  1.20 times at 2% (OCSVM and PCA drift most). Median recall is 2% to 6% and precision 13% to 20%.
- Neural: the held-out alert rate exceeds the budget more: 1.13 to 2.87 times at 1% and 1.08 to
  2.15 times at 2%. Deep SVDD is the largest (2.87 and 2.15), then the autoencoder (1.68, 1.52), DIF
  (1.60, 1.47) and LUNAR (1.60, 1.22); VAE (1.13, 1.10) and AE1SVM (1.14, 1.08) are closest.
  Median recall at 1% and 2% is 2% to 10%, precision 11% to 18%. The cause (scores on training rows
  lower than on held-out rows, fit-to-test shift) was not isolated.
- Rules at their own settings alert far more than a 2% budget (median alert rate z-score 11.4%,
  IQR 22.8%) except Great Expectations (1.6%, recall 3.1%). Recall of 30% and 41% for z-score and
  IQR comes with an alert volume about 6 to 11 times the 2% budget.
- At a given budget, differences between detectors are small relative to the spread across
  problems. No ranking is claimed; that needs a paired, source-clustered comparison.

## Limits

Medians over heterogeneous problems, no source-clustered inference, the build contamination is a
constant that does not tune the score distribution, and the thread-count sensitivity above. The
results are exploratory and are not promoted to the main tables (T172 stays open).

## T168: mandatory rules versus tunable thresholds

The three benchmark rules (z-score, IQR, Great Expectations) are generic statistical rules whose
bounds are fitted on training data (`RULE_DEFINITIONS_2026-11-03.md`; Methods, "Rule-based
detectors": they do not represent domain-informed declarative constraints). The benchmark therefore
contains no mandatory business rule. Evidence of the separation in the budget study: a rule has no
score, `fit_scores` returns none for each of them, and `run_method` gives it a `rule` record and
never a `budgets` record (`test_no_rule_is_ever_given_a_tunable_alert_budget`). A mandatory
business rule (a non-null key, a domain range, a format) is a constraint to enforce, not a
statistical operating point, and would likewise be reported outside any budget.
