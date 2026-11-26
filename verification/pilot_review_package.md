# Pilot statistical design: reviewer package and owner decision brief (#153, #154)

Status: prepared for an independent statistical reviewer and for the owner. It is not a review, an approval or an
authorization. The experiment freeze stays active. The design under review is
[`pilot_statistical_design.md`](pilot_statistical_design.md).

## 1. Facts re-derived from the committed artifacts (2026-11-26)

These are deterministic recomputations by the author of the package, not review findings.

| Statement in the design | Recomputed from | Result |
|---|---|---|
| Upper SD ratio table (section 5), n = 16, 24, 32, DE 1.0 to 3.0 | `effective_sd_interval` in `research/target_framework.py` | all 15 values match to two decimals |
| Confirmatory sources for effect 0.05, power 0.80, Holm k = 1, 3, 11 (section 5) | `paired_sources(sigma, 0.05, comparisons=k)` | all 12 values match (33/44/57, 47/63/81, 64/85/111, 93/124/161) |
| 16-group panel: 16 domain levels (1 group each), 13 schema families (largest 4), 9 curators (largest 4) | `plans["16"]["pilot"]` joined to `table` in `verification/evidence/dataset_registry_v2/unit_pilot_panel.json` | matches |
| No exposed group in the panel; 5 exposed groups in the registry | same file, field `exposed` | 0 in the panel, 5 in the table |
| k up to 11 is supportable at r = 1.4 against 137 floor-meeting clusters | required 57 (sigma-hat 0.07) and 111 (0.10), both below 137 | consistent |
| k = 11 fails at sigma-hat 0.10, r = 1.7 | required 161 against 137 | consistent |

Not re-derived: the 210 and 137 cluster counts of the holdout (`variance_pilot_design.md` 13.2), the batch population
figure of 34 to 36 confirmatory clusters, and the normality of source-level differences.

## 1a. The planning ratio, defined

`sd_ratio_interval(n, level)` in `research/target_framework.py` is the chi-square interval for sigma-hat / sigma from n
independent normal source-level differences; the upper ratio used in sizing is its inverse, the largest plausible
sigma divided by the estimate: sqrt((n-1) / chi2_{alpha/2}(n-1)). `effective_sd_interval(n, DE)` uses
floor(n / DE) effective sources instead of n, with a floor of two. The numerators and denominators of the tabulated
ratio (1.55 at n = 16, DE 1.0) and of the planning ratio r = 1.4 are therefore the same quantity: sigma-hat times r is
the sigma the confirmatory size is computed with.

They differ in assurance. Recomputed with the same function:

| Pilot n | two-sided 80 percent | 90 percent | 95 percent (the table) |
|---:|---:|---:|---:|
| 16 | 1.32 | 1.44 | 1.55 |
| 24 | 1.24 | 1.33 | 1.40 |
| 32 | 1.20 | 1.27 | 1.33 |

At n = 16 the ratio 1.4 corresponds to a two-sided level of about 87 percent (a one-sided upper bound of about 94
percent), not 95 percent; at n = 24 independent sources it is the 95 percent figure. So 1.4 is defensible as a planning
value only if it is described as an upper bound with that lower assurance, or if the pilot has at least 24 independent
(effective) sources; with a design effect above 1 the effective size falls (floor(16 / 1.3) = 12 gives 1.70). The
document's section 5 table is correct; the sentence that the plan "uses the upper end of the SD interval" is correct
only for the 95 percent column.

Effect on confirmatory capacity (paired sources for effect 0.05, power 0.80, Holm k = 1, 3, 11, against 137
floor-meeting clusters in the unit-level holdout):

| sigma-hat | r | k = 1 | k = 3 | k = 11 | k = 11 fits 137 |
|---:|---:|---:|---:|---:|---|
| 0.07 | 1.4 | 33 | 44 | 57 | yes |
| 0.07 | 1.55 | 39 | 53 | 68 | yes |
| 0.07 | 1.7 | 47 | 63 | 81 | yes |
| 0.10 | 1.4 | 64 | 85 | 111 | yes |
| 0.10 | 1.55 | 78 | 104 | 135 | yes, by 2 clusters |
| 0.10 | 1.7 | 93 | 124 | 161 | no |

Reading: moving from 1.4 to the 95 percent value for n = 16 (1.55) raises the requirement by 18 to 22 percent and keeps
every scenario but sigma-hat 0.10 with k = 11 comfortably inside the holdout; a larger pilot (24 groups, ratio 1.40 at 95
percent when sources are independent) removes the gap but adds C1 groups from one curator and no information on the
unidentified factors (design section 4), and the design effect applies on top. The numerical comparison alone therefore
proves no invalidity; it shows that the proposed 1.4 is an optimistic choice for n = 16 that the owner should either
accept knowingly (decision 4) or replace by 1.55.

## 2. Questions for the independent reviewer

1. Is the experimental unit (provenance group, clustered by linked set) the right unit for the pilot estimands?
2. Is dropping the registered domain plus schema-family mixed model justified by the identifiability table
   (16 domain levels with one group each)? Is the cluster bootstrap on paired per-cluster differences adequate with
   16 clusters, or is a small-sample correction needed?
3. The interval for sigma uses a design effect (1.0 to 3.0) that is hypothetical. Is 1.4 a defensible planning ratio,
   or should the plan use the DE 2.0 column (2.04 at n = 16)?
