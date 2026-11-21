# Dataset acquisition report (T434-T437, issue 131)

Date: 2026-11-21. Scope: discovery, licence verification, acquisition, structural validation.
No detector, pilot or neural run was executed or modified. Raw data lives under the gitignored
`data/acquired/` and `data/loghub/`; only manifests and validation results are tracked.
Reproduce: `python research/acquisition.py <source> --snapshot <id>`, then
`python research/acquisition_validate.py`, then `python research/dataset_catalog.py gap`.
Sources are configured in `verification/evidence/dataset_registry_v2/acquisition_sources.json`;
decisions and stages per entry are in `acquired_sources.json`.

## Stages reached (nothing is "ready for experiments" yet)

| Source | Stratum | Licence class and evidence | Acquired | Structural check | Scientifically eligible |
|---|---|---|---|---|---|
| Loghub 2k samples (16 systems) | C4 | research_only: logpai/loghub README "License" | yes | row counts only; timestamps cover under a week in 15 of 16 | as event sequences, not as time series |
| Monash forecasting archive (21 records) | C3 | open for the compiler: Zenodo metadata `cc-by-4.0` on every record; upstream terms of Kaggle, AEMO, KDD Cup and others not read | yes | series, frequency, start stamps and missing shares read | 18 of 21 families (see below) |
| openFDA drug events, drug labels, food enforcement | C6 | open: CC0 at open.fda.gov/terms (GMDN content only in device endpoints, not used) | yes | depth, arrays, optional fields measured | drug events and labels; food enforcement kept out of the count (depth 2, no arrays) |
| Stack Exchange data dump, 10 sites | C5 | open: CC BY-SA per the Creative Commons Data Dump terms; rows also carry per-post licence 2.5/3.0/4.0 | yes | 9 foreign keys checked on every site | yes, as one family |
| Open Food Facts (products, Open Prices) | C5, C6 | open: ODbL for the database, DbCL for contents, CC BY-SA for images (terms of use page) | no | not run | not assessed |
| OpenAlex | C5, C6 | not verified: the API now asks for a key tied to an e-mail address, which was not provided | no | not run | not assessed |
| CTU Relational | C5 | unclear: no licence on the "About" page | no | not run | no |
| RelBench upstream datasets | C5 | unclear or research_only candidate (see register) | no | not run | no |

## Rejected inside the acquired data

- Monash CIF 2016: no start timestamps and 48 of 72 series are artificial.
- Monash solar 10-minute: simulated, not observed.
- Monash wind 4-second: same collection pipeline as the solar 4-second series, counted once.
- openFDA food enforcement: semi-structured but flat (depth 2, no arrays); it does not test nested structure.
- Not fetched for size: London smart meters (220 MB), Kaggle Wikipedia traffic (145 MB), wind farms minutely (71 MB), weather (39 MB), Kaggle web-traffic weekly, temperature-rain.

## Independence analysis

Counts keep three levels (gap report): families (what a stratum target counts), systems and publishers.

- C3: 43 families and 26 publishers. The 18 Monash families all carry publisher
  `monash_compilation`, but their originals come from different institutions. The compiler's licence
  is verified; the originals' are not. Possible dependency to check: KDD Cup 2018 air quality and
  the Beijing series already in the first pool.
- C4: 16 systems, 1 curator. Claims over C4 must say so.
- C5: 1 family and 10 systems. The ten sites share a platform, schema and user population, so they
  count once. They are distinct communities, which gives ten data-generating populations, not ten
  independent pipelines.
- C6: 2 families, both from one publisher (FDA); different reporting systems and schemas.

## Natural facts found that change the protocol

- Stack Exchange: 5 to 29 percent of `Votes.PostId` values point to posts absent from the dump
  (deleted posts), and some `PostLinks.RelatedPostId` point to other sites. A referential-integrity
  fault study must baseline these natural orphans and must not count them as injected faults.
  Orphans are not evidence of ETL failure: the collection is not a complete database snapshot.
