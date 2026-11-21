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
- openFDA: every record set shows variable structure (optional paths 64 to 124), so
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

# Update 5 (2026-11-21): Open Contracting, USAspending, TLC, domains and diminishing return

Discovery (what exists), acquisition, readiness and experiments are separate here: nothing in this
update is an experiment.

## Open Contracting registry (136 publications read)

Each publication page states its own licence. Counts of stated licences: CC BY-NC-SA 4.0 41 (mostly
OpenTender), CC BY 4.0 19, PDDL 16, Mexican open-use licence 14, none stated 10, CC0 5, OGL 4, others.
The registry is the curator; the original publisher's terms are the ones that count. For the
publications that are acquired:

| Publication | Registry licence | Original publisher check | Decision |
|---|---|---|---|
| Ville de Montréal | CC BY 4.0 | confirmed: donnees.montreal.ca CKAN licence `cc-by` (Creative Commons Attribution 4.0 International) | accepted, experiment-ready (C2b and C6) |
| Georgia State Procurement Agency | CC0 | not read | acquired, excluded from counts |
| Dutch Ministry of Economic Affairs | CC0 | not read | acquired, excluded from counts |
| Zambia Public Procurement Authority | CC BY 4.0 | not read | acquired, excluded from counts |

Permissive publications of other producers with a bulk file under the size limit (Bulgaria, Honduras)
or above it (Chile, Colombia, Paraguay, Peru, Brazil, Guatemala, Ecuador: 1 to 5 GB) were not acquired.
Publications under CC BY-NC-SA (OpenTender, 41 of 136) are a research-only class, not acquired in this
pass because they are re-compiled from EU tender notices. All OCDS records are contract awards and
notices, not payments.

Montréal: 305922 compiled releases 2011-2025; the stable whole-contract hash sample (1 of 10) has
61102 view rows (30551 awards, 8930 suppliers); party references resolve completely; depth 6 but only
24 paths and 1 optional path, so it is a regular nested structure (adds depth, little schema
variability).

## USAspending and NYC TLC

- USAspending: public domain by 17 U.S.C. 105; Treasury added a licence notice in 2019 stating
  commercial and non-commercial reuse (GAO follow-up; the notice itself was not retrievable). The
  monthly award archives download with curl, but the Python client cannot verify the host's TLS chain
  (self-signed certificate in chain). Certificate checking was not disabled, so nothing was acquired.
  Records are contract actions with obligated amounts, not payments.
- NYC TLC: the NYC Open Data law says no use restrictions; the agency page returned 403 to automated
  access and the dataset metadata has no licence field. Kept as a candidate, not collected.

## C2b after this update

Four families (Online Retail without a view, MHRA, NHSBSA, Montréal), three experiment-ready, in three
domains (retail purchases, public payments, municipal contract awards). See
`verification/transactional_coverage.md` for the independence dimensions and fault applicability.
Diminishing return: more same-template UK ledgers add producers but not mechanisms; the missing
domains are card or bank payments, utility and telecom events, transport fares, inventory movements, and
no open source with a verified licence was found for them.

## Counts by stage (independent groups; experiment-ready counts independent groups)

| Stratum | Acquired families | Rights-verified groups | Experiment-ready groups | Target |
|---|---:|---:|---:|---:|
| C2b | 4 (+3 OCDS acquired, unverified) | 4 | 3 | 30 |
| C3 | 41 | 2 | 1 | 40 |
| C4 | 16 systems, 1 curator | 1 | 1 | 28 |
| C5 | 2 | 2 | 2 | 36 |
| C6 | 5 | 5 | 4 | 30 |

## Not done in this pass

- Monash upstream terms (13 families), RelBench and CTU terms, independent C4 producers, HMRC.
- Spreadsheet support (decision in the transactional coverage note: not justified now).
- Targeted L3 mutation runs: `make mutation-focus` runs the whole pinned test suite to map tests to
  mutants and needs the full dev and deep environment (torch, mutmut). That environment is not
  installed in this working copy, so no mutation result exists for the new modules.

# Update 6 (2026-11-21): publisher-level OCDS verification, bike-share, readiness

Separate stages: licensing, scientific readiness, experiments (none executed).

## OCDS publishers (rights read at the publisher)