4. Selection: the panel is drawn with a seed over eligible groups after excluding five exposed groups. Does exclusion
   bias the pilot sigma-hat (the excluded groups are all C3 UCI time series)?
5. Pilot and confirmatory separation: is "pilot-exposed groups are excluded from the confirmatory holdout" enough to
   prevent selection-on-the-outcome, given that the pilot also informs the sizing sigma?
6. Multiplicity: is a Holm family of at most 11 comparisons the right ceiling, and should it be fixed before the pilot?
7. Pooling: are pooled analyses across categories valid when no single category meets the sample-size figures
   (8 to 30 floor-meeting groups each)? What may be stated if only the pooled claim is powered?
8. Interpretation rules: how must a negative or inconclusive pilot be reported so it neither supports nor refutes the
   confirmatory hypotheses?
9. Is the smallest effect of interest 0.05 justified by the thesis claims or only a convenient value?

## 3. Risks the reviewer should weigh

- Pseudoreplication through linked sets: handled by clustering, but the linkage itself (Cincinnati pair) is undecided.
- Pilot sigma-hat from 16 sources is itself very uncertain (upper ratio 1.55 at DE 1.0); the plan depends on it.
- Domain effects are not identifiable; any domain-specific statement is exploratory.
- Cross-study exposure between the unit-level and batch pilots is unresolved (decisions 5 and 6).
- The planning ratio 1.4 does not carry the stated 95 percent assurance at n = 16 (section 1a); this is a precision of wording and of choice, not an arithmetic error.
- All sample sizes assume independent, normal source-level differences.

## 4. Owner decisions (design section 7) with a recommendation

Statistical recommendations only; every item stays the owner's decision.

| # | Decision | Options | Recommended | Rationale and cost |
|---|---|---|---|---|
| 1 | Unit-level pilot size | 16, 24, 32 | 16 | 24 and 32 add C1 groups from one curator and no information on the unidentified factors; only 16 keeps one group per domain and the largest family at 4. Smaller n widens sigma (ratio 1.55 against 1.40 at 24). |
| 1 | Exposure rule for the five plumbing groups | exclude from both sides; allow in the pilot with a sensitivity analysis | exclude | They informed Amendment 1, so using them confirmatorily would contaminate the result; the panel already excludes them. |
| 3 | Primary analysis | cluster bootstrap; mixed model with a curator effect | cluster bootstrap | A mixed model needs a dependency decision (ADR-0001) and the domain effect is unestimable anyway. |
| 4 | Planning ratio r, smallest effect, Holm family | r 1.4, 1.55 or 1.7; effect 0.05; k up to 11 | r 1.55 (the 95 percent value at n = 16, DE 1.0), and report 1.4 and 1.7 beside it | 1.4 is only about 87 percent two-sided at n = 16 (section 1a); 1.55 costs 18 to 22 percent more confirmatory sources and still fits the holdout in every tabulated scenario; 1.7 (DE 1.3) is the conservative bound and fails only at sigma-hat 0.10 with k = 11. |
| 5, 6 | Cluster in both pilots; cross-study exposure | allow or forbid | forbid in both | Keeps exposure bookkeeping simple and the confirmatory sets clean at a small cost in available clusters. |
| 7 | Cincinnati calls and fire dispatch linked | linked or independent | linked until evidence says otherwise | Treating dependent groups as independent inflates the effective sample. |
| 2, 8 | Batch contrasts, sizing rule, seed, floors, freeze date | see design section 7 | no recommendation | They are protocol choices with no statistical default; the seed must be drawn and recorded by the owner. |

Dependencies: #154 (protocol amendments for new execution pathways) and the runners #135 to #139 depend on decisions
1 to 4; no runner may be used on frozen data before an authorization gate separate from approving this design and from
approving a confirmatory sample size.

## 5. What closes #153

The acceptance criterion "documented, reviewed design" closes only with a recorded review by an independent human
statistician or a reviewer the repository governance recognizes. Nothing in this file is that record.

## 6. Standalone prompt for an independent reviewer

Give a reviewer this section and the three files named in it; nothing else is needed.

> You are asked for an independent statistical review of a pilot design for a benchmark of anomaly detectors on
> heterogeneous data sources. Files: `verification/pilot_statistical_design.md` (the design),
> `verification/pilot_review_package.md` (this package, sections 1 to 4), `research/target_framework.py` (the
> calculations: `sd_ratio_interval`, `effective_sd_interval`, `paired_sources`) and
> `verification/evidence/dataset_registry_v2/unit_pilot_panel.json` (the 16-group panel). The experimental unit is a
> provenance group (clustered by linked set); the outcome is a paired per-source difference between two detectors.
> Review: the unit definition and independence assumptions; provenance grouping and cluster dependence; exposure and
> contamination controls; the pilot selection and its bias; domain, schema-family and curator representation (16
> domains with one group each); variance estimation and the use of the upper endpoint of a chi-square interval, with
> and without a design effect; the effect size 0.05 and power 0.80; Holm correction and the ceiling of 11
> comparisons; pseudoreplication; the validity of pooled analyses across categories; generalization limits; the
> separation of pilot and confirmatory objectives; reproducibility of the calculations; and how negative or
> inconclusive results must be reported. For each point state: sound, sound with a stated limitation, or unsound, with
> the evidence. Do not approve anything on behalf of the project owner: approving the design, authorizing a pilot and
> approving a confirmatory sample size are three separate owner decisions. Answer with a numbered list of findings,
> each tagged blocking or non-blocking, and a final recommendation among accept, accept with changes, or reject.
