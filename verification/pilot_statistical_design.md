# Pilot statistical design: both pilots (issue #153)

Status: design consolidation, 2026-11-26; corrected and extended by `pilot_statistical_remediation.md`, 2026-11-27. Nothing was run, no detector result was read, no approval is implied
and the experiment freeze stays active. It reconciles the unit-level pilot (`variance_pilot_design.md`, sections 12
and 13) with the batch pilot of T424 (`batch_pilot_addendum_proposal.md`, a proposal) in one place: estimands,
alert budgets, identifiability, a conservative sample size and the exposure table. It was written by the
implementer and has not been independently reviewed; the owner decisions are in section 7.

## 1. The two studies

| | Unit-level pilot | Batch-level pilot (T424) |
|---|---|---|
| Question | between-source variance of paired detector differences on the protocol's detection unit | the same for the registered temporal-batch unit (`pipeline-batch-v1`) |
| Population | 235 groups, 231 clusters, five protocols | 47 groups, 46 clusters (batch-eligible tables), mostly C3 |
| Unit of inference | provenance cluster | provenance cluster |
| Panel | 16 clusters proposed (`unit_pilot_panel.json`) | 10 to 12 clusters (5 exposed, 5 to 7 fresh) proposed |
| Can run today | no (no unit-level runner) | an execution path exists; authorization is separate |

Batches, windows, seeds, mechanisms, severities and injected variants are never counted as sources (T430).

## 2. Estimands

Unit level (`variance_pilot_design.md` 11.6, 12.2): the mean over eligible groups of the paired difference in recall at
the matched 1 percent budget, per protocol's own unit, seeds and mechanisms averaged inside the group; confirmatory
families F1 (3), F2 (5 at most) and F5 (3), at most 11 comparisons in one Holm family at alpha 0.05; the pilot
estimates only variance components. Batch level (addendum 3 and 10.3): recall at the 5 percent budget averaged
over the five seeds then the 24 mechanism-severity cells, one primary contrast (`constraint_rules` against one named
learned detector, named before the pilot) and secondary contrasts reported with Holm. The two estimands share nothing
that may be pooled: different units, budgets and detectors. Neither pilot result enters a confirmatory estimate.

## 3. Alert-budget implementation

- **Unit level:** allowance k = floor(B x N) over eligible test units, the same k for both detectors of a pair, no
  minimum-one-alert exception, ties broken by the SHA-256 of the unit identifier; confirmatory only with at least
  20 positives and k at least 10 (so N at least 1,000). Maximum attainable recall is min(1, k / P).
- **Batch level:** the registered threshold is the 0.95 quantile of validation scores (linear interpolation) and a batch
  alerts when strictly above it. With 16 to 21 validation batches that flags exactly one batch, with 22 to 40 two; the
  probability that a new clean batch alerts is not Beta(1, n), which is the law for the sample maximum: for
  exchangeable continuous scores its mean is 1 - (0.95 (n - 1) + 1) / (n + 1) (9.3 percent at n = 20) with a standard
  deviation of 6.1 points (corrected in `pilot_statistical_remediation.md` section 9). The budget is therefore a target: the achieved false-alert rate is reported beside every recall (addendum 10.1; the
  rule itself is unchanged).

## 4. Identifiability of the random effects

Domain, schema family and curator are the proposed random effects. Levels per factor:

| Population | Groups | Domain levels | Schema-family levels | Curator levels |
|---|---:|---:|---:|---:|
| Corpus (addendum 10.2) | 235 | 150 (127 with one group) | 138 (125) | 88 (65) |
| Batch-eligible (addendum 10.2) | 47 | 44 (42) | 41 (39) | 27 (23) |
| Unit-level pilot, 16 groups | 16 | 16 (each with one pilot group) | 13 (largest 4) | 9 (largest 4) |
| Unit-level pilot, 24 groups | 24 | 20 | 13 (largest 12) | 9 (largest 12) |
| Unit-level pilot, 32 groups | 32 | 20 | 13 (largest 20) | 9 (largest 20) |

A factor in which almost every level holds one group cannot be separated from the group residual. Consequences:
a domain effect is not estimable from the pilot (16 levels, one group each); schema family is partly estimable
(13 levels, 3 shared) and curator is the only factor with several groups per level. The registered mixed model with
domain and schema-family effects is therefore not estimable as specified. Proposed analysis (as in addendum 10.2):
mean of per-cluster paired differences with a cluster bootstrap interval, `variance_components` and curator-based
sensitivity analyses for the pilot; intra-cluster correlations by domain and schema family stay hypothetical planning
ranges (0.2 and 0.5) until a larger sample exists. Under the current largest-pool allocation, enlarging the pilot to 24 or 32 groups adds C1 groups from one
curator; a balanced allocation does not (`pilot_statistical_remediation.md` section 3), but domain stays unidentifiable.

