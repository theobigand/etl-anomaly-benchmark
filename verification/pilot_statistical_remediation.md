# Pilot statistical design: remediation of the methodological assessment (#153)

Status: 2026-11-27, design only. Nothing was run on benchmark data, no detector result was read, no approval is
implied and the experiment freeze stays active. Every number comes from provenance metadata or synthetic data and is
reproducible with the commands in section 12. Proposals are not protocol amendments until the owner records them.

## 0. What this document is, and what it is not

A separate, model-assisted methodological assessment of `OWNER_DECISIONS.md`, `pilot_statistical_design.md`,
`pilot_review_package.md`, `research/target_framework.py` and the pilot panel file reproduced the planning
calculations, inspected the panel composition and returned the verdict "accept with changes". This document records
that assessment accurately and answers its findings. It is not the independent review that #153 requires: the
acceptance criterion (`pilot_review_package.md` section 5) asks for a recorded review by an independent human
statistician or by a reviewer the repository governance recognizes, and neither the assessment nor this response
qualifies. No reviewer identity, endorsement or approval is created here. #153 therefore stays open.

## 1. Finding register

| ID | Finding | Remediation in this change | Residual | Blocks pilot authorization |
|---|---|---|---|---|
| R1 | the largest-pool allocation concentrates larger panels around C1 and UCI | `pilot_panel_design.balanced_panel` (section 3) | owner picks size and records the seed (D-01, D-11) | no, once D-01/D-11 are decided |
| R2 | only 7 of 16 pilot groups meet the size floor, so their variance may not transfer | split technical and statistical panels; statistical panel draws only floor-meeting clusters (section 4) | the floor is a structural proxy only | no |
| R3 | unit of inference and estimand ambiguous | explicit definitions and aggregation (section 5) | detector applicability per unit is not yet specified, so contrast-specific counts cannot be computed | yes for confirmatory sizing, not for a pilot |
| R4 | two-sided level described as the probability that sigma lies below the bound; `sd_ratio_interval` docstring inverted | docstring fixed, coverage separated (section 6); the calculation was correct and is unchanged | none | no |
| R5 | confirmatory planning assumes independent clusters | dependence sensitivity, pilot and confirmatory dependence kept apart (section 7) | design effects are hypothetical | no |
| R6 | planning uses a noncentral t test; the analysis is a bootstrap | design-only simulations; primary analysis fixed (section 8) | simulation is synthetic | no |
| R7 | smallest effect of interest ambiguous | clarified, sensitivity added (section 10) | owner confirms (D-05) | no |
| R8 | 11 comparisons in one Holm family | families of one and three prepared, selection rule predefined (section 11) | owner confirms (D-06) | no |
| R9 | batch alert budget described by Beta(1, n) | corrected analytically and by simulation (section 9) | threshold rule unchanged, amendment is the owner's | no, batch pilot is a separate gate |
| R10 | exposure registry may be incomplete | historical overlap audited (section 12.1) | owner decides the rule (D-02, D-08) | yes for the unit-level panel |

## 2. Facts recomputed from the committed files

`unit_pilot_panel.json` (235 groups, 231 provenance clusters). Current proposal, 16 groups, seed 20261121: 16 domains,
13 schema families (largest 4), 9 curators (largest 4), 4 UCI clusters, 7 groups meeting the size floor, 210 holdout
clusters of which 136 meet the floor in every member (the committed 137 counts a cluster as meeting the floor when any
member does; one linked cluster has mixed members, and this document uses the stricter rule). 143 unexposed clusters
meet the floor in every member, per category participation: C1 23, C2a 22, C2b 22, C3 30, C4 14, C5 32, C6 8.
Those 143 are the whole pool from which a floor-eligible statistical pilot and the confirmatory sample must both come.

## 3. Balanced panel allocation (R1)

Procedure (`research/pilot_panel_design.py`, provenance metadata only, one seeded permutation, no search over seeds):