| Source | Decision | Basis |
|---|---|---|
| Georgia SPA | open (CC0), experiment-ready | the Agency's Publication Policy states CC0 for its OCDS 1.1 data; read in the 2023-02-28 Wayback copy because the live host's TLS chain does not verify; terms of service allow third-party exposure and forbid circumventing API limits |
| Zambia ZPPA | open (ODC-PDDL), experiment-ready | `zppa.org.zm/ocds-license` read live; the registry says CC BY 4.0 (discrepancy, publisher's statement governs, both permit this use); personal data only as authorised; security and defence contracts excluded |
| Netherlands (TenderNed) | unclear, not accepted | TenderNed says announcements are public and offers datasets but states no reuse licence; the registry's CC0 was not found at the publisher; public availability is not permission |

Every acquired export has one compiled release per contracting process, so one award row is one process
and a repeated row is a real duplicate. Georgia's registry export ends in 2019 and omits simplified
procurements; Zambia publishes selectively; all three describe awards and contracts, not payments.

## Bike-share (non-procurement transactional)

Capital Bikeshare and the Citi Bike Jersey City files: research_only under the operator's Data License
Agreement (any lawful purpose, analysis allowed, no stand-alone redistribution), read at the publishers.
1947784 and 319159 rental events (Sep to Nov 2024), no monetary amount, no rider identifiers; start and
end coordinates and station names are dropped. One operator and one trip schema, so one family, two
systems, one independent group.

## Counts by stage (independent groups for experiment-ready)

| Stratum | Acquired families | Rights-verified groups | Experiment-ready groups | Target |
|---|---:|---:|---:|---:|
| C2b | 7 (Online Retail, 2 UK ledgers, 3 OCDS accepted, bike-share; Netherlands not counted) | 7 | 6 (all but Online Retail) | 30 |
| C3 | 41 | 2 | 1 | 40 |
| C4 | 16 systems, 1 curator | 1 | 1 | 28 |
| C5 | 4 | 4 | 4 (OpenAlex, Stack Exchange, Georgia, Zambia) | 36 |
| C6 | 7 | 7 | 6 | 30 |

Georgia and Zambia appear in C2b, C5 and C6 under one provenance identity each. Their C5 entries rely
on native OCDS relations only (award, contract, party): a shallow relational structure that adds two
producers but not deep multi-table schemas.

## Diminishing return

Seven C2b families now cover four mechanisms (purchase lines, payments, contract awards, rental events).
The three OCDS producers and the two UK ledgers repeat a mechanism; more of them would add producers
and no mechanism. The next useful C2b sources have a different mechanism: card or bank payments,
utility or telecom usage events, subscription events, inventory movements.

## Mutation verification of the new L3 modules

Investigation, in order (no thresholds, policy or cache configuration were changed):

1. `make mutation-focus MODULE=research.readiness` needs the complete pinned environment. One exists:
   the conda environment `etl-benchmark` (Python 3.11.17, torch 2.14.1, mutmut 3.8.0). The `.venv`
   used for the fast checks lacks torch and mutmut.
2. The target runs the whole selected test suite once (`tests` and `research/tests`, markers
   `not real and not fault`, with the deselections of `pyproject.toml`) inside the copy under
   `mutants/`, to map tests to mutants. That is why one module still costs a full suite run.
3. The stats phase failed twice, with "runner returned 1". Running the same tests in the copy showed
   two genuine defects of this branch, not of the environment, both fixed:
   - six `test_dataset_catalog.py` tests read `data/catalog.json`, and `data/` is not part of the
     mutation copy (`also_copy` lists `verification` and `research`). Changing `also_copy` would edit
     `pyproject.toml`, which is a cache-invalidation file (`on_dependency_change = "rerun"`) and would
     discard the preserved mutation caches, so the catalog was moved instead to
     `verification/legacy_data_catalog.json`, a copied directory (the path in `dataset_catalog.py`,
     `coverage_matrix.py`, `data/README.md` and the design note follows);
   - `test_labelled_contracts.py::test_main_writes_every_problem...` failed because its fake `run_job`
     predated the `--seeds` option added earlier in this work; the fake now accepts `seeds`, and two
     assertions check the default seeds and the `--seeds` pass-through.
4. After these fixes the 139 focused tests pass in the complete environment. A full stats pass of
   the whole suite was not run to completion: the full suite progressed about 1 percent in five
   minutes in this session, so it is a multi-hour run, not a bounded one.

Status: no mutation verdict exists for `readiness`, `experimental_views`, `acquisition`,
`acquisition_validate`, `fault_protocols` or the changed `dataset_catalog`; the 95 percent threshold is
not evaluated; certification stays pending. The next step is one `make mutation-focus` run per module in
the complete environment on a machine that can spend the hours.

# Update 7 (2026-11-21): mutation measurements of the new L3 modules, defects found, job records, FRED

## Why the mutation statistics phase is expensive, and the workflow that worked

Root cause. `mutmut run` first runs the whole selected suite once to learn which tests cover which
function ("Running stats"). The selection in `pyproject.toml` is `tests` plus `research/tests` (4548
tests); in this session it ran at about 4 percent per 20 minutes, so a complete pass takes many hours.
`make mutation-focus` deletes `mutants/mutmut-stats.json` each time, so every module pays that cost again.
Stats can be reused only when no test or source changed, which a development loop never allows.

Two defects of this branch, not of the environment, made the stats phase fail with "runner returned 1";
both were fixed earlier in this branch (the catalog moved to a copied directory, and a stale
`--seeds` test). A third environmental detail: the forkserver worker crashed once with a bus error
until the controller's fixed environment (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
`MKL_NUM_THREADS=1`, `PYTHONHASHSEED=0`, empty `PYTHONPATH`, `python -P`) was used, as
`verification/mutation_run.py` does.

