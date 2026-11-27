# Owner decision package (#154, with #153)

Status: prepared 2026-11-27 for the owner. It is not an approval, not an authorization record and not a review. The
experiment freeze stays active. Nothing below was run on benchmark data; every number is recomputed from
`research/target_framework.py` (`sd_ratio_interval`, `effective_sd_interval`, `paired_sources`) and from the committed
panel `verification/evidence/dataset_registry_v2/unit_pilot_panel.json`.

Three gates stay separate: approving the design (#153), authorizing a pilot, and approving a confirmatory sample size.
Approving a unit definition (S03, #154) is a fourth, independent gate. The independent statistical review (#153) has not
been performed; its standalone prompt is section 6 of [`verification/pilot_review_package.md`](../../verification/pilot_review_package.md).

## 1. The planning ratio, verified

The ratio r multiplies the pilot estimate: the confirmatory size is computed with sigma = sigma-hat x r. The table
`effective_sd_interval` gives r = sqrt((n-1) / chi2_{alpha/2}(n-1)) for n effective sources. Assurance below is the
probability that the true sigma lies below sigma-hat x r when the source differences are independent and normal
(two-sided level 1-alpha; the one-sided bound is in brackets). The design effect DE reduces n to floor(n / DE).

| Pilot sources, DE | effective n | r = 1.4 | r = 1.55 (provisional) | r = 1.7 |
|---|---:|---:|---:|---:|
| 16, 1.0 | 16 | 87.4% (93.7%) | 95.1% (97.5%) | 98.1% (99.0%) |
| 16, 1.3 | 12 | 79.6% (89.8%) | 90.0% (95.0%) | 95.0% (97.5%) |
| 16, 2.0 | 8 | 65.5% (82.8%) | 78.6% (89.3%) | 86.6% (93.3%) |
| 24, 1.0 | 24 | 94.9% (97.4%) | 98.7% (99.4%) | 99.7% (99.8%) |

Confirmatory sources for effect 0.05, power 0.80, Holm family k (`paired_sources`), against 137 clusters that meet the
1,000-test-unit floor in the unit-level holdout:

| sigma-hat | r | k = 1 | k = 3 | k = 11 | k = 11 fits 137 |
|---:|---:|---:|---:|---:|---|
| 0.07 | 1.4 | 33 | 44 | 57 | yes |
| 0.07 | 1.55 | 39 | 53 | 68 | yes |
| 0.07 | 1.7 | 47 | 63 | 81 | yes |
| 0.10 | 1.4 | 64 | 85 | 111 | yes |
| 0.10 | 1.55 | 78 | 104 | 135 | yes, by 2 clusters |
| 0.10 | 1.7 | 93 | 124 | 161 | no |
| 0.12 | 1.4 | 91 | 122 | 157 | no |
| 0.12 | 1.55 | 111 | 148 | 192 | no |
| 0.12 | 1.7 | 133 | 178 | 230 | no |

Reading. 1.4 is an optimistic choice at 16 sources (87% two-sided, 80% if DE is 1.3). 1.55 is the 95% value at DE 1.0
and still about 90% at DE 1.3. 1.7 is 95% at DE 1.3. Moving from 1.4 to 1.55 raises the requirement by 18 to 22
percent. A larger sigma-hat (0.12) makes k = 11 infeasible whatever the ratio, so the Holm ceiling and the pooled claim
must be re-decided after the pilot, not before. The ratio was not chosen to maximize feasible comparisons; 1.55 is
provisional planning input only and the independent review must judge it.

## 2. Facts re-checked against the panel file

16 groups, 16 domain levels (one group each), 13 schema families (largest 4), 9 curators (largest 4), 0 exposed groups
in the panel; 5 exposed groups in the registry (all C3, UCI). A domain effect is therefore not identifiable from the pilot
and any domain statement stays exploratory; curator is the only factor with several groups per level.

## 3. Decisions

Each decision is the owner's. "Authorizes" and "does not authorize" are literal.

| ID | Question | Options | Recommended | Rationale | Authorizes | Does not authorize | Review first |
|---|---|---|---|---|---|---|---|
| D-01 | Unit-level pilot size | 16, 24, 32 | 16 | one group per domain, largest family 4; 24 and 32 add C1 groups from one curator and no information on unidentified factors; cost is a wider sigma (r 1.55 vs 1.40 at 24) | the panel size | running it | yes (#153) |
| D-02 | Exposure rule for the five plumbing groups | exclude from both sides; allow in the pilot with sensitivity | exclude | they informed Amendment 1; the panel already excludes them | the exclusion rule | any use of them | no |
| D-03 | Primary analysis | cluster bootstrap on per-cluster paired differences; mixed model with curator effect | cluster bootstrap | the domain effect is unestimable; a mixed model needs a dependency decision (ADR-0001) | the estimator | a result | yes (#153) |
| D-04 | Planning ratio r | 1.4, 1.55, 1.7 | 1.55, with 1.4 and 1.7 reported as sensitivity | section 1 | the value used in sizing tables | a confirmatory size | yes (#153) |
| D-05 | Smallest effect of interest | 0.05, other | 0.05 if the thesis claims justify it; otherwise state the claim first | only a convenient value so far | the effect in sizing | a claim | yes (#153) |
| D-06 | Holm family ceiling | k up to 11, smaller | up to 11, revisit after sigma-hat | k = 11 fails at sigma-hat 0.12 for every r | the family limit | adding comparisons later | yes (#153) |
| D-07 | Cluster in both pilots | allow, forbid | forbid | simple exposure bookkeeping, small cost in clusters | the rule | nothing else | no |
| D-08 | Cross-study exposure | exposure in one study excludes the group from the other's confirmatory set: yes, no | yes | keeps confirmatory sets clean | the rule | nothing else | no |
| D-09 | Cincinnati calls and fire dispatch | linked, independent | linked until evidence says otherwise | independent treatment inflates the effective sample | the cluster definition | nothing else | no |
| D-10 | Batch pilot (T424): contrasts (at most 3), sizing sigma rule, P, M, seed, exposed groups | see design section 7 | no statistical default | protocol choices | the batch plan | running it | yes (#153) |
| D-11 | Seed and sampling procedure for the unit-level panel | owner draws and records a seed | owner-drawn | the seed must be recorded by the owner | the panel | running it | no |
| D-12 | Floors: 15 percent test share, 20 positives, k at least 10; pilot eligibility | accept, change | accept | they define when a group can count | the floors | inclusion of a specific group | yes (#153) |
| D-13 | Experimental unit per protocol: P-TAB `row`, P-TS `time_window`, P-SEQ `event_sequence` (provisional `event_window`), P-REL `relationship` (provisional `relational_load`), P-NEST `nested_path` (provisional `document_batch`) | approve the protocol-defined unit; approve the provisional one; keep the registered `temporal_batch` only | approve the protocol-defined unit per protocol, one dated amendment each (S03) | the provisional units have no ground truth, metrics or operators yet | scientific use of that unit by its runner | execution | no |
| D-14 | Pilot execution | authorize, defer | defer until D-01 to D-12 and the review are recorded | separate gate | a pilot run | confirmatory run | n/a |
| D-15 | Confirmatory sample size | approve after the pilot | after the pilot | sigma-hat is what the pilot measures | the size | the run | n/a |
| D-16 | Evaluation and inclusion boundaries | per-category and pooled claims; negative or inconclusive pilots reported without supporting or refuting the confirmatory hypotheses | pooled claim only where powered, categories exploratory | no category alone meets the figures (8 to 30 floor-meeting groups each) | the reporting rule | nothing else | yes (#153) |
| D-17 | Lifting the freeze for a pilot | date and conditions | lift only after D-01 to D-13, D-14 and the review are recorded | the freeze guards the confirmatory sets | the lift | the confirmatory run | n/a |

## 4. Dependencies

Runners #135 to #139 may be built and tested on synthetic fixtures now (see [ENGINE_PERMISSIONS.md](ENGINE_PERMISSIONS.md));
their scientific use waits for D-13. #153 closes only with a recorded independent review. #154 closes with one dated
amendment per approved unit type. D-14 and D-17 depend on D-01 to D-13 and on the review.

## 5. Owner response template

Copy, fill in, and record in the repository yourself; nothing here creates an approval.

```
D-01: approve 16 | 24 | 32 | modify: ...
D-02: approve exclude | allow | modify: ...
D-03: approve cluster bootstrap | mixed model | modify: ...
D-04: approve 1.4 | 1.55 | 1.7 | modify: ...
D-05: approve 0.05 | modify: ...
D-06: approve k<=11 | modify: ...
D-07: approve forbid | allow
D-08: approve yes | no
D-09: approve linked | independent
D-10: approve | modify: ... (contrasts, sigma rule, P, M, seed, exposed groups)
D-11: seed = ...
D-12: approve | modify: ...
D-13: per protocol P-TAB / P-TS / P-SEQ / P-REL / P-NEST: protocol unit | provisional unit | registered batch only
D-14: authorize pilot on <date> | defer
D-15: after pilot
D-16: approve | modify: ...
D-17: lift on <date> | keep
```