1. Unit: the provenance cluster. A linked set is one unit and counts for its first category in the quotas.
2. Eligible: unexposed and, for the statistical panel, floor met in every member.
3. Quotas: water-filling. Each category gets an equal share; the remainder goes to the categories with most room left.
   This replaces "next place to the category with most ready groups", which is what concentrated panels around C1.
4. Inside a category, scarcest category first, prefer a cluster whose curator is below the cap (25 percent of the
   panel, at least 2), then a domain, a schema family and a curator not yet in the panel, then the seeded order.

| Panel | Clusters per category (C1 C2a C2b C3 C4 C5 C6) | Domains | Schema families (max) | Curators (max) | UCI | Floor met | Holdout clusters | Holdout floor-met |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| current 16 | 4 2 2 2 2 2 2 | 16 | 13 (4) | 9 (4) | 4 | 7 | 210 | 136 |
| balanced 16 | 2 2 2 3 2 3 2 | 16 | 14 (3) | 14 (3) | 3 | 16 | 210 | 127 |
| current 24 | 12 2 2 2 2 2 2 | 20 | 13 (12) | 9 (12) | 12 | 11 | 202 | 132 |
| balanced 24 | 4 3 3 4 3 4 3 | 24 | 20 (5) | 20 (5) | 5 | 24 | 202 | 119 |
| current 32 | 20 2 3 2 2 3 2 | 20 | 13 (20) | 9 (20) | 20 | 15 | 194 | 128 |
| balanced 32 | 5 5 4 5 4 5 4 | 32 | 27 (6) | 25 (6) | 6 | 32 | 194 | 111 |

Larger panels are not inherently less diverse: the current allocation makes them so. Balanced panels keep one group per
domain, and their schema-family and curator maxima are within 3 to 6 at every size. Seed sensitivity of the procedure,
not a search: over seeds 1 to 100 the maximum curator count is 2 to 3 (16), 4 to 5 (24) and 5 to 6 (32).

Retained confirmatory capacity per category after the balanced 16 / 24 / 32 pilot (floor-meeting holdout clusters):
C1 21/19/18, C2a 20/19/17, C2b 20/19/18, C3 27/26/25, C4 12/11/10, C5 29/28/27, C6 6/5/4. C6 (P-NEST) and C4 (P-SEQ)
cannot support a category-specific confirmatory claim at any panel size.

Trade-off. A floor-eligible pilot costs confirmatory capacity because the pilot draws from the same 143 clusters: 9
clusters at 16 (136 to 127), 8 more going to 24 and 8 more to 32. Precision gains shrink: the upper ratio is 1.55, 1.40
and 1.33 (independent sources), so sigma shrinks by 10 percent from 16 to 24 and by 5 percent from 24 to 32. At
sigma-hat 0.10, k = 3 and a confirmatory design effect of 1.3 the requirement falls from 136 to 111 to 101 while
capacity falls from 127 to 119 to 111: 24 turns an infeasible family into a feasible one, 32 gains nothing material.
A 32-group scenario is therefore reported but not recommended. Recommendation: balanced 24, with balanced 16 as the
capacity-preserving alternative. Both stay proposals; the seed is the owner's (D-11).

## 4. Eligibility and transportability of variance (R2)

What `floor` establishes: the recorded partition is the 70/15/15 hash split and 15 percent of the group's units is at
least 1,000, so a structural proxy for "enough test units". It does not establish 20 positives, k of at least 10 at the
1 percent budget, a runnable unit, detector applicability, label or schema validity, or independence. Two groups have
an unknown floor (non-hash partition) and are never counted as met.

Three purposes, kept apart:

| Purpose | Needs | Panel |
|---|---|---|
| technical protocol validation | a runnable unit; size is irrelevant | 7 below-floor clusters, one per category, disjoint from every statistical panel (`technical_validation_panel`); feeds no variance estimate and costs no confirmatory capacity because below-floor clusters never confirm |
| statistical pilot eligibility | the same size floor and exposure rules as the confirmatory population, so the variance is estimated on the population it will size | balanced panel above |
| confirmatory eligibility | floor, protocol-specific adequacy, contrast-specific applicability, not exposed, not pilot-exposed | holdout |