Workflow used (supported mutmut features only; no flag invented, no configuration changed): per module,
`mutmut run "research.<module>.*"` with `PYTEST_ADDOPTS="-k <test file>"` restricting the pytest selection
to that module's own tests. The stats pass then takes seconds and the run minutes. This is a lower bound on
kills (tests of other files could only kill more) and it is development feedback, not release evidence:
the release evidence is still the sharded campaign of `make verify-deep`.

## Results against the L3 threshold of 95 percent

Killed share, counting only `killed` (suspicious and timeout are not counted as kills):

| Module | Mutants | Killed | Survived | Suspicious | Timeout | Killed share |
|---|---:|---:|---:|---:|---:|---:|
| `research/readiness.py` | 450 | 450 | 0 | 0 | 0 | 100.0 percent |
| `research/acquisition.py` | 385 | 377 | 4 | 4 | 0 | 97.9 percent |
| `research/acquisition_validate.py` | 668 | 654 | 12 | 2 | 0 | 97.9 percent |
| `research/dataset_catalog.py` | 782 | 771 | 5 | 4 | 2 | 98.6 percent |
| `research/fault_protocols.py` | 870 | 843 | 22 | 5 | 0 | 96.9 percent |
| `research/experimental_views.py` | 1815 | 1744 | 64 | 6 | 1 | 96.1 percent (re-measured at 2163 mutants after later additions: 2076 killed, 96.0 percent) |

Raw counts: `verification/evidence/dataset_registry_v2/mutation_focus_2026-11-21.json`. The first measurements
before the test work were far lower (readiness 54 percent, acquisition 61 percent, acquisition_validate
34 percent, fault_protocols 63 percent, dataset_catalog 66 percent, experimental_views 33 percent, with
many `no tests` mutants in the command-line and builder code), so the gain comes from new exact tests, not
from excluding code.

Surviving mutants, by kind (not each one reviewed individually, none approved as equivalent): path
mutants that change only the letter case of a directory or file name, which a case-insensitive
file system (macOS APFS) cannot tell apart; arguments that equal their defaults (`ignore_index`,
`encoding="UTF-8"`, `maxsplit`); sample-boundary comparisons that need a hash exactly on a cut point;
and a few mutants of parameters that are accepted but unused. No equivalence approval was made.

## Defects found by the tests and fixed

- `acquisition_validate.json_shape` counted a path once per occurrence, so a path repeated inside an array
  could look present in every record; presence is now a share of records. Evidence regenerated: optional
  paths of openFDA events 33 to 64, Open Food Facts 9924 to 9964, OpenAlex works 14 to 46, Georgia 17 to
  18, Zambia 57 to 62. The earlier figures understated schema variability; documents were corrected.
  The remaining validation numbers did not change.
- `fault_protocols.conformance` compared the reference rows of a ledger with themselves (a check that
  could not fail) and did not draw the scaled rows from the test partition. It now injects over the whole
  table restricted to the test rows and checks the reference rows, the truth rows and the changed rows.
- `experimental_views.spend_view` parsed dates day-first, which turns an ISO date 2024-02-03 into
  3 March. ISO dates are now parsed as written. No acquired ledger holds ISO dates (0 of 5033), so the
  existing views are unchanged (the manifest checksums are identical).
- `experimental_views.build` was split into one builder per source so that each can be tested; outputs are
  byte-identical (same manifest checksums).
- Redundant code that only created unkillable mutants was removed (a type table identical to the type
  name, an unused salt argument, a BOM replace that the following regular expression already did).

## New source and one rejection

