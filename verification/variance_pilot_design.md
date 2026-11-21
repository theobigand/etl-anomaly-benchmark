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

## 10. Revision after the owner decisions of 2026-11-21 (design only; the pilot is not run)

### 10.1 Outcomes and detection units

- **Primary outcome:** recall at a matched alert budget. The alert budget is fixed per detection unit as a fraction of the units
  scored in the test partition (default 1 percent, with 0.5 and 2 percent as sensitivity points), identical for every detector in a
  contrast and set without labels. Detection units follow the protocol: row (P-TAB), time window (P-TS), event sequence (P-SEQ),
  relationship (P-REL), nested path (P-NEST). Recalls on different units are never pooled as if equivalent: the source-level
  value is computed on the protocol's own unit and aggregated across protocols only inside a prespecified family
  (section 10.4) as an average over the protocols that apply to the source.
- **Secondary outcomes:** AUPRC at a standardised anomaly prevalence (injection is performed at one prespecified prevalence per
  protocol, and AUPRC is also reported against the prevalence baseline so that sources at different prevalences are not compared
  directly); AUROC; false-positive burden (false alerts per clean unit and absolute alert volume per run); runtime and memory.
  A secondary metric is computed only for detectors and protocols where it is defined. AUROC, AUPRC and recall are strongly related and
  are not treated as independent evidence.
- **Smallest effects of interest (provisional design assumptions, not validated):** recall 0.05, AUPRC 0.05, AUROC 0.02,
  false-positive burden and cost 20 percent relative. Sensitivity to smaller and larger effects is tabulated in
  `dataset_target_methodology.md` section 10 (columns for 1, 3 and 6 comparisons and three hypothetical SDs).

### 10.2 Pairing, unit of inference and missing results

The unit of inference is the original provenance group. Within a group, two detectors are compared only on the same observations,
the same train, validation and test partitions, the same fault realisations (the same injected faults and seeds), the same
evaluation units and the same alert-budget rule. Seeds and repeated injections are averaged to one value per group and detector;
they improve precision inside a group and do not add groups. Population estimates use the source-level paired differences, with
random effects for domain and schema family (a hierarchical model) as the primary analysis and a domain-cluster bootstrap as
the robustness check. A detector that is not applicable to a protocol is recorded as not applicable and the group leaves that
contrast; a detector that fails technically is recorded as a failure and is not imputed; the number of groups per contrast is
reported with every estimate. Contrasts across structurally incompatible detectors are not formed.

### 10.3 Pilot and confirmatory separation

Pilot and confirmatory groups are disjoint at the provenance-group level. Groups that share a generating system, duplicated records or
a substantially shared population (the creator-linked closure of the flat tables, the French timetable feeds as one schema family,
the 4TU process logs of one organisation) are treated as linked: when one member is drawn into the pilot, the others of its linked set
are kept out of the confirmatory holdout where the readiness inventory allows it, and the exception is recorded. Pilot groups are
drawn by a seeded draw over the fixed, alphabetically ordered provenance-group identifiers of each category (`draw_pilot`), using
no detector output. The confirmatory selection is not adapted to pilot rankings.

### 10.4 Holm families derived from the thesis hypotheses

The families follow the four research questions of the paper (`paper/main.tex`) and the batch-level study. Counts are those of the
prespecified primary contrasts; each family is tested with Holm's step-down procedure at familywise alpha 0.05; exploratory
diagnostics are not adjusted and are labelled exploratory.

| Family | Research question | Primary contrasts | Planned comparisons k |
|---|---|---|---:|
| F1 | RQ1: rule-based, classical and neural detectors | rule versus classical, classical versus neural, rule versus neural, on recall at the matched budget, pooled over the protocols that apply | 3 |
| F2 | RQ2: per-anomaly-mechanism profile | rule-based versus the best prespecified learned family inside each of the five protocols (P-TAB, P-TS, P-SEQ, P-REL, P-NEST) | 5 |
| F3 | RQ3: operating point and time | label-free budget versus training-prevalence threshold; chronological versus random split | 2 |
| F4 | RQ1 operational: alert burden | the three F1 contrasts on false-positive burden (log ratio) | 3 |
| F5 | RQ4: cost | the three F1 contrasts on fit plus score time (log ratio) | 3 |

Total planned primary comparisons: 16 over five families, adjusted within family, not across families. The families are fixed
before any confirmatory outcome and are not split afterwards. Per-category effects are exploratory unless the confirmatory
holdout of the category is large enough (section 10.5).

### 10.5 Pilot size and allocation against the current inventory

Ready groups per category (readiness contract, 2026-11-21): C1 52, C2a 12, C2b 10, C3 11, C4 13, C5 20, C6 9; a group in
several categories is drawn once. Allocation rule (`pilot_allocation`): at most 25 percent of the ready groups of a category, at
least 3 where available, total capped at 24 pilot slots. This gives the slots C1 5, C2a 3, C2b 3, C3 3, C4 3, C5 4, C6 3 (sum 24);
a seeded dry run on the identifiers (no detector involved) yields 22 distinct groups because some groups serve two categories, leaving
a confirmatory holdout of 96 groups overall and, per category, 47, 9, 6, 8, 10, 16 and 6 groups (C1 to C6 in the order above:
C1 47, C2a 9, C2b 6, C3 8, C4 10, C5 16, C6 6).
Reading: a pilot of about 22 to 24 groups is compatible with the inventory and represents every category, but it leaves
confirmatory holdouts of 6 to 16 groups in the scarce categories, far below the 34 to 52 sources that a one-comparison contrast needs
at a hypothetical SD of 0.10 and a difference of 0.05. Category-level confirmatory claims are therefore not supportable from the current
inventory; pooled claims over the holdout (96 groups, fewer after clustering) are. Smaller pilots (16 groups with 2 to 3 per category)
keep more holdout but weaken the variance estimate; larger pilots consume scarce categories. The proposal for owner review is 24 slots
as drawn above, with a stated fallback to 16 if the inventory of any scarce category falls.

### 10.6 Precision of the pilot SD estimate and its assumptions

For independent normal source-level differences, the 95 percent interval of sigma-hat divided by sigma from n sources is
[0.78, 1.40] at n = 24 (so the upper limit of sigma is 1.40 times sigma-hat; the earlier 1.40 is this value). It holds only if the
source-level paired differences are independent and approximately normal with a common variance. Clustering by schema family and domain
lowers the effective number of sources: with a design effect of 1.3, 1.6, 2.0 and 3.0 (hypothetical) the upper ratio of the 24-source
pilot becomes 1.50, 1.58, 1.70 and 2.04; for 16 sources it is 1.55 (no clustering) to 2.87 (design effect 3) and for 32 sources 1.33 to 1.83
(`effective_sd_interval`). Heterogeneous variances across categories would widen the intervals further; the variance components
are therefore estimated in the hierarchical model of section 10.2 with profile-likelihood intervals, and the planning figure above
is only a design guide.

### 10.7 Decisions still needed from the owner

1. The alert budget fraction (1 percent proposed) and its sensitivity points.
2. Whether category-level confirmatory claims are dropped in favour of pooled claims, given holdouts of 6 to 16 groups.
3. The 24-slot allocation or the 16-slot fallback, and the linked-set rule for the holdout.
4. The family definitions F1 to F5 and the choice of the best learned family in F2.
5. The prevalence standard for AUPRC per protocol.