- Monash: missing shares reach 40 percent (rideshare); a missing-value fault study needs a baseline.
- openFDA: every record set shows variable structure (optional paths 33 to 124), so
  schema-drift detection needs a baseline of natural variation.

## Anomaly applicability matrix

N = natural label, S = suspected natural without label, I = controlled injection into real data,
X = not applicable.

| Mechanism | C3 Monash | C4 Loghub | C5 Stack Exchange | C6 openFDA |
|---|---|---|---|---|
| Statistical and contextual outliers | S, I | S, I | I | I |
| Collective anomalies | S, I | S, I | X | X |
| Missing and invalid values | S (natural gaps), I | I | I | S (optional fields), I |
| Duplicates | I | I | I | I |
| Schema violations and type inconsistency | X | X | I | S (type variation), I |
| Nested-structure corruption | X | X | X | I |
| Referential-integrity violations | X | X | I after natural-orphan baseline | X |
| Event-order violations | I | I | I (timestamps of posts) | X |
| Temporal gaps | S, I | X | I | X |
| Distribution shift, volume, freshness | I | I | I | I |

No dataset acquired here carries confirmed anomaly labels. Everything counted as a fault will be a
controlled injection and will be reported as such. The earlier natural-label evidence (SKAB and NAB)
is unchanged.

## Gaps public collection cannot fill now

- C5 reaches 1 family. More relational families need rights evidence that public sources did not give
  (CTU, RelBench upstreams) or a key tied to a person's e-mail (OpenAlex). Several tables from one
  database never count as several sources, so 36 families is not reachable from the sources found.
- C6 has 2 families. Open Food Facts nested JSON and OpenAlex nested works are the candidates.
- C4 lacks independent producers: Loghub is one curator, and public production logs with reuse
  terms were not found.
- C3 exceeds its target by count, but without natural labels beyond SKAB and NAB.

## Targets (T437)

The numeric targets stay unchanged. Two recommendations, not applied: (1) C1 and C2 targets are met by a
schema criterion that does not measure anomaly mechanisms, so they should not be read as coverage;
(2) C5 and C6 targets of 36 and 30 are not realistic with public data and should be restated
as a minimum of 15 families with a stated limit, or kept as aspirations. A decision is needed.

## Continuation plan

1. Open Food Facts bulk export or API (ODbL) for C6 and, with Open Prices, C5; privacy: drop contributor names.
2. OpenAlex through the bulk snapshot (CC0) if an API key is not authorised.
3. Read the upstream terms of RelBench (Kaggle H&M and Avito, Stack Exchange, Ergast, AACT) and ask
   the CTU maintainers for dataset-level terms.
4. T437: separate transactional from categorical tables by key structure and repeated entities.
5. Fetch the large Monash records and Loghub-2.0 only if the batch protocol needs them.

# Update 2 (2026-11-21): OpenAlex, Open Food Facts, T437, Monash upstream, C4 candidates

## Decisions applied

- OpenAlex: keyless API only, no key, no e-mail. Anonymous budget is 1000 credits per day shared by
  IP (a list request costs one credit). About 75 requests were used. Cursor paging needs a key, so a
  seeded `sample=1000` (seed 42) with page numbers was used instead. A key is not needed for this
  extraction; a larger one would need the selective S3 snapshot (not estimated yet, not started).
- C5 and C6 targets stay at 36 and 30. The provisional 15-family milestone is a planning step only.

## New acquisitions

| Source | Stratum | Class | Result |
|---|---|---|---|
| OpenAlex (1000 works, 3756 authors, 1520 institutions, 884 sources) | C5, and C6 as a second view of the same family | open (CC0) | the three foreign keys are complete (0 orphans in 3762, 4477, 990); `referenced_works` leave the sample by construction (24763 of 24763) and are not faults; author names and ORCID iDs are personal data and are dropped before use |
| Open Food Facts delta export (9688 products changed on 2026-11-10/11) | C6 | open (ODbL, DbCL) | depth 12, 359 array paths, 866 multi-type paths, about 10000 distinct paths; the search API answered 503 and 401 and was not circumvented, so the official delta export was used; contributor names must be dropped; ODbL share-alike applies to derived databases |