Using the 9 below-floor groups of the current 16 (the two C2b, two C6 and others) to estimate a variance for floor-meeting
clusters would need a justification of transportability that the data cannot supply; they remain valid for technical
validation. Pilot eligibility is a proposal until the owner decides D-12.

## 5. Unit of inference and estimand (R3)

Unit of inference: the provenance cluster. Seeds, mechanisms, severities, injected variants, batches, windows and
multiple category participations are never independent sources.

| Level | Definition |
|---|---|
| detection unit | the protocol's unit: `row`, `time_window`, `event_sequence`, `relationship`, `nested_path` (unit-level study); `temporal_batch` is a different study |
| dataset-level outcome | for one group, one participation and one detector pair: paired difference of recall at the matched 1 percent allowance (k = floor(B x N), same k for both detectors, ties by SHA-256 of the unit id) |
| aggregation inside a group | mean over seeds, then over the registered mechanism-severity cells applicable to the unit, equal weights |
| group outcome | difference of the two detectors' aggregated recall |
| cluster outcome | equal-weight mean of the group outcomes of the cluster's groups, then over the protocols (participations) where the contrast is eligible: each cluster contributes one number |
| primary estimand | the mean of cluster outcomes, equal weight per cluster |
| sensitivity estimand | the mean over categories of the within-category mean of cluster outcomes, each category weighted equally; a cluster in several categories enters each of them and the weights are reported; interpretation: typical category, not typical source |
| missing paired outcome | the cluster leaves that contrast only, with a reason and a count; never imputed; sensitivity analysis shows the effect of dropping |
| contrast-specific eligibility | a cluster is eligible for a contrast if some participation has a runnable unit, both detectors applicable, at least 20 positives and k of at least 10, not exposed, not in a pilot |

The unit-level and temporal-batch studies are never pooled: units, alert budgets (1 and 5 percent) and detector sets
differ. Contrast-specific counts cannot be computed today: the compatibility matrix
(`dataset_registry_v2/compatibility_model.json`) marks only `temporal_batch` runnable and lists no detector for the
protocol-defined units, because the S03 amendments that would define detector applicability do not exist. The 143
floor-meeting clusters are therefore an upper bound on any unit-level contrast, not a count of one. The figures 137 or
143 must not be read as the number available for every comparison.

## 6. Planning-ratio coverage (R4)

`sd_ratio_interval(n, level)` returns multiplicative two-sided bounds of sigma over sigma-hat; its upper end is the
planning ratio r, and sigma = r x sigma-hat is what the confirmatory size uses. The implementation is correct; only the
docstring (which said sigma-hat over sigma) and the prose were wrong. Under independent normal source-level differences
the upper end of a two-sided 95 percent interval is a 97.5 percent one-sided upper bound. The two quantities, and the
two-sided level equivalent to a given ratio, are separate:

| Ratio r | n_eff 16 one-sided / two-sided | n_eff 12 | n_eff 8 |
|---:|---:|---:|---:|
| 1.4 | 93.7% / 87.4% | 89.8% / 79.6% | 82.8% / 65.5% |
| 1.55 | 97.5% / 95.1% | 95.0% / 90.0% | 89.3% / 78.6% |
| 1.7 | 99.0% / 98.1% | 97.5% / 95.0% | 93.3% / 86.6% |

The one-sided column reproduces the assessment's figures. Neither number is an unconditional guarantee of confirmatory
power: both condition on independent normal differences, and the realized sigma-hat is itself random.

