# Batch-level variance pilot (T424): proposed design addendum

Status: **proposal, not approved, not dated as an addendum**. It becomes the dated addendum of
`pipeline_batch_faults.md` only when the owner approves it. The experiment freeze is active, no
pilot has run, no detector result was read, and nothing below fixes the confirmatory sample size.
Numbers come from the audit files named in each section and from `research/target_framework.py`.

## 1. Two pilots, two studies

| | Unit-level pilot | Batch-level pilot (T424) |
|---|---|---|
| Defined in | `variance_pilot_design.md` 11.7 and 12.5 | `13-pipeline-level-study.md` T424; `pipeline_batch_faults.md` |
| Study | typed and mixed row-level injection, protocol contrasts F1 to F5 | replayed loads with eight pipeline fault mechanisms |
| Size | 16 provenance groups (24 deferred) | "24 to 48 sources" |
| Alert budget | 1 percent of eligible test units, `k = floor(0.01 N)` | 5 percent of clean validation batches (95th percentile of scores) |

These are not one requirement stated twice. They answer different questions about different units, so
the numbers neither contradict nor substitute for each other, and the 16-group plan
(`pilot_plan_dry_run.json`, 119 groups, predates Wave 28) is not the batch pilot. What is unresolved
is only that T424 gives a range (24 to 48) that was written before the eligible population was known.

**Why 1 percent cannot carry over.** A batch source has 80 to 101 batches and 20 percent of them
(16 to 20) are the clean validation set that sets the threshold. A 1 percent budget would need at
least 100 clean batches; at 5 percent the threshold is one order statistic of 16 to 20 scores and the
attainable false-alert resolution is 1/16 to 1/20. The 5 percent budget is therefore the registered
batch value and not an inconsistency; sensitivity budgets are optional and need approval.

## 2. Scientific question of the pilot

Estimate the quantities that size the confirmatory batch study, without ranking detectors:

1. the between-source SD sigma of the paired difference in recall at the 5 percent budget, for each
   contrast fixed below;
2. the source-by-detector variance and the within-source intraclass correlation, to set a design
   effect for the clustering of mechanisms and seeds inside a source;
3. whether the eligible population can support a confirmatory contrast at all (section 5).

## 3. Estimand, population, unit

- **Unit of inference:** the provenance cluster (a provenance group, merged with the groups it is
  linked to in `evidence/dataset_registry_v2/linked_sets.json`). Batches, seeds, mechanisms,
  severities and injected variants are never counted as sources (T430).
- **Per-source outcome:** recall at the 5 percent budget averaged first over the five registered
  seeds, then over the 24 mechanism-severity cells with equal weight (registered averaging order),
  separately for the clean-reference arm; the contaminated arm is reported, not used for sizing.
- **Contrasts (to be fixed by the owner before the pilot, at most three):** the paired difference
  between `constraint_rules` and one named learned detector per profile type, and between
  `constraint_rules` and `volume_freshness`. The sizing sigma is the largest of them. Naming the
  best learned detector after seeing pilot results is not allowed.
- **Population:** registry groups for which the registered batch unit is defined (a timestamped
  table with at least four continuous columns and 1,500 clean rows). `batch_eligibility.json`:
  **47 of 235 groups** after the ten views were restored and time columns were detected by content
  (before: 40); 46 clusters (one linked pair). Per category: C1 1, C2a 6, C2b 8, C3 21, C4 5, C5 6,
  C6 0 (no overlap among eligible groups, so 47 distinct). C3 supplies 45 percent of the frame.
  The claim of the batch study is therefore about **timestamped numeric tabular loads**, mainly
  sensor and operational series. It cannot speak for C6, and category-level claims stay exploratory.
- **Fault mechanisms:** the eight registered mechanisms apply to every eligible group. The
  referential-integrity operator (T425, `research/relational_faults.py`) is implemented and tested
  but is not part of the registered mechanism set and has no registered batch profile feature; adding
  it is a protocol amendment (section 8, decision 4), so the pilot does not use it.

## 4. Exposure and linked sources

- Five groups were seen by the plumbing pilot, whose full-profile outcome informed Amendment 1:
  `airquality_italy`, `candanedo_umons`, `seoul_bike`, `steel_korea`, `tetouan_power`. They cannot
  be confirmatory evidence. Proposal: **use them as part of the pilot** (their variance is still
  informative, the pilot result is not confirmatory evidence) so the pilot spends fewer fresh
  clusters. UCI 275, 247 and 799 are not registry groups.
- Linked sets (`linked_sets.json`, Update 32): Bloomington water plant with the Locus solar site
  (found), GitHub advisories, OSV-Go and NVD (found), Cincinnati calls and fire dispatch (candidate;
  treated as linked until the owner decides). A cluster is drawn as one unit, so linked groups can
  never fall on both sides of the split (`batch_statistics.draw_clustered_pilot`, tested). Random
  effects do not remove direct duplication, so the split rule, not the model, is the protection.

