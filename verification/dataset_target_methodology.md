# Dataset coverage targets: audit and sample-size framework

Status: proposal for owner review. The approved acquisition targets are unchanged by this document.
All numerical illustrations are design-only: they use hypothetical parameters and no detector was run.
Reproduce with `python research/target_framework.py` (output `verification/evidence/dataset_registry_v2/target_framework.json`;
source attributes in `source_attributes.json`).

## 1. Facts: where the targets come from

Documented in the repository (confirmed):

- The per-stratum figures first appear in `docs/thesis-remediation/13-pipeline-level-study.md`, section
  "Dataset strata (added 2026-11-21)", commit `c1bcb25` (2026-11-21): minimum, recommended and ambitious
  counts of independent source families: C1 15/36/50, C2 (transactional and categorical) 15/30/45,
  C3 15/40/55, C4 15/28/40, C5 15/36/55, C6 15/30/45. The same text states that they are "planning figures
  conditional on an assumed variance" and that the variance pilot (T424) fixes them.
- The figures used as targets so far (36, 30, 40, 28, 36, 30) are the "recommended" column; they sum to 200
  category participations. Nothing in the repository derives them per stratum from a power or precision
  calculation.
- `docs/thesis-remediation/DESIGN_DECISION_2026-11-21.md`, section "Sample size", gives the only calculation:
  for a two-sided paired comparison with alpha 0.05 and power 0.80, about 7.85 (sigma/delta)^2 sources, giving
  87 sources for sigma 0.10 and delta 0.03 and 71 for sigma 0.15 and delta 0.05, "before multiplicity and
  clustering corrections". It states a planning range of about 120 to 300 independent source families over all
  strata, "not a requirement until the pilot fixes it". That range was introduced on 2026-11-20 (commit
  `6ca0a8e`) from a design review; the review text itself was not located in the repository.
- `verification/experimental_coverage_assessment.md` already records that the number of datasets or publishers
  must not be the sample size and that the targets need a methodological argument "that is not written here".
- The statistical plan of the first thesis phase (`04-statistical-validity.md`) already requires source-cluster
  bootstraps and forbids counting seeds as datasets.

Interpretation (mine, not documented): the targets are planning objectives of the "recommended" tier, not formal
sample-size requirements and not minimum coverage requirements. The minimum column (15) is the only figure that is
described as a minimum, and it too has no calculation behind it.

C2 versus C2a and C2b. The original C2 target (30) belonged to a stratum defined as "transactional and
categorical". Later the stratum was split into C2a (categorical or mixed schema) and C2b (genuinely
transactional) and the figure 30 was carried to C2b alone. That is a change of definition without a
re-derivation: either 30 now applies to a narrower class than it was planned for, or C2a has no target. This
document keeps 30 for C2b as the approved objective and proposes treating C2a as a separate, smaller stratum (section 8).

Independence accounting changed after the targets were set: the original counts were of "source families" at a
time when whole UCI tables were counted; the current accounting uses provenance groups (one per original producer,
with conservative grouping), so historical C1 and C2a counts (92 and 42 by a coarse rule) are not comparable with
current C2b to C6 counts and are not re-audited here.

## 2. Claims, units and what must be independent

Research questions of the paper (`paper/main.tex`): RQ1 detector families compared behind one interface, RQ2 per
anomaly type profile and its stability across generators and real tables, RQ3 dependence on operating point and
time, RQ4 cost. The batch-level ETL study adds a controlled fault study at load level.

| Claim | Estimand | Unit of inference | Evidence level that is independent |
|---|---|---|---|
| Detector family A beats B on structure S | mean over sources of a paired metric difference at a matched alert budget | source group within stratum S | original producer and generating system; shared schema and curator are dependence to model |
| Per-anomaly-mechanism profile | detection rate per mechanism and family | source group where the mechanism is applicable | only groups whose protocol supports the mechanism |
| Generalisation across domains | between-domain variance of the difference | domain | domain (needs many domains, not many tables) |
| Operating-point sensitivity | change of metric across budgets | source group | same as the first row |
| Cost (RQ4) | time and memory per detector and size | dataset instance (size is the factor) | not a source-sample question |

Not independent evidence: rows, batches, windows, injected faults, severities, seeds, detector executions,
snapshots, tables of one database, views of one source. A detector is applicable only to some structures and
mechanisms, so the effective sample for a claim is the number of groups where both detectors apply.

