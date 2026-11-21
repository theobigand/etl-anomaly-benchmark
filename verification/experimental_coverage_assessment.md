# Readiness and experimental-coverage assessment (2026-11-21)

Status: planning document for the freeze. No detector was run, no inferential statistic was computed,
and no source was selected or tuned using detector results. Counts below are experiment-ready
groups from `verification/evidence/dataset_registry_v2/readiness.json`; a count is never read as
statistical power.

## What is ready, and with what dependence structure

| Stratum | Ready groups (datasets) | Dependence structure for later source-clustered analysis |
|---|---|---|
| C2b transactional | UK ledger MHRA (1), UK ledger NHSBSA (1), Montréal contracts (1), Georgia procurement (1), Zambia procurement (1), Lyft bike-share (2), CC-IN2P3 SLURM jobs (1) | MHRA and NHSBSA share a publication template; the three OCDS producers share a standard and a domain but not records or systems; the two bike-share cities share an operator and a schema; the SLURM job records are one centre and a different mechanism (compute-job events, no money) |
| C3 time series | Melbourne pedestrian (1) | one city, one sensor network |
| C4 logs | Loghub collection (16) | one curator; the 16 systems are separate systems but one group |
| C5 relational | Stack Exchange (10 sites), OpenAlex (1), Georgia (1), Zambia (1) | the ten sites share a platform and schema; Georgia and Zambia carry only three native entity types |
| C6 nested | openFDA events, OpenAlex, Open Food Facts, Montréal, Georgia, Zambia (1 each) | OpenAlex, Montréal, Georgia and Zambia reuse sources already counted in C2b or C5 |

Cross-stratum overlap: Georgia, Zambia and Montréal appear in C2b and C6 (and Georgia and Zambia in C5),
OpenAlex in C5 and C6. For a claim that pools strata the independent unit is the provenance
identity: the 19 group slots across strata reduce to 13 distinct provenance identities (MHRA, NHSBSA,
Montréal, Georgia, Zambia, Lyft, CC-IN2P3, Melbourne, Loghub, Stack Exchange, OpenAlex, openFDA, Open Food Facts).
Which dependence level is right depends on the claim:

- a claim about detector behaviour across structures (tabular, temporal, sequence, relational,
  nested) uses the structure as the factor and the provenance identity as the random effect;
- a claim inside one structure uses the independent group in that stratum, and the schema family as a
  second level where groups share a standard (OCDS, the GOV.UK spend template, the Lyft trip schema);
- a claim about domains would use the domain, and C2b has five mechanisms (purchase lines, payments, contract awards, rental events, compute-job events) but three of the seven groups
  are one mechanism (contract awards).

## Anomaly-type feasibility (controlled injection only)

Eligible ready groups per protocol (a group counts once per protocol):

| Protocol and mechanisms | Ready groups | Feasibility |
|---|---:|---|
| P-TAB scale, duplicate, invalid code, cross-field (transactional tables) | 7 (C2b) | feasible; groups are not independent in domain, so any pooled claim is conditional on the three mechanisms |
| P-TS level shift, drift, missing interval | 1 | exploratory only; one network cannot support a claim about time series |
| P-SEQ order, drop (event sequences) | 1 (one curator, single streams of 2000 events) | exploratory only |
| P-REL broken reference | 4 | feasible; relational depth is low for OCDS; natural orphan baselines exist in Stack Exchange and Zambia |
| P-NEST missing required field, type change | 6 | feasible; schema complexity differs widely (openFDA and Open Food Facts rich, Montréal regular) |

Important mechanisms without suitable data: payment-specific faults (no source has monetary
payments outside the two UK ledgers, which are censored views), currency and unit faults in more than one
currency domain, multi-line inconsistency beyond NHSBSA, inventory or stock movement faults, usage-billing
faults, real timestamps for P-SEQ gap and delay mechanisms (Loghub samples have none usable), and a
chronological split for openFDA (two receipt dates only).

Substantial acquisition with insufficient readiness: C3 (41 families acquired, 1 ready: upstream terms of 13 Monash
families unread), C2b OCDS (the Netherlands acquired but rights unclear), Online Retail (acquired, no view).

## Natural irregularities that stay baseline conditions

- Stack Exchange: 5 to 29 percent of votes point to deleted posts; links to other sites.
- OpenAlex: references to works outside the 1000-work sample (all of them).
- Zambia: 7 of 1368 contracts reference an absent award; selective publication.
- Georgia: 151 awards without amount; the export ends in 2019; simplified procurements absent.
- NHSBSA: 35 percent of rows share a transaction number (multi-line payments); credit notes in both UK ledgers.
- MHRA: non-contiguous returns; both ledgers publish only payments above 25000 pounds.
- Bike-share: negative and multi-day durations, 23 percent of Washington trips without a start station.
- openFDA, Open Food Facts, Zambia: optional-field and type variation (the schema-drift baseline).
- Pedestrian counts: sensor outages and strong seasonality.

## Injection protocols that still need realism validation

- Severity grids are design ranges, not failure rates; no field data constrain them. A sensitivity
  analysis over the grid (not a single setting) is required before any claim.
- P-SEQ: single 2000-event streams are not sessions; the sequence unit is weak.
- P-NEST: required-ness is inferred from presence above 0.95, not from a published schema; this should
  be validated against the OCDS and openFDA schemas where they exist.
- P-REL on OCDS: only three entity types; results do not transfer to deep relational schemas.
- P-TS: no natural drift labels exist to compare an injected drift with a real one.

## Recommendations before the freeze is lifted (for owner decision)

1. Pre-register the design before any detector touches a new dataset: strata, protocols, severity grids,
   seeds, partitions (reference, validation and test as in `anomaly_protocols.md`), the matching rules, the
   alert-budget operating points and the exclusion rules, with the unit of inference stated per claim.
2. State per claim its dependence level (provenance identity, schema family, domain) and the model
   (source-clustered or hierarchical); do not use the number of datasets or publishers as the sample size.
3. Separate exploratory protocol development (this phase, fixtures and conformance only) from a
   confirmatory run on a sealed set of groups chosen by provenance and structure, not by outcome.
4. Fix a sealed hold-out of groups before the first run, and record which are sealed.
5. Close the largest data gaps first or narrow the claims: C3 and C4 can only support exploratory
   statements today; C2b supports claims only about the three mechanisms it contains.
6. Decide whether the numerical targets (C2b 30, C5 36, C6 30, C3 40, C4 28) remain the design
   targets or are restated as a minimum with stated limits. This needs a methodological argument that
   is not written here; the targets are unchanged.