## 5. Size: what the population allows

Fresh clusters: 41 (46 clusters, 5 exposed). With the exposed groups in the pilot, a pilot of P
clusters leaves `46 - P` for the confirmatory study. Sources a paired contrast needs
(`target_framework.paired_sources`, alpha 0.05, power 0.80, delta 0.05; no design effect):

| sigma | 1 contrast | 3 (Holm) | delta 0.03, 1 contrast |
|---|---|---|---|
| 0.08 | 23 | 30 | 58 |
| 0.10 | 34 | 45 | 90 |
| 0.12 | 48 | 64 | 128 |
| 0.15 | 73 | 98 | 199 |

| Pilot clusters P (5 exposed + fresh) | 12 | 16 | 18 | 24 |
|---|---|---|---|---|
| Confirmatory clusters left (46 - P) | 34 | 30 | 28 | 22 |
| SD interval of the pilot, no clustering (sigma-hat ratio) | 0.71 to 1.70 | 0.74 to 1.55 | 0.75 to 1.50 | 0.78 to 1.40 |

Reading: the frame can meet a single-contrast confirmatory need only if sigma is at most about 0.10
and the pilot is about 12 clusters; three contrasts (45) are out of reach at any pilot size, and so
is delta 0.03. A pilot of 24 to 48, as T424 reads, would leave 22 or fewer clusters. The pilot size
is **not fixed here**: it is a trade between a sharper sigma and the clusters left, and the sizing
rule below applies to the actual eligible frame. (The 87 sources for sigma 0.10 and delta 0.03 in `DESIGN_DECISION_2026-11-21.md` is the normal
approximation 7.85 (sigma/delta)^2 = 87.2, truncated instead of rounded up; the small-sample
paired-t search of `paired_sources`, which also gives the 34 for delta 0.05 that the design uses, gives
90, and 71 becomes 73 for sigma 0.15. Both are correct for their method; this proposal uses the
function. The dated decision record is left unchanged.)

**Options for the owner when the frame is too small** (a scientific decision, not taken here):
(a) amend the protocol with further units (event window, relational load, document batch;
section 7) so that more of the 235 groups qualify; (b) state the batch claim for the stratum that
qualifies and report the confirmatory contrast as underpowered or exploratory; (c) run the batch
study as exploratory throughout. Reusing pilot clusters as confirmatory evidence is not an option.

## 6. Pilot procedure (after approval)

1. **Panel:** `python research/batch_statistics.py pilot-plan --total P --minimum M --seed S
   --reuse-exposed --output FILE`, with P, M and S fixed by the owner (the earlier registered seed
   candidate is 20261121). Only group identifiers, categories and the seed are read. The output is
   committed before any run.
2. **Execution:** `python research/registry_units.py run --step T424-pilot --authorization FILE
   --groups ... --output DIR [--compact]`; refuses without an authorization record naming the step
   and every group. Registered seeds 42, 1, 2, 3, 4; clean and contaminated arms; both profiles.
3. **Estimation** (synthetic-tested, no outcome fitted so far): `paired_difference_sd`,
   `variance_components` (balanced crossed design, expected mean squares, negative components
   truncated and listed), `icc_oneway`, cluster bootstrap of the per-cluster mean for intervals,
   `target_framework.sd_ratio_interval` and `effective_sd_interval` for the SD, and
   `paired_sources` with Holm level alpha over the family size for the recalculated size.
4. **Output:** variance components with intervals, the recalculated confirmatory size per contrast
   and the clusters left, and a dated addendum fixing the size. No ranking, no per-detector claim.

**Stopping and inconclusive results.** A group that fails to run is recorded with its reason and is
not replaced. If the upper bound of the SD interval implies a need above the clusters left, the
result is "confirmatory contrast not supported in this stratum" and the owner chooses among the
options in section 5; the pilot is not enlarged using confirmatory clusters. Held-out outcomes are
never inspected to adjust the design.

## 7. Analysis proposal and C1 weighting

- **Primary:** equal weight per cluster (the registered pooled estimand: groups, not rows or
  batches), mean of per-cluster paired differences, interval by cluster bootstrap, Holm over the
  contrast family. This needs no model that the frame cannot identify.
- **Why not the mixed model as primary:** over the eligible frame, domain has 44 levels (42 with one
  group), schema family 41 (39), curator 27 (23, the largest is `zenodo` with 13). Domain and schema
  family effects are confounded with the group's own residual and cannot be estimated; only curator
  is partly estimable. The mixed model with crossed domain, schema-family and curator effects of the
  unit-level design is therefore not fitted. `statsmodels` is not in the lock, so it would also add
  a dependency; that is a decision for the owner, not taken here.