Grouping strategy for later inference (proposal). Level 1: provenance group (original producer and generating
system), the unit now used in readiness. Level 2: cluster for inference: domain, then shared schema family and
curator as additional random effects, because sources of one schema family (for example twelve GTFS feeds, eight
XES logs) share exporter conventions and are likely correlated even when their operations are unrelated. A common
curator alone is not treated as dependence; a common schema family or ecosystem is treated as a modelled cluster.
The decision of how much correlation to assume is empirical (section 6).

## 3. Quantitative framework (design-only)

Model for one comparison of detectors A and B in stratum S: for source s in cluster c, D_s = metric(A) - metric(B)
= delta + u_c + e_s with u_c ~ N(0, tau^2) and e_s ~ N(0, sigma_e^2), reporting the cluster-robust mean of D_s.
For independent sources the standard deviation of D_s is sigma = sqrt(tau^2 + sigma_e^2); clustering multiplies
the variance of the mean by the design effect 1 + (m - 1) rho (m sources per cluster, intra-cluster correlation
rho). Required independent sources for a two-sided paired t test: smallest n with power >= 0.80 at level
alpha / k (k comparisons, Bonferroni; Holm is no worse), computed exactly with the non-central t distribution;
for confidence-interval precision the smallest n with t_(n-1) sigma / sqrt(n) <= half-width. The normal
approximation reproduces the documented 7.85 factor (7.849).

Sources needed per stratum for one paired comparison (exact t, alpha 0.05, power 0.80). Columns: k = 1, 3, 6
comparisons, then sources for a 95 % CI whose half-width equals delta.

| sigma | delta | k=1 | k=3 | k=6 | CI half-width = delta |
|---|---|---|---|---|---|
| 0.05 | 0.03 | 24 | 32 | 38 | 14 |
| 0.05 | 0.05 | 10 | 14 | 16 | 7 |
| 0.05 | 0.1 | 5 | 6 | 7 | 4 |
| 0.1 | 0.03 | 90 | 120 | 139 | 46 |
| 0.1 | 0.05 | 34 | 45 | 52 | 18 |
| 0.1 | 0.1 | 10 | 14 | 16 | 7 |
| 0.15 | 0.03 | 199 | 265 | 307 | 99 |
| 0.15 | 0.05 | 73 | 98 | 113 | 38 |
| 0.15 | 0.1 | 20 | 27 | 31 | 12 |
| 0.2 | 0.03 | 351 | 469 | 542 | 174 |
| 0.2 | 0.05 | 128 | 171 | 198 | 64 |
| 0.2 | 0.1 | 34 | 45 | 52 | 18 |

Design effect for clustered sources (sigma 0.10, delta 0.05, k = 1; independent requirement 34):

| sources per cluster | rho | design effect | sources needed |
|---|---|---|---|
| 2 | 0.0 | 1.00 | 34 |
| 2 | 0.2 | 1.20 | 41 |
| 2 | 0.5 | 1.50 | 51 |
| 4 | 0.0 | 1.00 | 34 |
| 4 | 0.2 | 1.60 | 55 |
| 4 | 0.5 | 2.50 | 85 |
| 8 | 0.0 | 1.00 | 34 |
| 8 | 0.2 | 2.40 | 82 |
| 8 | 0.5 | 4.50 | 153 |

Smallest detectable paired difference for a given number of independent sources (power 0.80, alpha 0.05, k = 1):

| independent sources | sigma 0.05 | sigma 0.10 | sigma 0.15 |
|---|---|---|---|
| 10 | 0.0499 | 0.0997 | 0.1495 |
| 18 | 0.0351 | 0.0701 | 0.1052 |
| 25 | 0.0293 | 0.0585 | 0.0877 |
| 34 | 0.0248 | 0.0496 | 0.0743 |
| 49 | 0.0205 | 0.0409 | 0.0613 |
| 73 | 0.0167 | 0.0333 | 0.0499 |

Simulation of the cost of ignoring clustering (null effect, 2000 repetitions, source SD 0.05, seed 11): a
source-level test on clustered data rejects far above the nominal 5 % when domains matter, a domain-level
analysis stays near 5 %.

| domains | sources per domain | domain SD | source-level rejection | domain-level rejection |
|---|---|---|---|---|
| 6 | 5 | 0.08 | 0.3595 | 0.048 |
| 10 | 3 | 0.08 | 0.219 | 0.0525 |
| 10 | 3 | 0.02 | 0.085 | 0.0505 |

Assumptions (all hypothetical): metric differences are approximately normal at source level, sigma and delta are
in the units of the chosen metric (an average-precision difference is used as the working picture), one
comparison family per stratum, Bonferroni with k = 1, 3 or 6. None of sigma, rho, tau is measured. Calibration
requires the T424 variance pilot: between-source SD of paired differences per stratum, the source-by-detector
variance component, the intra-cluster correlation by domain, schema family and curator, and the share of sources
where each detector pair is applicable. The pilot must be run only after the freeze is lifted; no such run was made.

