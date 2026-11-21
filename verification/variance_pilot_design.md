# Variance pilot: draft preregistration (T424)

Status: design only. Execution is not authorised; the freeze on detector experiments, pilots and neural
campaigns stays active until the owner lifts it explicitly. Nothing here was run. This document must be
dated and frozen before the first pilot result exists, and the pilot sources must not be reused as
confirmatory evidence (section 7).

## 1. Purpose

The pilot estimates the quantities that turn the illustrative sample-size tables of
`dataset_target_methodology.md` into requirements: the between-source standard deviation of paired
detector differences (sigma), the source-by-detector variance, the intra-cluster correlation by domain,
schema family and curator, and how often each detector pair is applicable. It does not test hypotheses and
does not rank detectors; its outputs are variance components with uncertainty intervals.

## 2. Contrasts (claim families)

Prespecified before any result; each family is one Holm family at familywise alpha 0.05 in the later
confirmatory stage. The pilot estimates the variance of the same contrasts.

| Family | Contrast (paired within source) | Metric | Applies to |
|---|---|---|---|
| F1 | rule-based versus classical machine learning | recall at matched alert budget; AUPRC at standardised prevalence | all structures where both are defined |
| F2 | classical machine learning versus deep learning | same | same |
| F3 | per-mechanism profile (injected type) | detection rate per mechanism and family | groups whose protocol supports the mechanism |
| F4 | alert burden | false alerts per clean unit at matched detection quality (log ratio) | same as F1 |
| F5 | cost | fit and score time and peak memory (log ratio) | dataset instances, not source-sampled |

AUROC is reported as a secondary metric (smallest effect of interest 0.02); AUROC, AUPRC and recall at an
alert budget are strongly related, so they are not counted as independent evidence and are not placed in
one correction family as separate claims. Metrics are used only if they exist in the thesis methodology.

## 3. Detector families and applicability

Detector families are those of the existing 17-detector registry (rule-based, classical machine learning,
neural). A detector enters a contrast only where it is applicable to the structure and mechanism of the
group; non-applicable cases are recorded, not imputed. The pilot reports, per contrast, the number of groups
where both detectors apply, which fixes the effective sample of each claim.

## 4. Sampling units and clustering

Unit of inference: the provenance group (original producer and generating system). Inside a group, batches,
windows, injected faults, severities and seeds are repeated measures and are averaged to one paired
difference per group before variance estimation. Clusters: domain, schema family and curator (crossed or
nested as the data allow). The unit of the variance estimate is never a row, a batch or a seed.

## 5. Pilot sample selection

- Eligible: groups at experiment-ready status that are not sealed for the confirmatory stage.
- Frame: stratified by category and by domain; within a stratum, groups are listed in a fixed order (alphabetical
  provenance-group id) and selected by a seeded draw recorded before any result; the seed and the list are
  committed with the design.
- Size: 24 groups minimum in total with at least 4 per category and 3 domains per category where available; the
  alternative sizes below are decided from the precision targets, not from observed performance.
- The same selection rule applies to every detector; a source is never added or dropped because a detector did
  well or badly on it. A source that cannot be run for a technical reason is replaced by the next in the fixed order
  and the replacement is logged.

## 6. Analysis model and estimators

For contrast c, group g in cluster(s) k: D_cg = delta_c + u_k + e_g (random effects for domain and schema family,
residual at group level), fitted by restricted maximum likelihood; variance components with profile-likelihood or
parametric-bootstrap intervals, never point estimates alone. sigma_c is the square root of the total variance of D.
The intra-cluster correlation of each cluster level is estimated from the same model; if a level is not estimable
from the pilot (too few clusters) it is reported as not estimated and the sensitivity range of the methodology
document remains the planning basis. Source-by-detector variance is estimated from per-group detector scores in a
model with detector and group effects. No multiple-comparison adjustment is applied to variance estimates.

Precision of sigma from n groups (normal differences, 95 percent interval, `research/target_framework.py`):
n = 10 gives an interval of 0.69 to 1.83 times the estimate, n = 24 gives 0.78 to 1.40, n = 48 gives 0.83 to 1.25.
The pilot size is therefore chosen by the upper-limit ratio the owner accepts (1.40 needs 24 groups per contrast);
contrasts defined on fewer groups report wider intervals and are flagged.

## 7. Separation from confirmatory data and selection rules

- A confirmatory hold-out of groups is fixed and recorded before the pilot starts, chosen by provenance and
  structure only; pilot groups and hold-out groups are disjoint at the provenance-group level and at the
  schema-family level where possible.
- Detector hyper-parameters and operating points are fixed by the label-free protocols of the thesis before the
  pilot; the pilot may not change them.
- No dataset is added, dropped or re-weighted because of observed detector performance; no injected fault
  parameter is tuned on pilot results.
- Pilot results update only the sample-size calculation (variance components); they do not enter the confirmatory
  estimates. If a pilot group is later wanted in the confirmatory set, that is a deviation to be recorded.

## 8. Recalibration rule

After the pilot, required confirmatory sources per family are recomputed with `paired_sources` (exact t, Holm
level alpha divided by the family size k), using the upper end of the sigma interval and the estimated design
effect from the cluster structure; the result is recorded in a dated addendum before the confirmatory run. If the
requirement exceeds the attainable number of independent groups, the claim is narrowed (fewer strata, larger
smallest effect, or exploratory status) rather than the data selected.

## 9. Open points for the owner

1. The pilot size (24 groups minimum is a proposal).
2. Which metrics enter F1, F2 and F4 (those that exist in the thesis methodology).
3. The confirmatory hold-out rule and who seals it.
4. The date the freeze is lifted for the pilot only.