- **Sensitivity:** category-balanced weights (inverse category size), leave-one-category-out, and
  leave-one-curator-out for `zenodo`, each reported next to the primary.
- **C1:** all 52 sources stay in the registry. One of them is batch-eligible, so C1 weighting does not
  arise in the batch study; it matters for the unit-level study (effective groups 4.6 at rho 0.2,
  2.0 at rho 0.5) where the earlier recommendation stands.

## 8. Other units and the decisions they need

`registry_units.compatibility` (`batch_compatibility.json`) separates a missing definition from an
invalid pairing. Representations without an approved definition stay unsupported, and their detector
interface is undefined; none is forced into the numeric timestamped format.

| Unit | Applies to | Information kept / lost if transformed | Decision needed |
|---|---|---|---|
| `event_window` | event logs (26 groups of protocol P-SEQ) | window profile (counts per activity, inter-event times) keeps volume and freshness; loses case-level ordering | window length and profile definition |
| `relational_load` | multi-table sources (32 groups of protocol P-REL) | load of child-table rows plus orphan share; loses parent history | profile feature for orphan share, severity grid, which tables are loads |
| `document_batch` | nested documents (27 groups of protocol P-NEST) | batch of documents with path-level null and type shares; loses nesting beyond the flattened paths | path flattening rule, schema-drop meaning |

Also: panel sources (several entities in one table, for example `zen_bess`, `zen_telecom_kpis`,
`zen_aegis_vehicle`, whose time is an elapsed counter) need an entity-level replay rule; sparse tables
lose all rows under the complete-case rule (for example `backblaze`, `ecb_fx`, `monash_pedestrian`);
single-column series (`ea_hydrology`, `usgs_water`) fall below the four-column profile.

## 9. Decisions needed from the owner (none is taken here)

1. The contrasts (at most three) and the sizing sigma rule.
2. The pilot size P, the per-category minimum M and the seed S, after reading section 5.
3. Whether the five exposed groups join the pilot.
4. The population option when the frame is too small (section 5 a, b or c), and whether the
   referential-integrity operator and any other unit enter the protocol by amendment.
5. Whether a mixed-model dependency is wanted at all (section 7).
6. Whether Cincinnati calls and fire dispatch are linked.

Authorizing the pilot is a separate gate from approving this addendum, and approving the confirmatory
sample size is a later gate that needs the pilot result.


## 10. Revision 2 (2026-11-25, after the execution path and the relational keys were completed)

Still a proposal; nothing here is approved and nothing was run on a registry source.

### 10.1 Finite-sample alert budget (verified, `test_alert_budget_resolution.py`)

The registered threshold is `np.quantile(validation scores, 0.95)` with linear interpolation, and a
batch alerts when its score is strictly above it. On its own validation scores that flags exactly
one batch for 16 to 21 validation batches (6.25, 5.9, 5.6, 5.3, 5.0, 4.8 percent) and two for 22 to
40 (9.1 percent at 22), because the interpolated quantile lies between the two largest scores and
the largest is the only one above it. Tied top scores flag nothing (a rules detector whose clean
scores are constant has threshold 0 and alerts on any positive score). Correction (2026-11-27): 1/(n+1) and Beta(1, n)
describe the exceedance probability of the sample maximum, not of an interpolated empirical
quantile. The registered threshold lies between the two largest validation scores for 16 to 21
batches, so for exchangeable continuous scores the probability that a new clean batch alerts has
mean 1 - (0.95 (n - 1) + 1) / (n + 1), that is 10.3 percent at n = 16, 9.3 at n = 20, 7.2 at n = 40
and 5.9 at n = 100, with a standard deviation of 6.1 points at n = 20 (exact order-statistic moments,
`research/analysis_design_simulation.py`; `verification/pilot_statistical_remediation.md` section 9).
The false-alert rate observed on m clean test batches adds binomial noise, ties flag nothing, and
temporal dependence between batches lowers the effective n. So "5 percent" is a target, not an
achieved rate, and in expectation it is exceeded with fewer than about 100 validation batches. Proposed clarification:
report the achieved false-alert rate on the clean test batches beside every recall, compare
detectors only inside a source at their own achieved rate, and do not describe the budget as exact.
The threshold rule itself is not changed.

### 10.2 Statistical model