## 4. Coverage is a separate requirement

Power fixes how many independent groups are needed to estimate a mean difference; it does not say that the groups
span what the claims are about. The coverage framework per stratum requires variation in: domain, original
producer and generating system, schema complexity (columns, types, nesting depth, relation count), scale,
temporal behaviour (period, gaps, trend, seasonality for C3; session length and branching for C4; join
cardinalities and orphan baselines for C5; depth and optionality for C6), natural versus injected ground truth,
and the set of applicable anomaly mechanisms (P-TAB, P-TS, P-SEQ, P-REL, P-NEST). Many near-identical sources
(for example thirty GTFS feeds) raise precision for one schema family while leaving other conclusions
unsupported; several independent sources in one domain are useful to estimate within-domain variance. The
framework therefore states a minimum number of domains and schema families next to the number of groups, not a
quota per domain.

## 5. Current coverage against the framework

Ready groups from the readiness contract (machine-derived, `readiness.json` and `source_attributes.json`).
Effective groups discount groups that share a schema family by an assumed intra-family correlation of 0.2 and 0.5.

| stratum | ready groups | domains | curators | schema families | largest schema-family share | effective groups (rho 0.2) | effective groups (rho 0.5) |
|---|---|---|---|---|---|---|---|
| ALL | 52 | 34 | 19 | 25 | 0.2308 | 34.5595 | 28.5049 |
| C2b | 10 | 7 | 5 | 5 | 0.3 | 7.9524 | 6.3333 |
| C3 | 11 | 11 | 4 | 6 | 0.5455 | 8.0 | 6.7143 |
| C4 | 13 | 10 | 3 | 5 | 0.6154 | 8.0 | 6.1111 |
| C5 | 18 | 6 | 6 | 6 | 0.6667 | 9.4167 | 7.1795 |
| C6 | 9 | 7 | 7 | 7 | 0.3333 | 8.1429 | 7.5 |

Category participations are not distinct groups: the 52 provenance groups give 61 participations.

## 6. Evaluation of the historical targets (indeterminate where the pilot is needed)

| stratum | historical target | ready groups | effective groups (rho 0.5) | assessment |
|---|---|---|---|---|
| C1 flat tabular | 36 | not recomputed under provenance grouping | n/a | indeterminate: historical coarse count only |
| C2a categorical | none after the split | not recomputed | n/a | undefined: needs a decision |
| C2b transactional | 30 | 10 | 6.3333 | defensible as planning figure only; effective independence is about 6 to 8 |
| C3 time series | 40 | 11 | 6.7143 | indeterminate: 40 is in the range of one-comparison requirements for sigma 0.10 and delta 0.05 (34) to sigma 0.15 (73), but not for multiple comparisons |
| C4 logs and sequences | 28 | 13 | 6.1111 | the 28 is below the one-comparison need for sigma 0.10 and delta 0.05 (34); 8 XES logs share one schema family |
| C5 relational | 36 | 18 | 7.1795 | the count is inflated by twelve GTFS feeds; domains and schema families are few |
| C6 nested | 30 | 9 | 7.5 | indeterminate; depth and optionality coverage still thin |

Reading: with sigma 0.10 and delta 0.05 a single stratum needs about 34 independent sources for one comparison
and about 52 for six; with delta 0.10 it needs 10 to 16. The recommended figures (28 to 40) sit inside that
range, which is consistent with, but does not demonstrate, the intended precision. Under sigma 0.15 or
design effects of 2 or more the requirements double. Pooled claims across strata use all groups, so 52 nominal
groups (about 29 effective at rho 0.5) detect roughly 0.04 to 0.06 at sigma 0.10, but stratum-specific claims
remain far from that. No target is shown to be excessive or insufficient until sigma and rho are measured.

## 7. Proposal (not adopted)

Three tiers with explicit definitions instead of one number:

1. Exploratory minimum. Enough independent groups per stratum to run the pilot and to estimate sigma and rho
   with usable uncertainty: at least 15 groups, at least 5 domains and 3 schema families per stratum
   (the 15 of the existing minimum column; the domain and schema criteria are new). Supports descriptive
   statements and the variance pilot only.
2. Claim-specific inferential minimum. For each pre-registered claim, n = paired_sources(sigma_pilot,
   delta_min, k, design_effect_pilot) groups where both detectors apply, with delta_min stated before the
   run. Until sigma is measured the working placeholder is the sigma 0.10, delta 0.05, k = 3 row (45 independent
   groups before design effect), stated as such.