Open Prices was not collected (same service, API refusing).

## T437: transactional versus categorical

Operational rule (`transactional_signals`, `is_transactional`): a table is transactional when it has
an entity key (identifier-named, integer or text, at least 20 distinct values, at least 20 percent of
rows sharing a value) and an event column (amount, price, quantity, balance and the like) or a verified
time column. A float column is a measure, never a key.

Result on the 134 readable tables of C1 to C3: 1 transactional (Online Retail, UCI 352), 133 not
transactional. 56 tables (ADBench numpy files, no key columns to read) are not audited. The earlier
42 families of "transactional and categorical" are therefore categorical tables, not transactions, in
all but one case. The C2 target of 30 is not met for transactional data: the realistic count is 1.
Two earlier heuristics were rejected on the evidence (they flagged a student "application order" and
"MedOwnCostPctIncNoMtg" as keys). Sources with repeated entities but no event column (diabetes
130-US hospitals: patient number over encounters) are kept as repeated-entity records and are not
promoted. Historical strata are unchanged and the audit is in `transactional_audit.json`.

## Monash upstream terms (priority D)

Read at the publisher: sunspot is CC BY-NC 4.0 (WDC-SILSO), so the compiler's CC BY does not apply and the
family is `research_only`; the Melbourne pedestrian data is CC BY. Rejected for now as unclear: Vehicle
Trips (FiveThirtyEight repository without licence) and Bitcoin (scraped web graphs). The other 15
families keep the compiler's licence and are provisional (`upstream_status: not_verified`). KDD Cup 2018
air quality and the Beijing PM2.5 table (UCI 381) are the same city and pollutant from different
producers; they are grouped conservatively. C3 is 41 families, 26 publishers, 0 experiment-ready.

## C4 candidates

- Loghub-2.0 (Zenodo 8275861, labelled large corpora of the same 14 systems): the record says CC BY 4.0,
  the repository README says research use. The same systems are not new families; kept `research_only`,
  not fetched (HDFS 321 MB, Thunderbird 293 MB, Spark 230 MB).
- AIT log data set V1.1 (Zenodo 4264796, four testbeds, six days, two labelled attacks per testbed):
  CC BY-NC-SA 4.0 (`research_only`), but 3.4 GB and synthetic testbed logs. Deferred; synthetic data would
  not count as an independent natural source.
- Other candidates (public web-server access logs, cloud-platform traces) were not found with
  verifiable reuse terms in this pass.

## Target against experiment-ready coverage

| Stratum | Target | Counted families | Experiment-ready |
|---|---:|---:|---:|
| C1 flat tabular | 36 | 92 | 0 new, earlier protocols unchanged |
| C2 transactional | 30 | 42 categorical, 1 transactional | 0 new |
| C3 time series | 40 | 41 (provisional upstream) | 0 |
| C4 logs | 28 | 16 systems, 1 curator | 0 |
| C5 relational | 36 | 2 (Stack Exchange, OpenAlex) | 0 |
| C6 nested | 30 | 4 (openFDA x2, OpenAlex, Open Food Facts) | 0 |

"Experiment-ready" is zero for every newly acquired source: no injection protocol has been
designed per dataset yet, and upstream terms are open for most Monash families.

## Next highest-value tasks

1. Read upstream terms for the remaining 15 Monash families and fix their class.
2. Add the next relational and nested families: eligible RelBench upstreams after reading Kaggle,
   Stack Exchange, Ergast and AACT terms; GH Archive and other event APIs for C6; the OpenAlex S3
   snapshot only if a larger sample is justified.
3. Draft the per-dataset injection specification before any run, and re-audit the 56 unread tables
   for transactional structure.

# Update 3 (2026-11-21): readiness, T437 closed, upstream terms, overlap

## Readiness (contract: `verification/dataset_readiness_contract.md`)

Data acquired, scientifically validated and ready are different stages, and no experiment was run.

