# Owner decision package (#154, with #153)

Status: revised 2026-11-27 after a separate, model-assisted methodological assessment (verdict "accept with changes").
It is not an approval, not an authorization record and not the independent review that #153 requires (that needs an
independent human statistician or a reviewer the repository governance recognizes). The experiment freeze stays active.
Nothing here was run on benchmark data. Every recommendation below is methodological advice, not an owner approval.

Four gates stay separate: approving the design (#153), approving a unit definition (S03, #154), authorizing a pilot, and
approving a confirmatory sample size. Details and calculations:
[`verification/pilot_statistical_remediation.md`](../../verification/pilot_statistical_remediation.md); unit
specifications: [`verification/unit_amendment_proposals.md`](../../verification/unit_amendment_proposals.md).

## 1. What changed since the previous package

- The coverage wording is corrected. The planning ratio r = 1.55 is the upper end of a two-sided 95 percent interval, a
  97.5 percent one-sided upper bound at 16 effective clusters; 1.4 is 93.7 percent one-sided and 87.4 percent two-sided.
  Neither is a guarantee of confirmatory power.
- The largest-pool allocation concentrated larger panels. A balanced allocation (equal category shares, curator cap, new
  domain, schema family and curator first) gives 16 floor-eligible clusters with one group per domain and at most 3 per
  curator, at a cost of 9 confirmatory clusters.
- The pilot should draw from floor-meeting clusters; only 7 of the 16 current groups do.
- A family of 11 comparisons is infeasible in most scenarios; one or three primary comparisons are prepared.
- The batch alert budget is not Beta(1, n); the expected false-alert probability at 16 to 100 validation batches is 10.3
  to 5.9 percent, not 5.
- 30 UCI groups of the registry were rows with detector outcomes in the earlier pool benchmark and are not recorded as
  exposed; three of them are in the current 16-group proposal.
- The percentile bootstrap is anti-conservative at 16 clusters; residual curator dependence inflates type I error to
  14 to 21 percent unless curator-block resampling is used.

## 2. Decisions

Readiness: **ready for owner approval** = no further methodological work; **needs review** = the independent review of
#153 should look at it first; **separate gate** = depends on other decisions.

### D-01 Unit-level pilot size

- Question: how many provenance clusters in the statistical pilot, and drawn how?
- Options: 16, 24, 32; current allocation or balanced allocation.
- Recommended: balanced allocation, 24 clusters (balanced 16 if capacity matters more than sigma precision); not 32.
- Evidence: balanced 16 / 24 / 32 keep one group per domain, max curator 3 / 5 / 6, retain 127 / 119 / 111 floor-meeting
  holdout clusters (current 16: 136). The upper ratio is 1.55 / 1.40 / 1.33. At sigma-hat 0.10, k = 3, DE 1.3 the
  requirement is 136 / 111 / 101: 24 makes the family feasible, 32 adds nothing material.
- Limits: the floor is a structural proxy; C4 and C6 have 14 and 8 eligible clusters, so no panel supports a C4- or
  C6-specific confirmatory claim.
- Depends on: D-02, D-07, D-08, D-12; D-11 for the seed.
- Authorizes: the size and allocation rule. Does not authorize: running the pilot, or any group.
- Readiness: needs review.

### D-02 Exposure rule for the plumbing groups

- Question: what happens to the five groups that informed Amendment 1 (`airquality_italy`, `candanedo_umons`,
  `seoul_bike`, `steel_korea`, `tetouan_power`)?
- Options: exclude from pilot and confirmation; allow in the pilot with a sensitivity analysis.
- Recommended: exclude from both. Also decide the new question below.
- Evidence: they are the only groups the registry records as exposed. The earlier pool benchmark ran detectors on 30
  other registry groups (including `uci:193`, the cardio dataset); they are in none of the registry's exposure lists.
  Treating them as exposed lowers the floor-meeting holdout to 114 / 106 / 98 (balanced 16 / 24 / 32).
- Limits: the pool exposure is study-specific (native labels, another unit and protocol).
- Depends on: D-08. Authorizes: the exclusion rule and, if chosen, the wider rule for the 30 groups. Does not authorize: any use.
- Readiness: ready for owner approval; the 30-group rule is an additional choice (exclude: recommended for the confirmatory set).

### D-03 Primary analysis

- Question: which estimator, test and resampling unit?
- Options: Student t on cluster outcomes; percentile cluster bootstrap; sign-flip permutation; mixed model with a curator
  effect.
- Recommended: equal-weight mean of cluster outcomes with Student t and Holm across the family; curator-block resampling
  as a mandatory sensitivity analysis; percentile bootstrap and permutation as robustness checks.
- Evidence: simulations (2,000 repetitions): t holds 4.2 to 5.5 percent at 5 percent in the normal, heterogeneous and
  80-cluster skewed cases (9.2 for 16 skewed clusters, where no procedure holds); the percentile bootstrap gives 7.7 percent at 16 clusters; dependence at icc 0.2 / 0.5 gives 14 / 21 percent for the
  procedures that ignore it and 8 / 7 percent with curator blocks.
- Limits: synthetic data, one sigma; the domain plus schema-family model stays unidentifiable and exploratory.
- Depends on: D-06. Authorizes: the estimator. Does not authorize: a result.
- Readiness: needs review.

### D-04 Planning ratio and sizing rule

- Question: which ratio r, and which rule turns pilot variance into a confirmatory size?
- Options: 1.4, 1.55, 1.7; fixed ratio or an assurance-based rule.
- Recommended: 1.55 provisionally (1.4 and 1.7 as sensitivity); after the pilot, choose the one-sided assurance (97.5
  percent provisional), compute n_eff from the usable clusters and the pilot dependence, and size with sigma-hat x r.
- Evidence: coverage table in the remediation section 6; the calculation was correct, only the wording was wrong.
- Limits: independent normal differences; the realized sigma-hat is random.
- Depends on: D-01, D-06. Authorizes: the planning input. Does not authorize: a confirmatory size (that is D-15).
- Readiness: needs review.

### D-05 Smallest effect of interest

- Question: which effect is sized for?
- Options: 0.05, other.
- Recommended: 0.05, provisionally. It means five recall percentage points at the matched 1 percent budget (one more
  injected defect in twenty caught for the same review effort), not a 5 percent relative gain.
- Evidence: requirements at sigma-hat 0.10, r = 1.55: delta 0.03: 212 / 283 clusters (k = 1 / 3), 0.05: 78 / 104, 0.07:
  41 / 55, 0.10: 21 / 29. Testing zero, detecting 0.05 with power 0.80 and showing an effect above 0.05 are three
  different claims; only the first two are planned.
- Limits: the value is not yet justified by a thesis claim beyond practical relevance; it must be fixed before any outcome.
- Authorizes: the effect used in sizing. Does not authorize: a claim. Readiness: needs review.

### D-06 Confirmatory family

- Question: how many primary comparisons?
- Options: 1, 3, up to 11.
- Recommended: at most 3: A = rule-based against classical machine learning (k = 1), B = the three F1 contrasts (k = 3);
  use B if its required clusters fit the contrast-specific eligible clusters, else A, else no confirmatory claim.
  F2, F5, burden and AUPRC are exploratory with their own multiplicity treatment. 11 is a sensitivity scenario only.
- Evidence: k = 11 fits only at sigma-hat 0.07; k = 3 is feasible at 0.10 with DE 1.0 and, at 24 clusters, with DE 1.3.
- Limits: contrast-specific eligible counts do not exist yet (no detector applicability for the protocol-defined units).
- Authorizes: the family limit and the selection rule. Does not authorize: adding comparisons later, or dropping a
  detector or dataset from the evaluation. Readiness: needs review.

### D-07 Cluster in both pilots

- Question: may a provenance cluster be in the unit-level and the batch pilot?
- Options: allow, forbid. Recommended: forbid. Evidence: simple exposure bookkeeping, small capacity cost.
- Authorizes: the rule. Does not authorize: anything else. Readiness: ready for owner approval.

### D-08 Cross-study exposure

- Question: does exposure in one study exclude a cluster from the other study's confirmatory set?
- Options: yes, no. Recommended: yes, applied at the cluster level. Evidence: keeps confirmatory sets clean.
- Limits: it interacts with the 30-group question of D-02.
- Authorizes: the rule. Does not authorize: anything else. Readiness: ready for owner approval.

### D-09 Cincinnati sources

- Question: are Cincinnati emergency calls and fire dispatch one source?
- Options: linked, independent. Recommended: linked until evidence supports independence.
- Evidence: the registry already draws them as one cluster (candidate link); independent treatment inflates the effective sample.
- Authorizes: the cluster definition. Does not authorize: anything else. Readiness: ready for owner approval.

### D-10 Batch pilot (T424)

- Question: contrasts (at most three), sizing rule, pilot size, minimum, seed, exposed groups for the batch study.
- Recommended: defer the final batch design until its specification and calibration assumptions are verified.
- Evidence: the alert budget is a target, not an achieved rate (10.3 percent expected at 16 validation batches); the
  threshold rule needs an amendment decision (conformal order statistic is a candidate); about 34 to 36 confirmatory
  clusters make a confirmatory batch claim unlikely unless sigma-hat is about 0.07 or less.
- Authorizes: nothing now. Does not authorize: running the batch pilot. Independent of the unit-level pilot authorization.
- Readiness: separate gate; needs review.

### D-11 Seed and sampling procedure

- Question: who draws the unit-level panel seed, and when?
- Options: owner draws and records one seed; implementer proposes one. Recommended: the owner draws and records one seed
  once, after the selection rules (D-01, D-02, D-07, D-08, D-12) are fixed; the procedure then runs once. The procedure's
  balance does not depend on the seed (curator maximum 2 to 3 over seeds 1 to 100 at 16).
- Authorizes: the draw. Does not authorize: re-drawing for a preferred panel. Readiness: ready for owner approval.

### D-12 Floors and pilot eligibility

- Question: are 15 percent test share, 20 positives and k of at least 10 the floors, and must pilot clusters meet them?
- Options: accept, change. Recommended: retain provisionally; require pilot clusters to meet the same structural floor;
  verify protocol-specific adequacy (positives and k per mechanism) before confirmatory use. Below-floor clusters serve
  a separate technical-validation panel.
- Evidence: 150 groups meet the floor, 83 do not, 2 are unknown; the floor does not establish positives, runnability or
  detector applicability.
- Authorizes: the floors and the pilot eligibility rule. Does not authorize: inclusion of a specific group.
- Readiness: needs review.

### D-13 Experimental unit per protocol

- Question: which unit does each protocol use, and under which specification?
- Options: protocol-defined unit; the provisional unit; the registered `temporal_batch` only.
- Recommended: the five protocol-defined units (P-TAB `row`, P-TS `time_window`, P-SEQ `event_sequence`, P-REL
  `relationship`, P-NEST `nested_path`), each by one dated amendment, once its specification is complete. The drafts are in
  `unit_amendment_proposals.md`; `event_window`, `relational_load` and `document_batch` stay provisional and are not
  equivalent.
- Limits: no detector interface or detector list is registered for any of the five units; P-REL needs an operator a rule
  cannot see; P-NEST needs a budget definition.
- Authorizes: scientific use of that unit by its runner, per protocol. Does not authorize: execution.
- Readiness: needs review of each proposal; the owner can decide protocol by protocol.

### D-14 Pilot execution

- Question: authorize the pilot run now?
- Options: authorize, defer. Recommended: defer until D-01 to D-12 and the independent review are recorded. Separate gate.
- Authorizes: a pilot run. Does not authorize: a confirmatory run. Readiness: separate gate.

### D-15 Confirmatory sample size

- Question: how many clusters confirm?
- Recommended: determine after the authorized pilot, with the rule of D-04 and the family of D-06, against
  contrast-specific eligible clusters and the dependence sensitivity of the remediation section 7.
- Authorizes: the size. Does not authorize: the run. Readiness: separate gate.

### D-16 Evaluation and inclusion boundaries

- Question: which claims are made, and how are negative or inconclusive results treated?
- Options: per-category and pooled claims; pooled only.
- Recommended: pooled claims where powered; per-category analyses exploratory (no category reaches the required figures:
  6 to 29 floor-meeting holdout clusters); negative or inconclusive pilots reported without supporting or refuting the
  confirmatory hypotheses; unit-level and temporal-batch results never pooled.
- Authorizes: the reporting rule. Does not authorize: dropping a detector or dataset from the evaluation.
- Readiness: needs review.

### D-17 Lifting the freeze for a pilot

- Question: when, and on which conditions?
- Recommended: keep the freeze; lift only after D-01 to D-13, D-14 and the independent review are recorded.
- Authorizes: the lift. Does not authorize: the confirmatory run. Readiness: separate gate.

## 3. Summary of readiness

Ready for owner approval: D-02 (and the 30-group choice), D-07, D-08, D-09, D-11. Need the independent review first:
D-01, D-03, D-04, D-05, D-06, D-12, D-13, D-16. Separate gates: D-10, D-14, D-15, D-17. No decision here needs separate
approval of ordinary engineering details.

## 4. Dependencies

Runners #135 to #139 are built and tested on synthetic fixtures (see [ENGINE_PERMISSIONS.md](ENGINE_PERMISSIONS.md));
their scientific use waits for D-13. #153 closes only with a recorded independent review. #154 closes with one dated
amendment per approved unit. D-14 and D-17 depend on D-01 to D-13 and on the review.

## 5. Owner response template

Copy, fill in and record in the repository yourself; nothing here creates an approval.

```
D-01: approve balanced 16 | balanced 24 | modify: ...
D-02: approve exclude five | allow | modify: ...; 30 labelled-pool groups: exclude from confirmation | keep eligible
D-03: approve t + curator-block sensitivity | modify: ...
D-04: approve 1.55 + assurance rule | 1.4 | 1.7 | modify: ...
D-05: approve 0.05 | modify: ...
D-06: approve A (k=1) / B (k=3) with the selection rule | modify: ...
D-07: approve forbid | allow
D-08: approve yes | no
D-09: approve linked | independent
D-10: defer | approve: ... (contrasts, sigma rule, P, M, seed, exposed groups)
D-11: seed = ...
D-12: approve | modify: ...
D-13: P-TAB / P-TS / P-SEQ / P-REL / P-NEST: protocol unit | provisional unit | registered batch only
D-14: authorize pilot on <date> | defer
D-15: after pilot
D-16: approve | modify: ...
D-17: lift on <date> | keep
```