For the unit-level corpus (235 groups) the factor structure is domain 150 levels (127 with one
group), schema family 138 (125) and curator 88 (65); for the 47 batch-eligible groups it is 44 (42),
41 (39) and 27 (23). Domain and schema-family effects cannot be separated from the residual of a
group, so the registered mixed model with those effects is not estimable as specified; only curator
(large levels such as `uci`, `zenodo`) carries information. No dependency was added.
Proposed amendment: primary analysis is the mean of per-cluster paired differences with a cluster
bootstrap interval (`batch_statistics.cluster_bootstrap`); sensitivity analyses are
category-balanced weights, leave-one-category-out and leave-one-curator-out, plus
`variance_components` for the pilot. A mixed model with a curator random effect could be added later
if the owner wants one (it needs a dependency decision). The registered Holm procedure is kept for
the confirmatory family.

### 10.3 Contrasts and multiplicity

One primary contrast (paired difference in recall at the 5 percent budget between `constraint_rules`
and one learned detector fixed before the pilot) and secondary contrasts (against `volume_freshness`
and `distribution_distance`) reported with Holm inside the secondary family. The batch protocol
registers hypotheses B1 to B5 as exploratory, so no registered confirmatory hypothesis is removed by
this choice; the owner decides whether any of B1 to B5 becomes confirmatory.

### 10.4 Exposed groups

The five plumbing-pilot groups are all C3 series from the UCI pool, a single regularly sampled family,
and were chosen by eligibility, not by detector result. Including them in the pilot makes the pilot
sigma estimate cover that family more heavily than the frame (5 of 10 to 12 pilot clusters against
about 11 percent of the frame). Proposed: include them and report the pilot variance with and without
them; the confirmatory panel excludes them in any case.

### 10.5 Populations by design option

| Option | Population (independent clusters) | Pilot | Confirmatory capacity | Claim it can support |
|---|---|---|---|---|
| A. Registered numeric batch unit | 46 (41 fresh, 5 exposed) | 10 to 12 (exposed plus 5 to 7 fresh) | 34 to 36 | one primary contrast, only if the pilot sigma is at most about 0.10; scope limited to timestamped numeric loads, mostly C3 |
| B. A plus proposed units | event window 25, relational load 33, document batch 30 groups, each a separate estimand | per unit | below 34 each before any pilot | none confirmatory; exploratory per unit; pooling across units is not justified |
| C. Unit-level study as the confirmatory study | 235 groups, 231 clusters | 16 groups (registered) | about 215 | the registered protocol contrasts over seven structures; batch study stays exploratory |

Planning with the SD interval of a pilot of n clusters: n = 10 gives 0.69 to 1.83 times the estimate,
n = 12 gives 0.71 to 1.70. If the pilot estimate is sigma-hat = 0.06, 0.07, 0.08, the upper bound with
n = 10 needs 40, 54 or 69 confirmatory clusters for delta 0.05 (one contrast), against 36 available;
the point estimates need 34 or fewer only for sigma-hat up to about 0.10. So whether option A can be
confirmatory is decided by the pilot, and the design must accept "not supported" as an outcome.

**Recommendation.** Option C as the confirmatory study (it has the capacity), and option A as the
mandatory batch-level study run through the pilot with 10 clusters (5 exposed, 5 fresh) and a stated
decision rule: confirmatory if the required size from the pilot sigma is at most the clusters left,
otherwise exploratory with intervals. Option B's units are implemented only as provisional components
(section 10.6) and are not part of the recommendation until approved.

### 10.6 Provisional units, implemented but not registered

| Unit | Code | Observation | Truth | Detector input | Metric | Limit | Approval needed |
|---|---|---|---|---|---|---|---|
| `relational_load` | `relational_units.relational_cells` | consecutive child rows of one declared key (file order) | rows with an injected unresolved reference | orphan share of the load | recall, false-alert rate at the 5 percent rule | file order is not a load time; natural orphans raise the threshold | load definition, severity grid, detector set |
| `event_window` | none (definition only) | window of events of one log | per window | activity counts and inter-event times | as batch | window length undefined | window definition, profile |
| `document_batch` | none (definition only) | batch of nested documents | per batch | path-level null and type shares | as batch | flattening rule undefined | flattening rule, fault meaning |

The relational keys of 32 relational views (139 keys) were recomputed on the local tables and equal the
counts recorded by the builders (`relational_keys.json`). Not modelled as plain keys: FEC
`pas2.OTHER_ID` (polymorphic, no declared type column) and two conditional references of
`zen_3pfl`. Event windows and document batches have no code because their definitions are exactly
the open decisions; writing them would fix those decisions.

### 10.7 Execution path

`registry_units.py run` is the general execution path: any registry group, the real `run_source`,
per-group atomic result file, `--seeds` and `--compact`, authorization record required. A synthetic
group runs end to end through the real harness in `test_registry_units.py`. `pipeline_batch.main`
(L4) is kept unchanged for the historical UCI series; those series are registry groups too and run
through `registry_units.py` when eligible.