3. Generalisation objective. The recommended 28 to 40 per stratum together with minimum counts of domains
   (at least 8) and schema families (at least 4) and at least three independent mechanisms applicable in the stratum.

Proposed changes: define C2a explicitly (small stratum, exploratory tier only); report effective groups beside nominal
groups; add the domain and schema-family minima to the readiness report. No change of the 30, 40, 28, 36 and 30 is
proposed before the pilot.

## 8. Consequences for acquisition (applied now without changing the targets)

- Prefer new domains and new schema families over further feeds of an existing family: C5 needs non-GTFS
  relational databases; C4 needs non-XES, non-job-accounting logs; C3 needs domains absent today (finance,
  telecom, retail demand, geophysics, medical monitoring); C6 needs nested application records from other
  publishers.
- C2b needs retail, payments, utility billing and logistics transactions beyond procurement and event logs with amounts.
- Sources that serve several mechanisms (for example event logs with amounts) are valuable only once per group.
- Replication within a domain is still useful for within-domain variance but is capped by the schema-family minimum.

## 9. Decisions requiring approval

1. Adopt the three-tier framework and the definition of provenance group plus modelled schema-family cluster.
2. Define C2a (target and tier) now that C2 is split, and decide whether C1 and C2a are re-audited under provenance grouping.
3. Authorise the T424 variance pilot after the freeze (needed to turn illustrations into requirements).
4. Decide the minimum number of domains and schema families per stratum.
5. Decide the default multiplicity family (Bonferroni or Holm) and the smallest meaningful difference delta_min per metric.


## 10. Owner decisions of 2026-11-21 and their implementation

Status of this document after the decisions: the three-tier framework, the provisional targets, the diversity guardrails
and the Holm policy are adopted as planning rules; the numbers below remain illustrative where they depend on
hypothetical parameters, and none of them is a statistically validated requirement.

**A. Three tiers.** (1) Exploratory coverage: at least 3 distinct application domains and 2 distinct structural or
generating-mechanism families. (2) Claim-specific inferential coverage: the number of independent groups where both
detectors of a contrast apply, from `paired_sources` with the pilot's sigma and design effect (section 3). (3) Generalisation
coverage: the domain and family minima below, with the quota. A category can pass tier 1 and fail tiers 2 and 3.

**B. Provisional acquisition targets** (planning figures; their sum is 230 category participations, not 230 independent groups):
C1 36, C2a 30, C2b 30, C3 40, C4 28, C5 36, C6 30. Historical note: the figure 30 of 2026-11-21 belonged to the combined C2
("transactional and categorical"); it was carried to C2b without a new derivation; C2a's 30 is a new provisional target with no statistical basis.

**C. Variance pilot.** Design drafted in `variance_pilot_design.md`; execution is not authorised and the freeze stays active.

**D. Diversity guardrails.** Exploratory: 3 domains and 2 families. Generalisation planning minima (domains / families):
C1 5/3, C2a 5/3, C2b 5/4, C3 5/3, C4 5/3, C5 5/4, C6 5/4. Domains are the subject areas recorded in `source_attributes.json`
(`domain`); the structural or generating-mechanism family of a group in a category is `structure[category]` in the same file.
Classification criteria (fixed before counting): C2b by the business object of the transaction (contract award, expenditure
ledger, rental, property sale, purchase order process, fine and payment, subsidy payment); C3 by the measured system or
temporal regime (environmental sensing, building energy, hydrological gauging, urban mobility counts, equipment telemetry, public
health surveillance, industrial energy metering, utility load, vehicle signals, ambient living sensors); C4 by the sequence
generator (operational job trace, system and application logs, business process execution, IT service incident log); C5 by
relational topology (timetable network, clinical record graph, bibliographic graph, community question graph,
contract-grant-patent linkage, user-item ratings, shallow procurement releases); C6 by the record form (regulatory registry,
product catalogue, library catalogue, cultural catalogue, scholarly work, procurement release). File formats are not
families (CSV against Parquet, XML against JSON). C1 and C2a use the subject-area mapping of `research/provenance_audit.py`
(instrument measurement, clinical or biological records, administrative or survey records, computational or derived features).

Current state (machine-derived; ready groups from the readiness contract):

| Category | Ready groups | Quota | Gap | Domains | Families | Largest family (share) | Exploratory | Generalisation diversity |
|---|---|---|---|---|---|---|---|---|
| C2b | 10 | 30 | 20 | 7 | 7 | contract award (0.3) | yes | yes |
| C3 | 11 | 40 | 29 | 11 | 10 | urban mobility counts (0.1818) | yes | yes |
| C4 | 13 | 28 | 15 | 10 | 4 | business process execution (0.5385) | yes | yes |
| C5 | 20 | 36 | 16 | 7 | 7 | timetable network (0.6) | yes | yes |
| C6 | 9 | 30 | 21 | 7 | 6 | procurement release (0.3333) | yes | yes |