- CC-IN2P3 SLURM job records (Zenodo record 18668107, CC BY 4.0 at the depositors, who are the producing
  centre's staff): 233716 jobs in the id-sampled view over two months, experiment-ready in C2b, no
  monetary amount. About one job in five ends failed, cancelled, timed out or out of memory: a natural
  scheduler outcome and baseline, not an ETL fault.
- FRED-MD (Monash record 4654833): restricted. The FRED terms of use prohibit using FRED content in
  connection with the development or training of any software program or machine learning, and
  anomaly detectors are trained on the data. The compiler's CC BY label does not lift the clause.
- Discovered, not acquired: SURF Lisa HPC traces (Zenodo 13625495, CC BY 4.0, parquet files and large
  monitoring tables), F-DATA Fugaku jobs (Zenodo 11467483, CC BY 4.0, 27 GB), Olist Brazilian e-commerce
  (Kaggle, CC BY-NC-SA 4.0 per a secondary source, login required, not acquired), Low Carbon London smart
  meters (4TU CC BY 4.0, 137 MB zip above the size limit).

## Counts by stage after this update

| Stratum | Acquired families | Experiment-ready groups | Target |
|---|---:|---:|---:|
| C2b | 8 (Online Retail, 2 UK ledgers, 3 OCDS, bike-share, SLURM; Netherlands not counted) | 7 | 30 |
| C3 | 40 | 1 | 40 |
| C4 | 16 systems, 1 curator | 1 | 28 |
| C5 | 4 | 4 | 36 |
| C6 | 7 | 6 | 30 |

The mutation figures concern verification of software, not scientific results. No experiment was run.
Certification stays pending: only the full sharded campaign of the exact release commit can certify.

# Update 8 (2026-11-21): discovery wave, new experiment-ready sources, candidate ledger

Discovery is not acquisition. This update separates what was searched, what was acquired and what is ready.

## Discovery coverage

Searched in this wave: Zenodo (25 keyword queries across the five categories, 186 open-licence records
read, 52 candidates triaged into `verification/evidence/dataset_registry_v2/candidate_ledger.json`),
publisher pages and APIs of ClinicalTrials.gov, Crossref, Open Library, NOAA GHCN-Daily, Open Power
System Data, Google ClusterData, the Parallel Workloads Archive, the City of Chicago portal, Capital
Bikeshare and Citi Bike. Searches not yet run: Figshare, Harvard Dataverse, OpenML, Hugging Face, Kaggle
(login), non-English portals, national statistical agencies, and Zenodo queries by publisher.

Ledger by status (52 candidates): experiment-ready 9; accessible and eligible, not yet acquired 10;
needs a bounded extraction (large files) 7; permission pending 6; needs a parquet reader 3;
synthetic testbeds or staged attacks kept outside natural counts 5; structurally unsuitable 2; unclear
2; blocked (TLS, access, authentication, size, firewall) 6; others 6. Every entry names the next
step.

## New acquisitions and readiness (exact figures)

| Source | Stratum | Class and evidence | Result |
|---|---|---|---|
| ClinicalTrials.gov, 12000 studies starting in 2023 | C6 | open: terms read in an archived copy (the live page needs a browser) | experiment-ready: depth 12, hundreds of paths, about 90 percent optional; investigators, officials and contacts dropped and 203 e-mail addresses in free text redacted |
| Crossref, 2000 random works | C6 | documented as unrestricted metadata; the literal page could not be quoted | acquired and structurally valid, rights pending, not counted: depth 6, 54 paths; references leave the sample (2 of 23729) so no relation |
| UCI 357, 360, 374, 560, 799, 849, 851 | C3 | CC BY 4.0 on the UCI page | experiment-ready after a view with an exact time format; 5 independent groups from 7 tables (357 and 374 share a research team: grouped); uci:275 (Capital Bikeshare 2011-12) left out as redundant; uci:172 and uci:492 rejected (repeated timestamps) |
| Google ClusterData2019 | C4 | open (CC BY, README of the publisher) | not acquired: json.gz shards are 60 to 465 MB, the 11 MB parquet shard needs a parquet reader |
| Parallel Workloads Archive | C4 | free for researchers, cite the archive | blocked: the host's firewall refused automated requests after a burst; not bypassed |

Defects found while doing this: a time column parsed day-first turns ISO dates into swapped months (fixed
earlier); e-mail addresses inside free text survived a key-based privacy filter, so a redaction step was
added and tested.

## Coverage progression (experiment-ready independent groups)

| Category | Initial | New | Final | Target | Remaining gap |
|---|---:|---:|---:|---:|---:|
| C2b | 7 | 0 | 7 | 30 | 23 |
| C3 | 1 | 6 | 7 | 40 | 33 |
| C4 | 1 | 0 | 1 | 28 | 27 |
| C5 | 4 | 0 | 4 | 36 | 32 |
| C6 | 6 | 1 | 7 | 30 | 23 |

Distinct provenance identities across categories: 21 (MHRA, NHSBSA, Montréal, Georgia, Zambia, Lyft,
CC-IN2P3, Melbourne, Loghub, Stack Exchange, OpenAlex, openFDA, Open Food Facts, ClinicalTrials.gov,
five C3 UCI groups); Georgia, Zambia, Montréal and OpenAlex count in several categories. C4 did not
advance: the two largest sources are blocked by size and by a firewall.

## Taxonomy note: job records

CC-IN2P3 SLURM job records are operational events (usage records of a compute service), not purchases or
payments. They stay in C2b until a taxonomy change is approved. The scientific consequence: a claim about
payment-like transactions must exclude them (they have no amount), and the same data would fit C4 better
(event records with a state machine). C2b without them has 6 groups.

## Technical status

Tests: the focused research tests and the mutation inventory pass in the complete environment (new tests
for the study, bibliography, job, series and redaction views). Focused mutation of
`experimental_views.py` after the additions: 2076 of 2163 killed (96.0 percent). No full campaign and no
certification. No experiment was run.

## Update 9: bounded range acquisition, panels, relational tables and the Borg prefix (2026-11-21)

**Capability.** `Snapshot.fetch_range` stores a byte range of a remote file only when the server answers
`206` with a consistent `Content-Range` (offset, length and `bytes a-b/total` are checked; a `200` full
response, a missing or malformed header, an oversized body and a foreign host are rejected). The manifest
entry is marked `partial`, records the exact range and the reported total size, and its checksum is that of
the fragment, never of the whole file. `gzip_prefix_lines` decodes a gzip stream from its start under an
output cap, keeps only complete lines and reports whether the stream ended; such a sample is a prefix in file
order, not a random sample. Both are covered by exact tests and a focused mutation run.

**Wave A1 (accessible, legally eligible).** Seven Zenodo records were acquired and checksummed:

| Record | Outcome |
|---|---|
| RKI emergency-department surveillance (24396501) | experiment-ready C3 panel, 343682 rows |
| RKI COVID-19 hospitalisations (24388435) | experiment-ready C3 panel, 292264 rows; same producer, one group `rki_surveillance` |
| 3PFL linked contracts, grants, patents (3369582) | five-table C5 view with measured key orphans (contract links 3 of 14282, grant links 2 of 35989, patent links 19 of 50271); upstream terms pending, so not ready |
| DataCenter traces (14564935) | acquired; provenance of the traces undeclared; not ready |
| AEGIS vehicle sensors (820576), NYC telematics (6647220) | acquired; GPS positions need a privacy decision; no view |
| PURE requirements (7118517) | PDF documents; structurally unsuitable |

**Wave A2.** Google ClusterData 2019 cell a: the bucket honours ranges (206 verified). A 30 MiB prefix of a
collection-events shard and a 40 MiB prefix of an instance-events shard were read (prefix sample, not random).
Result: of 299716 collections in the prefix only 284 have two events and none three, because shards split
lifecycles by id. The data are a valid tabular event sample but not an event-sequence source, so Google is
structurally valid and scientifically ineligible for C4. The zip central directories of two large Zenodo
records (CLUE 7119953 holds one 635 MB compressed member; 3549604 holds 2776 members) were read with ranges;
no member was extracted. MetroPT2, Swiss Dwellings and Open Library were not processed in this update.

**Reclassification.** CC-IN2P3 SLURM jobs move from C2b to C4: they are usage events without amounts. C2b now
has 6 ready groups; C4 has 2 (Loghub, CC-IN2P3).

**Wave A3.** `pyarrow` is absent from both environments; adding it changes `pyproject.toml` and
`environment.yml` and would invalidate preserved mutation caches, so the Parquet candidates remain deferred
for an owner decision.

**Ledger by machine** (`candidate_ledger.json`, 52 unique entries). Participations: C3 24, C4 13, C2b 11,
C6 8, C5 8.

| Ready groups | Initial (Update 8) | Final |
|---|---:|---:|
| C2b | 7 | 6 |
| C3 | 7 | 8 |
| C4 | 1 | 2 |
| C5 | 4 | 4 |
| C6 | 7 | 7 |

Targets (30, 40, 28, 36, 30) are unchanged and not met. No experiment was run.