## 5. Conservative sample size

The requirement uses the upper end of the SD interval of the pilot, never the point estimate. With `n` pilot sources and a
design effect `DE`, the upper ratio of sigma over its estimate is (`effective_sd_interval`):

| Pilot n | DE 1.0 | DE 1.3 | DE 1.6 | DE 2.0 | DE 3.0 |
|---:|---:|---:|---:|---:|---:|
| 16 | 1.55 | 1.70 | 1.83 | 2.04 | 2.87 |
| 24 | 1.40 | 1.50 | 1.58 | 1.70 | 2.04 |
| 32 | 1.33 | 1.40 | 1.46 | 1.55 | 1.83 |

Confirmatory sources for a smallest effect 0.05 at power 0.80 and Holm level alpha / k (`paired_sources`, exact t),
for hypothetical estimates sigma-hat and the upper ratio r (sigma used = sigma-hat x r):

| sigma-hat | r | k = 1 | k = 3 | k = 11 |
|---:|---:|---:|---:|---:|
| 0.07 | 1.4 | 33 | 44 | 57 |
| 0.07 | 1.7 | 47 | 63 | 81 |
| 0.10 | 1.4 | 64 | 85 | 111 |
| 0.10 | 1.7 | 93 | 124 | 161 |

Against these, the unit-level holdout of the 16-group plan has 210 clusters, 137 of which meet the 1,000-test-unit floor
(`variance_pilot_design.md` 13.2): a pooled claim is supportable for k up to 11 at r = 1.4 (sigma-hat 0.07 or 0.10)
and at sigma-hat 0.07 with r = 1.7, and for k = 3 at sigma-hat 0.10 with r = 1.7, but not for k = 11 at sigma-hat 0.10
with r = 1.7 (161 against 137); no single category meets the figures (8 to 30 floor-meeting groups). The batch population has about 34 to 36 confirmatory clusters (addendum 10.5), so a
confirmatory batch claim needs a pilot sigma-hat of about 0.07 or less at r = 1.4 and is otherwise exploratory. These
numbers are planning illustrations: sigma-hat is exactly what the pilot measures, and every figure assumes independent
normal source-level differences.

Reproduce: `effective_sd_interval(n, design_effect)` and `paired_sources(sigma, 0.05, comparisons=k)` of
`research/target_framework.py`; pilot factor levels from `unit_pilot_panel.json` (`table`, `plans`).

## 6. Exposure table

| Group or set | Seen by | Consequence in this design |
|---|---|---|
| `airquality_italy`, `candanedo_umons`, `seoul_bike`, `steel_korea`, `tetouan_power` (C3, UCI) | the plumbing pilot, whose full-profile outcome informed Amendment 1 | never confirmatory; unit-level panel excludes them from both sides (13.3); batch proposal lets them join the pilot and reports sigma with and without them (addendum 10.4) |
| Bloomington water plant with the Locus solar site; GitHub advisories, OSV-Go and NVD | linked sets (found), no detector exposure | drawn as one cluster in both pilots |
| Cincinnati calls and fire dispatch | linked set (candidate) | treated as linked until the owner decides |
| the 16 unit-level pilot groups | nothing yet | become pilot-exposed after the pilot; excluded from the confirmatory holdout by construction |
| the batch pilot clusters | nothing yet | the same, within the batch study only |

Cross-study exposure: a group in both pilot panels would be exposed in both. The unit-level panel and the batch panel
are drawn separately; the owner decides whether a cluster may serve in both pilots (decision 5) and whether exposure in
one study excludes a group from the other study's confirmatory set (decision 6). The five plumbing groups are the only
groups the registry (`linked_sets.json`, `exposed_groups`) records as exposed today.

## 7. Decisions for the owner (none taken here)

1. Unit-level pilot size (16, 24 or 32), minimum per category, seed, and the exposure rule for the plumbing groups
   (`variance_pilot_design.md` 13.5).
2. Batch pilot: contrasts (at most three), the sizing sigma rule, pilot size P, minimum M, seed S, whether the five
   exposed groups join (addendum 9).
3. Primary analysis for both pilots: cluster bootstrap on per-cluster paired differences (proposed) or a mixed model
   with a curator effect (needs a dependency decision, ADR-0001).
4. The planning inputs: the upper ratio r to plan with (1.4 proposed), the smallest effect (0.05) and the Holm family size.
5. Whether a cluster may be in both pilot panels.
6. Whether exposure in one study excludes a group from the other study's confirmatory set.
7. Whether Cincinnati calls and fire dispatch are linked.
8. The floor assumptions (15 percent test share; 20 positives; k at least 10) and the date the freeze is lifted for a pilot.

Authorizing a pilot, approving this design and approving a confirmatory sample size are three separate gates.