Retain r = 1.55 as the provisional planning value and 1.4 and 1.7 as sensitivity scenarios. Proposed sizing rule, after
the authorized pilot (the final choice is the owner's, D-04 and D-15):

1. State the assurance gamma (one-sided; provisional 97.5 percent, equal to the 95 percent two-sided interval).
2. Compute n_eff = floor(n_usable / DE_pilot) from the usable pilot clusters and the pilot's own dependence estimate
   (curator-level variance components), at least 2.
3. r = the upper bound for gamma at n_eff, from the chi-square quantile; sizing sigma = sigma-hat x r.
4. Confirmatory clusters N = `paired_sources(sigma, delta, comparisons=k, design_effect=DE_conf)`.
5. Compare N with the contrast-specific eligible clusters; if N exceeds them, apply the predefined reduction of
   section 11. Never relax gamma, delta or alpha to fit.

## 7. Confirmatory dependence and capacity (R5)

Dependence is applied once at each stage and never twice: pilot dependence only widens r (through n_eff); confirmatory
dependence only inflates N (through DE_conf). A simple design effect does not capture unequal cluster sizes, crossed
curator and schema-family dependence, or heterogeneous variances; it is a sensitivity device, not a model.

Confirmatory clusters needed (delta 0.05, power 0.80, Holm level alpha/k, ratio of the pilot size) against the floor-meeting
holdout of the balanced panel. Plain number: fits the capacity; `*`: fits only if the outcome-exposed clusters of section
12.1a stay eligible; `x`: infeasible. All sigma-hat and DE values are hypothetical scenarios, not measurements.

| Pilot, r, capacity (standard / strict) | sigma-hat | k=1 DE 1.0 | k=1 DE 1.3 | k=3 DE 1.0 | k=3 DE 1.3 | k=11 DE 1.0 | k=11 DE 1.3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 16, 1.55, 127 / 103 | 0.07 | 39 | 51 | 53 | 69 | 68 | 89 |
| | 0.10 | 78 | 102 | 104 * | 136 x | 135 x | 176 x |
| | 0.12 | 111 | 145 x | 148 x | 193 x | 192 x | 250 x |
| 24, 1.40, 119 / 95 | 0.07 | 33 | 43 | 44 | 58 | 57 | 75 |
| | 0.10 | 64 | 84 | 85 | 111 * | 111 * | 145 x |
| | 0.12 | 91 | 119 * | 122 x | 159 x | 157 x | 205 x |
| 32, 1.33, 111 / 87 | 0.07 | 30 | 39 | 40 | 52 | 51 | 67 |
| | 0.10 | 58 | 76 | 77 | 101 * | 100 * | 130 x |
| | 0.12 | 82 | 107 * | 110 * | 143 x | 142 x | 185 x |

(The k = 11 DE 1.0 and DE 1.3 entries at sigma-hat 0.10 and r = 1.55 are 135 and 176 as in the assessment.) A family of 11
is infeasible in most hypothetical scenarios. A family of 3 is infeasible at sigma-hat 0.12 for pilots of 16 and 24 and,
at sigma-hat 0.10 with DE 1.3, for a pilot of 16; at 24 or 32 it fits only while the outcome-exposed clusters stay eligible.
Infeasible comparisons are reported as such, not rescued.

## 8. Primary analysis and its operating characteristics (R6)

The planning model (noncentral t with Bonferroni alpha/k) does not by itself establish the power of a bootstrap
procedure. Proposed primary analysis, to be fixed before any confirmatory outcome:

- Estimator: the mean of cluster outcomes, equal cluster weights (section 5).
- Test and interval: Student t on the cluster outcomes, two-sided, one test per comparison, Holm across the family.
  The percentile cluster bootstrap and a sign-flip permutation test are robustness checks, not the primary.
- Resampling unit: the cluster. A curator-block resampling is the sensitivity analysis for residual dependence.
- Unequal cluster sizes: handled by the cluster outcome; equal weight, with a size-weighted estimate as sensitivity.
- Small samples: below 40 clusters every claim is exploratory.
- Missing pairs: section 5.
- Not restored: the domain plus schema-family mixed model (not identifiable); domain and schema-family effects are
  exploratory, curator is the only factor with several groups per level.

Synthetic simulation (`research/analysis_design_simulation.py`, 2,000 repetitions, 999 resamples, sigma 0.10, effect
0.05, no real data, Monte Carlo error about 0.5 points at 5 percent). Type I error at 5 percent / at the Holm level for
k = 3 (1.67 percent), and power at effect 0.05 at the Holm level:

| Scenario | t | sign-flip | percentile bootstrap | curator bootstrap | power at 0.0167 (t / curator) |
|---|---|---|---|---|---|
| 16 clusters, normal | 4.3 / 1.7 | 4.3 / 1.5 | 7.7 / 3.5 | 7.5 / 3.5 | 29 / 42 |
| 16 clusters, bounded skewed | 9.2 / 4.8 | 9.2 / 4.4 | 10.7 / 6.9 | 10.6 / 6.4 | 17 / 49 |
| 40, heterogeneous variances, unequal sizes | 4.2 / 1.0 | 4.7 / 1.1 | 6.7 / 2.4 | 6.8 / 2.9 | 50 / 56 |
| 80, bounded skewed | 5.5 / 2.3 | 5.6 / 2.5 | 5.9 / 2.4 | 5.7 / 2.5 | 100 / 100 |
| 80, curator dependence, icc 0.2 | 13.9 / 5.8 | 13.7 / 5.6 | 15.1 / 7.2 | 8.0 / 3.5 | 94 / 88 |
| 80, curator dependence, icc 0.5 | 21.4 / 13.4 | 21.4 / 13.0 | 22.9 / 14.6 | 7.0 / 3.3 | 90 / 70 |

Reading. (1) The percentile bootstrap is anti-conservative at 16 clusters (7.7 percent at a nominal 5) and is not the
primary; the t procedure holds its level when differences are roughly symmetric. (2) Skewed bounded differences break
every procedure at 16 clusters and none at 80: small pilots measure variance, they do not test. (3) Residual dependence
between clusters of one curator inflates type I error to 14 to 21 percent for every procedure that ignores it; the
curator-block resampling restores it to 7 to 8 percent at the 5 percent level and 3 to 4 at the Holm level, at a power
cost (90 to 70 percent at icc 0.5). Residual dependence beyond the registry's linked sets is therefore a threat to the
confirmatory claim, not a detail, and the curator-block analysis is a mandatory sensitivity analysis.

## 9. Batch alert budget (R9)

For n exchangeable continuous validation scores the registered threshold is the linear-interpolated 0.95 quantile, a
point between the order statistics j = floor(0.95 (n - 1)) + 1 and j + 1, and a new batch alerts when strictly above it.
Beta(1, n) is the law of the exceedance probability of the sample maximum only. The quantities are distinct:

| Quantity | Value |
|---|---|
| validation batches above the threshold | exactly 1 for 16 to 21 validation batches, 2 for 22 to 40 (deterministic) |
| threshold estimation | an interpolated order statistic: a random variable with the Dirichlet moments of uniform order statistics |
| probability that a new clean batch alerts | 1 - T on the uniform scale; mean 1 - (0.95 (n - 1) + 1) / (n + 1), exact variance from the order-statistic covariance |
| observed false-alert rate on m test batches | threshold uncertainty plus binomial noise, `observed_rate_sd` |
| dependence and ties | temporal dependence lowers the effective n; ties at the top flag nothing under strict inequality |

| Validation batches | mean alert probability | sd | Beta(1, n) mean if the threshold were the maximum |
|---:|---:|---:|---:|
| 16 | 10.3% | 6.7 points | 5.9% |
| 20 | 9.3% | 6.1 | 4.8% |
| 21 | 9.1% | 6.0 | 4.5% |
| 30 | 7.9% | 4.5 | 3.2% |
| 40 | 7.2% | 4.0 | 2.4% |
| 60 | 6.5% | 3.1 | 1.6% |
| 100 | 5.9% | 2.3 | 1.0% |

So a nominal 5 percent budget is exceeded in expectation by a factor of about 1.2 to 2 with 16 to 100 validation batches,
and the realized rate has a standard deviation comparable to the budget itself. The earlier statement in the design
(mean 1/n, sd near 1/n) is corrected in `pilot_statistical_design.md` and the addendum. The registered threshold
implementation is unchanged: a change (for example the order statistic ceil((n + 1) 0.95), the conformal rule) is a
scientific amendment that needs owner authorization, and the batch pilot authorization stays separate from the
unit-level one.

## 10. Smallest effect of interest (R7)

0.05 is an absolute difference of five recall percentage points at the matched alert budget, not a 5 percent relative
improvement. In an ETL setting, with injected faults found within a fixed alert allowance, it means one more injected
defect in twenty is caught for the same review effort. It is a provisional, practically motivated value chosen before
any benchmark outcome. Three claims must not be conflated:

1. H0: difference = 0 (what the analysis tests).
2. Power 0.80 to detect a true difference of 0.05 (what sizing uses).
3. A difference that exceeds 0.05 (a non-inferiority-style superiority margin; not planned, and would need more clusters).

Sensitivity at sigma-hat 0.10, r = 1.55, power 0.80 (clusters, k = 1 and k = 3): delta 0.03: 212 and 283; 0.05: 78 and
104; 0.07: 41 and 55; 0.10: 21 and 29. The threshold is not moved to fit the capacity: at 0.03 the family is infeasible
and is reported as such.

## 11. Multiplicity and hypotheses (R8)

`paired_sources` uses alpha divided by the number of comparisons. That is the first (most stringent) step of Holm, a
conservative planning approximation: later Holm steps have more power, so the sizing is exact for the smallest p-value and
conservative for the rest.

The registered design (`variance_pilot_design.md` 11.3 to 11.6) defines F1 (three detector-family contrasts on recall at
the matched 1 percent budget: rule-based against classical, classical against neural, rule-based against neural), F2 (rule-based
against the best prespecified learned family inside each of the five protocols), F5 (cost, three contrasts, hardware fixed).

| Family | Contents | Status | k |
|---|---|---|---:|
| primary candidate A | F1 contrast 1: rule-based against classical machine learning | confirmatory if feasible | 1 |
| primary candidate B | all three F1 contrasts | confirmatory if feasible | 3 |
| secondary | F2 per protocol, F5 cost, burden, AUPRC | exploratory unless separately powered and authorized; own Holm adjustment, labelled | up to 11 as sensitivity |

Selection rule, fixed before any confirmatory outcome and independent of observed detector rankings: use B if its required
clusters (section 6) do not exceed the contrast-specific eligible clusters; otherwise use A; if A is infeasible, no
confirmatory claim is made and F1 is reported as exploratory. The rule uses only the pilot's sigma-hat, the dependence
estimate and the eligible counts. No detector or dataset is dropped from the evaluation: confirmatory status only decides
which comparisons are tested with a familywise guarantee. Exploratory comparisons are reported in full with their
multiplicity treatment and a statement that they carry no familywise guarantee.

## 12. Exposure and contamination (R10)

### 12.1 Historical overlap

`linked_sets.json` records five exposed groups (the C3 UCI plumbing groups). The registry's UCI groups are also rows of
the earlier labelled-pool benchmark (`dataset_registry/uci_pool.json`, `labelled_pool/labelled_results.json`), where
detectors ran on native labels and outcomes were reported. Groups of the 235-group registry that appear there:

| Role in the earlier pool | Registry groups | In current 16 / 24 / 32 panel |
|---|---:|---|
| `labelled` (detector outcomes on native labels; includes `uci:193`, the cardio dataset of the principal benchmark) | 30 | 3 (`uci:267`, `uci:292`, `uci:296`) / 7 / 10 |
| `carrier` only (injection input of the typed-injection study, which retained 42 of its carriers) | 21 | not computed |

This exposure is study-specific (different unit, native rather than injected faults, different protocol) and the registry
does not record it. It is not automatically exposure under the unit-level protocols, but it is outcome exposure of the
kind the pilot is meant to avoid. The existing rules are preserved until amended; as a scenario, treating the 30 labelled
groups as exposed for both pilot and confirmation lowers the retained floor-meeting holdout to 114 / 106 / 98 clusters
(balanced 16 / 24 / 32), mostly in C1 (21 to 10 at 16). Decision D-02 and D-08 are widened accordingly. The 5 plumbing
groups, the cross-study rule and the Cincinnati link stay as recommended: exclude the five from the statistical pilot and
confirmation, forbid a cluster in both pilots, exclude a cluster from the other study's confirmatory set when exposed, and
treat Cincinnati calls and fire dispatch as linked until evidence says otherwise (they already share a cluster).

Harmless metadata and authorized structural validation (units, partitions, schema) are not outcome exposure; reading a
detector output, a recall or a label-derived score is.

### 12.1a Reconciled inventory (2026-11-27, supersedes the 30-group figures above)

The first overlap matched only registry groups literally named `uci:N`. `research/exposure_inventory.py` reads the file
names of twelve earlier study folders under `verification/evidence` (no result is opened), maps UCI identifiers to
groups through both group names and readiness facts, and counts each group once.

| Class | Groups | Clusters |
|---|---:|---:|
| `plumbing` (registry `exposed_groups`; all five also appear in earlier studies, `candanedo_umons` in the labelled pool) | 5 | 5 |
| `outcome` (an earlier study produced detector outcomes on the dataset; not plumbing) | 52 | 52 |
| `structure` only (partitions, no outcome) | 0 | 0 |
| outcome-exposed in total | 57 | 57 |

The studies are the labelled pool, typed injection, typed train-only, the train-only replay, the pool extensions v1 to v3
(chronological, typed-mixed, ETL repair, schema rules), the alert-budget study, the full registry run, the pipeline-level
pilot and the natural temporal study. The 30 groups named `uci:N` were a subset; 22 more groups are exposed through named
registry groups or through the later studies. Floor-meeting unexposed clusters: 143 when every member meets the floor,
144 when any member does (the committed holdout counts 137 and 136 are these numbers minus the 7 floor-meeting groups of
the 16-group proposal; the difference is one linked cluster with mixed members, and this document uses the stricter rule).

Under the registry rule the balanced holdout keeps 127 / 119 / 111 floor-meeting clusters (16 / 24 / 32). If every
outcome-exposed cluster is treated as unavailable for confirmation (a provisional planning rule, not an approval), it keeps
103 / 95 / 87. These are structural upper bounds before contrast-specific eligibility. Outcome generation is established
by file names and the thesis documents; that outcomes influenced a current design decision is established only for the
five plumbing groups (Amendment 1). The other 52 are recorded with their studies in `exposure_inventory.json` so the owner
can set a rule per study (D-02, D-08), for example exposure by studies that produced typed-injection outcomes only.

### 12.2 Reproduction

```
python research/pilot_panel_design.py --output verification/evidence/dataset_registry_v2/pilot_panel_alternatives.json
python research/exposure_inventory.py --output verification/evidence/dataset_registry_v2/exposure_inventory.json
python research/analysis_design_simulation.py --output verification/evidence/dataset_registry_v2/analysis_design_simulation.json
```

Both are deterministic (default seeds 20261121 and 2026) and read no detector output. Focused mutation measurements:
`docs/thesis-remediation/evidence/focused-statistical-remediation-2026-11-27/measurement.json`.

## 13. Limits

Not checked: contrast-specific eligible counts (no detector applicability exists for the protocol-defined units), the
normality and independence of real source-level differences, whether any group outside the historical pool was exposed by
other work, and the validity of a design effect for crossed dependence. The simulations use one sigma (0.10); the
conclusions about the t procedure and about curator dependence do not depend on its value, the power figures do.
