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
- The proposed planning ratio 1.4 is below the n = 16 interval at every tabulated design effect (1.55 to 2.87).
- All sample sizes assume independent, normal source-level differences.

## 4. Owner decisions (design section 7) with a recommendation

Statistical recommendations only; every item stays the owner's decision.

| # | Decision | Options | Recommended | Rationale and cost |
|---|---|---|---|---|
| 1 | Unit-level pilot size | 16, 24, 32 | 16 | 24 and 32 add C1 groups from one curator and no information on the unidentified factors; only 16 keeps one group per domain and the largest family at 4. Smaller n widens sigma (ratio 1.55 against 1.40 at 24). |
| 1 | Exposure rule for the five plumbing groups | exclude from both sides; allow in the pilot with a sensitivity analysis | exclude | They informed Amendment 1, so using them confirmatorily would contaminate the result; the panel already excludes them. |
| 3 | Primary analysis | cluster bootstrap; mixed model with a curator effect | cluster bootstrap | A mixed model needs a dependency decision (ADR-0001) and the domain effect is unestimable anyway. |
| 4 | Planning ratio r, smallest effect, Holm family | r 1.4 or 1.7; effect 0.05; k up to 11 | plan with r 1.7 for a 16-group pilot and report 1.4 beside it | The interval computed for n = 16 is 1.55 at DE 1.0 and 1.70 at DE 1.3, so r = 1.4 is below it at every design effect; 1.4 is reached only at n = 24 with DE 1.0 or n = 32 with DE 1.3. Planning with 1.4 on a 16-group pilot is optimistic. |
| 5, 6 | Cluster in both pilots; cross-study exposure | allow or forbid | forbid in both | Keeps exposure bookkeeping simple and the confirmatory sets clean at a small cost in available clusters. |
| 7 | Cincinnati calls and fire dispatch linked | linked or independent | linked until evidence says otherwise | Treating dependent groups as independent inflates the effective sample. |
| 2, 8 | Batch contrasts, sizing rule, seed, floors, freeze date | see design section 7 | no recommendation | They are protocol choices with no statistical default; the seed must be drawn and recorded by the owner. |

Dependencies: #154 (protocol amendments for new execution pathways) and the runners #135 to #139 depend on decisions
1 to 4; no runner may be used on frozen data before an authorization gate separate from approving this design and from
approving a confirmatory sample size.

## 5. What closes #153

The acceptance criterion "documented, reviewed design" closes only with a recorded review by an independent human
statistician or a reviewer the repository governance recognizes. Nothing in this file is that record.