| Stratum | Acquired | Structurally valid | Scientifically eligible | Protocol-ready | Experiment-ready (independent groups) |
|---|---:|---:|---:|---:|---|
| C3 | 21 records, 2 after upstream checks | 2 | 1 | 1 | Melbourne pedestrian (1) |
| C4 | 16 systems | 16 | 16 | 16 | Loghub collection (1 group) |
| C5 | 11 | 11 | 1 | 1 | OpenAlex (1) |
| C6 | 3 | 3 | 2 | 2 | OpenAlex, openFDA events (2) |

The first experiment-ready dataset exists in each of C3, C4, C5 and C6. Against the targets
(C3 40, C4 28, C5 36, C6 30) the independent experiment-ready groups are 1, 1, 1 and 2. The
numerical targets are unchanged. The C4 group of 16 systems is one curator, so it counts as one
group for inference.

## T437 closed

190 C1 to C3 tables audited: 1 transactional (Online Retail, UCI 352), 133 tables without a repeated
entity key and an event column, 56 sources without keys by construction (36 ADBench numeric arrays,
20 NAB and SKAB sensor series). Recommended taxonomy: split C2 into C2a "categorical and mixed
tables" (41) and C2b "transactional or event data" (1, target 30). The historical C2 count (42) is
kept for compatibility but must not be read as transactional coverage. UCI Online Retail II (UCI 502,
same UK retailer, adjacent period) is not in the pool; if added, it is the same source family as Online
Retail and not a new one.

## Upstream terms of Monash families (read where the publisher's own page was found)

| Family | Finding | Status |
|---|---|---|
| Sunspot | CC BY-NC 4.0 at WDC-SILSO | verified, `research_only` |
| Melbourne pedestrian | CC BY on the City of Melbourne catalogue | verified, open |
| AEMO-based series (Australian electricity demand, 4-second solar and wind) | AEMO copyright notice allows use "as authorised"; no open licence found | unresolved |
| FRED-MD | FRED terms of use apply (free use, credit to FRED and the original source); no dataset-specific licence found | unresolved |
| Saugeen river flow | Water Survey of Canada data is usually Open Government Licence Canada; the Saugeen gauge record was not found | unresolved |
| US births | public-use files of NCHS have use conditions beyond the public-domain label of reports | unresolved |
| Vehicle trips, Bitcoin | no licence or scraped | rejected |
| Others (Kaggle competitions, KDD Cup, NN5, Tourism, hospital, car parts, weather, covid, traffic, rideshare) | not read | open |

These findings come from search results and publisher pages that were reachable. They are
recorded as unresolved where no authoritative licence text was found, not as accepted.

## Independence and overlap

- Stack Exchange: ten sites, one platform and schema, one family. OpenAlex: one family in two strata.
- KDD Cup 2018 air quality is grouped with UCI 381 (Beijing PM2.5) in clustered analyses.
- Monash series from the same producer (4-second solar and wind) count once.
- openFDA events, labels and recalls are three reporting systems of one publisher.
- Loghub: 16 systems, one curator; upstream log producers are not separately stated.

## Remaining scientific gaps (ordered)

1. C2b: one transactional table against a target of 30. This is the largest gap and no source for it is
   identified yet. Candidates to evaluate: retail and payment event datasets with explicit open licences.
2. C5 and C6: one and two experiment-ready groups. Next: relational databases from independent
   producers with read licences (RelBench upstream terms, CTU per-database terms), nested event APIs.
3. C4: independent producers beyond Loghub, with documented terms.
4. C3: upstream terms of 13 Monash families, and natural labels beyond SKAB and NAB.
5. Privacy review of Stack Exchange and Open Food Facts to unlock their views.
6. Per-dataset injection specification instances; all protocol content so far is a template.

## Whether the numerical targets are still appropriate

Not decided. The evidence so far: C1 and C2 counts overstate coverage; C5 and C6 availability of
public sources with clear terms is low; the 15-family milestone is a planning step. Any change needs a
methodological argument that has not yet been written, so none is proposed here.