C1 and C2a are not in the readiness contract; their provenance audit (`provenance_audit_c1_c2a.json`) over the historical
tables gives, for C1, 115 tables, 94 sources, 80 provenance groups (shared-creator closure),
8 domains and 4 mechanism families; for C2a, 40 tables, 40 sources, 40 groups,
7 domains and 4 families. These are candidate groups: they have not been re-run through the v2 readiness
contract, and the T437 finding that many categorical tables are small or toy tables still applies, so they are not counted as ready.
Globally the readiness contract has 54 distinct provenance groups, 35 domains, 20 curators and
26 schema families; 12 of the 20 C5 groups are one schema family (timetable feeds) and 7 of 13 C4 groups are business-process
logs, so those categories are concentrated.

**E. Multiplicity and effect sizes.** Confirmatory families are prespecified before outcomes are seen (F1 to F5 in
`variance_pilot_design.md`); within a family Holm's step-down procedure at familywise alpha 0.05
(`holm_adjust`, `holm_rejections`); no single correction over every exploratory metric; adjusted p-values, effect sizes and
intervals are reported; exploratory results are labelled. Provisional smallest effects of interest: recall at matched alert
budget 0.05, AUPRC 0.05 (at standardised prevalence), AUROC 0.02, false-positive burden and cost 20 percent relative
(planned on the log-ratio scale, ln(1/0.8) = 0.2231). They are design assumptions; each metric must exist in the thesis
methodology before use, and AUROC, AUPRC and recall are related, so they are not independent claims.

Independent sources needed per contrast (exact t, 80 percent power, alpha 0.05 divided by the family size k; hypothetical
between-source SD sigma on the metric's scale; analysis on source-level paired differences):

| Metric | Scale | sigma | delta | k = 1 | k = 3 | k = 6 |
|---|---|---|---|---|---|---|
| recall at matched alert budget | absolute | 0.02 | 0.0500 | 4 | 5 | 6 |
| recall at matched alert budget | absolute | 0.05 | 0.0500 | 10 | 14 | 16 |
| recall at matched alert budget | absolute | 0.1 | 0.0500 | 34 | 45 | 52 |
| AUPRC | absolute | 0.02 | 0.0500 | 4 | 5 | 6 |
| AUPRC | absolute | 0.05 | 0.0500 | 10 | 14 | 16 |
| AUPRC | absolute | 0.1 | 0.0500 | 34 | 45 | 52 |
| AUROC | absolute | 0.02 | 0.0200 | 10 | 14 | 16 |
| AUROC | absolute | 0.05 | 0.0200 | 52 | 69 | 80 |
| AUROC | absolute | 0.1 | 0.0200 | 199 | 265 | 307 |
| false-positive burden | log ratio | 0.02 | 0.2231 | 3 | 3 | 3 |
| false-positive burden | log ratio | 0.05 | 0.2231 | 3 | 4 | 4 |
| false-positive burden | log ratio | 0.1 | 0.2231 | 4 | 6 | 6 |
| cost | log ratio | 0.02 | 0.2231 | 3 | 3 | 3 |
| cost | log ratio | 0.05 | 0.2231 | 3 | 4 | 4 |
| cost | log ratio | 0.1 | 0.2231 | 4 | 6 | 6 |

Pilot size for estimating sigma (upper end of its interval relative to the estimate):

| Max upper ratio | Interval level | Pilot sources |
|---|---|---|
| 1.25 | 0.8 | 24 |
| 1.25 | 0.95 | 49 |
| 1.4 | 0.8 | 13 |
| 1.4 | 0.95 | 25 |
| 1.6 | 0.8 | 8 |
| 1.6 | 0.95 | 15 |

Reading: for AUROC at delta 0.02 the requirement is very sensitive to sigma (about 10 to 200 sources between sigma 0.02 and
0.10), so AUROC claims are only feasible if the between-source SD of AUROC differences is small; a 20 percent relative reduction
(0.223 on the log scale) is easy to detect unless sigma on that scale exceeds about 0.3. These are not validated: sigma and the
clustering correlation are unknown until the pilot. Normal-approximation and independence assumptions apply; clustered sources
need the design effect of section 3. Assumptions needing owner approval before confirmatory execution: the metrics list, the
pairing rule within group, the family definitions, the Holm family sizes, the smallest effects, and the hold-out rule.