# Update 4 (2026-11-21): transactional sources, privacy views, protocol conformance

## Transactional sources (C2b)

| Source | Decision | Evidence |
|---|---|---|
| UK public spending, MHRA | accepted, experiment-ready | OGL v3 on the data.gov.uk record; 1330 transactions, 193 suppliers, 24 returns (2020-2024, not contiguous) |
| UK public spending, NHSBSA | accepted, experiment-ready | OGL v3; 3477 transactions, 154 suppliers, 24 monthly returns (2024-08 to 2026-09); 35 percent of rows share a transaction number with another line (multi-line payments, a baseline) |
| Charity Commission | rejected for now | 45 usable rows |
| NICE, Ofsted | deferred | spreadsheets saved as CSV; banner layout; a per-file reader is not justified yet |
| Tate | rejected | TLS certificate chain does not verify; certificate checking was not disabled |
| Instacart 2017 | not downloaded | the dataset terms (third-party copy of the May 2017 text) say access is not a licence grant; the original page was not retrievable |
| NYC TLC trip records | discovered, not collected | NYC Open Data law says no use restrictions; the TLC page returned 403 to automated access and the dataset metadata has no licence field; terms unread |
| Open Contracting registry | discovered | OCDS recommends CC0 or CC BY but each publication has its own licence; none read; UK Find a Tender is OGL according to its API documentation |

Independence: MHRA and NHSBSA are separate organisations with separate ledgers; they report on one
government template, so the shared template is a documented dependence, not shared observations.
Months of one organisation count once. C2b now has three families: Online Retail (UCI 352) and the two
ledgers, two of them experiment-ready; the target stays 30.

## Privacy views (Stack Exchange, Open Food Facts, UK spending)

- Stack Exchange: titles, bodies, comment text, display names, locations and profiles dropped; every
  user reference goes through one salted pseudonym mapping, so links resolve exactly as in the source.
  All 10 sites reach experiment-ready. Natural orphans (votes of deleted posts) remain and are a baseline.
- Open Food Facts: 18 contributor keys dropped at every depth, structure kept; a scan finds none left.
- UK spending: supplier names pseudonymised (sole traders can be individuals); descriptions, postcodes,
  VAT numbers and contract codes dropped.
- Pseudonymisation is not anonymisation. Derived views of CC BY-SA and ODbL data stay local.

## Protocol conformance (no detector, no metric)

`python research/fault_protocols.py` injects one controlled fault per protocol into the real views and
checks invariants: determinism, unaffected data unchanged, truth equal to the changed units, faults only in
the allowed partition, no change outside the named path, time order and sequence length. All five
protocols pass (`protocol_conformance.json`). For relational data the 2219 natural orphan references of
the Stack Exchange coffee site are reported as a baseline, never selected and never labelled. These are
mechanics checks on fixtures and small samples, not results.

## Counts by stage (independent groups)

| Stratum | Acquired | Experiment-ready groups | Target |
|---|---:|---:|---:|
| C2b | 3 families (Online Retail, 2 ledgers) | 2 | 30 |
| C3 | 41 families (21 Monash records) | 1 | 40 |
| C4 | 16 systems, 1 curator | 1 | 28 |
| C5 | 2 families (11 systems) | 2 | 36 |
| C6 | 4 families | 3 | 30 |

Online Retail itself has no experimental view yet.

## Remaining gaps, in order

1. C2b: 2 ready of 30. More ledgers need a per-organisation reader; NYC TLC and Open Contracting need
   their terms read where the publisher allows it. Instacart is closed without a licence.
2. C4: no independent log producer with documented terms found in this pass.
3. C5: RelBench and CTU terms still unread; OCDS publications could give relational and nested records.
4. C3: 13 Monash families' upstream terms.
5. C6: another independent nested producer beyond FDA, OpenAlex and Open Food Facts.
6. Claims: effective sample size for any claim equals the number of independent groups of its stratum
   (today 1 to 3), so no per-stratum statistical claim is supportable yet.
