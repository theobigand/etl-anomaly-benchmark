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

**Mutation status of Update 9 (focused, tests narrowed by keyword).** New range and gzip code in
`acquisition.py`: 208 killed, 35 survived (85.6 percent), below the L3 threshold of 95 percent; survivors are in
`open_range`, `_get_range`, `fetch_range` and `gzip_prefix_lines`. For `experimental_views.py` the narrowed run
cannot isolate the new functions (the shared time parser `_stamped` is exercised by the series tests, which the
filter excluded), so no figure is claimed. The new code is therefore not mutation-certified; closing the
survivors is open work.

## Update 10: Parquet, archives, process-mining logs and new groups (2026-11-21)

**Dependency.** `pyarrow>=21,<27` was added to `pyproject.toml` (runtime dependencies) and `environment.yml`
(conda). Installed: 25.0.0 in the conda environment `etl-benchmark` (Python 3.11, the newest conda-forge build
that solves there) and 26.0.1 in the local `.venv`; both pass the Parquet tests, and the lower bound is the first
major version with the batch and row-group API used. The change invalidates the previous mutation caches by
design (they hash the manifests); no earlier mutation figure is reused for the changed environment.

**Capabilities added.** `research/parquet_reader.py` (L3): footer-only inspection, column projection, row-group
selection, bounded record batches with a per-batch byte limit, a deterministic stride by global row position,
file-size limit, explicit errors for malformed or truncated files, and a sampling record (columns, row groups,
rows read and kept, truncation). `acquisition.py`: `zip_members`, `extract_member` (flat extraction, path
traversal, size and compression-ratio limits) and `zip_prefix_lines` (deflate prefix of the first member of a cut
archive). Unsupported: Parquet over HTTP without a full download (the footer sits at the end of the file, so a
remote Parquet file needs a complete bounded copy), encrypted or stored zip members, zip64 prefix of members that
are not the first.

**Ledger.** 63 entries (52 initial plus 11 discovered): 25 experiment-ready, 3 acquired with rights pending,
5 structurally unsuitable, 5 accessible and eligible, 6 permission pending, the rest blocked or synthetic.

**Candidates processed.** Parquet: SURF Lisa SLURM jobs (C4, ready, one row in 8 of 1.6 million jobs); F-DATA
Fugaku (C4, ready, April 2021 file only); PECD (permission pending: it repackages ENTSO-E inputs whose terms are
unread); idling positions of Munich shared vehicles (location data scraped from providers: rights and privacy
block, not acquired). Other: MetroPT2 (C3, ready, first 4.5 days by range); RKI series (C3 ready, Update 9);
3PFL (C5 ready after excluding the PATSTAT-derived patent table; blank keys are treated as missing, 143 natural
grant-to-grantee orphans of 11457); AEGIS (C3 ready, OBD signals only, relative time, no positions, dates or
other sensors; one driver, one vehicle, 33 trips, reduced privacy not anonymisation); NYC telematics (blocked:
undocumented columns); DataCenter traces (file names match public cloud traces, not an independent source);
Open Library (C6 ready from editions, depth 3; C5 not supported because dump prefixes in key-text order contain
12 editions with a fully resolved work in 192930); CLUE-LDS (view built from a 40 MiB zip prefix, rights pending);
Swiss Dwellings (structurally unsuitable: two single wide tables of 1.1 and 1.6 GB); Google ClusterData
(prefixes have 284 of 299716 collections with two events: no lifecycle continuity; full reconstruction would need
every shard of the cell, so no P-SEQ claim).

**4TU.ResearchData.** The repository's terms resource states CC0 for datasets without another licence. Real
event logs: BPI Challenge 2012 (financial institution), 2013 incidents (Volvo IT), 2015 municipality 5, Road
Traffic Fines, 2019 purchase orders (CC BY, 60 MiB prefix, 19484 complete cases), 2020 travel claims (CC BY-NC,
research only; domestic and international are one group) and Sepsis. Each is a C4 group; Road Traffic Fines and
BPIC 2019 also count in C2b through amounts (same provenance group). BPIC 2017 shares the provenance of 2012;
the other four 2015 municipalities share one group. Natural irregularities stay baselines: BPIC 2019 has event
times before 1999, Road Traffic Fines start at 1999-12-31.

**Other additions.** MovieLens ml-latest-small (C5, research only, no redistribution; four tables without
orphans). Candidates still actionable: BPIC 2014 (CSV log), BPIC 2018 (158 MB gzip XES: needs a gunzip-to-bytes
prefix helper), BPIC 2016 (CSV), more 4TU logs, MusicBrainz tables, CTU and RelBench upstream terms.

| Category | Initial ready (Update 9) | Newly ready | Final ready | Target | Gap |
|---|---:|---:|---:|---:|---:|
| C2b | 6 | 2 | 8 | 30 | 22 |
| C3 | 8 | 2 | 10 | 40 | 30 |
| C4 | 2 | 9 | 11 | 28 | 17 |
| C5 | 4 | 2 | 6 | 36 | 30 |
| C6 | 7 | 1 | 8 | 30 | 22 |

Distinct provenance groups with at least one ready category: 35 (21 before the previous update). Independent
original producers are the same list: no group is a curator of another. Shared curators: Loghub (one group),
4TU.ResearchData (hosting only; each log has its own producer), Zenodo (hosting only). New anomaly mechanisms
supported by protocols: P-SEQ on real process cases, P-TAB on supercomputer job records (SURF, Fugaku,
CC-IN2P3: three producers), P-TS on a metro compressor and a vehicle signal set. Application domains added:
HPC operations, public health surveillance, industrial maintenance, automotive, hospital pathways, public
administration processes, police fines, purchasing, travel expenses, recommender data, library catalogues.
The targets are unchanged and not met.

**Mutation status of Update 10 (focused, keyword-narrowed tests, development feedback).** `parquet_reader.py`: 152
killed, 2 survived (98.7 percent). Range, gzip, zip prefix and extraction code in `acquisition.py`: 319 killed of
384 generated for these functions (83.1 percent; 63 survived, 2 suspicious), below the L3 threshold of 95
percent, so that code is not mutation-certified; closing the survivors is open work. The new views and builders in
`experimental_views.py` have exact tests but no isolated mutation figure yet. No certification is claimed.

## Update 11: streaming logs, relational feeds, new domains and the target audit (2026-11-21)

**Safety work in `acquisition.py`.** Redirects are now guarded: a listed host may send the client only to https and
to a listed host, a subdomain of one, or a host named in the source's `redirect_hosts` (used once, for the object
storage behind the property register). The zip extractor no longer carries a size check that the archive reader
already enforces (dead code removed); decompression is bounded to the output limit plus one byte and returns at
most the limit. Tests pin the opener construction, the range request, the exact error messages, and the bounds.

**Streaming XES (`research/xes_stream.py`).** Sequential gzip or plain input, incremental XML parsing, complete
traces only, finished traces detached from the tree, limits on input, decompressed output and traces, refusal of
DOCTYPE and ENTITY declarations (also when split across chunks), and a status that says how reading ended
(`log_closed` or the limit or the source cut). A prefix is labelled as a prefix; a case-hash selection is
deterministic and is not a random sample. BPI Challenge 2018 (CC0, 158 MB gzip) was read as an 80 MiB prefix: 22835
complete cases decoded, the first 8000 kept. A CSV adapter with an explicit schema mapping (one row is one event)
was added for BPI Challenge 2014 (Rabobank ICT, 466737 events, 46616 incidents). BPI Challenge 2016 is not an event log
(one row per complaint) and was rejected; BPIC 2017 is the same producer as 2012.

**New groups.** C4: Rabobank ICT, German paying agency (BPIC 2018, also C2b through payment amounts). C5: twelve
French GTFS feeds from the national access point (one per network, licences lov2 or odbl declared by the publisher;
0 orphans on the three key relations; shared schema family, shared curator) and MovieLens is unchanged. C6: The Met
catalogue (CC0, 1000 objects by an even stride, depth 4; the host answered 403 at five requests per second and
the retry was paced at one per second). C3: Environment Agency daily river flow (OGL v3, 12 stations as one network
group). C2b: French property transactions (DGFiP register, Licence Ouverte 2.0, department 69 for 2024, addresses,
parcels and coordinates dropped). Not processed: GHCN-Daily (no licence statement located at the publisher),
CTU and RelBench (upstream terms unresolved), BPIC 2011 and Hospital Billing (identifiers not located).

**Coverage (machine-derived, readiness contract).**

| Category | Initial ready (start of this phase) | Newly ready | Final ready | Target | Gap |
|---|---:|---:|---:|---:|---:|
| C2b | 8 | 2 | 10 | 30 | 20 |
| C3 | 10 | 1 | 11 | 40 | 29 |
| C4 | 11 | 2 | 13 | 28 | 15 |
| C5 | 6 | 12 | 18 | 36 | 18 |
| C6 | 8 | 1 | 9 | 30 | 21 |

52 distinct provenance groups (49 at the previous report), 61 category participations, 34 domains, 19 curators and 25
schema families (`target_framework.json`). The C5 gain is twelve feeds of one schema family: without them C5 would be
6 groups, and the effective number of groups under an assumed intra-family correlation of 0.5 is 7.2. C1 and C2a were not
recomputed under provenance grouping.

**Target audit.** `verification/dataset_target_methodology.md` documents where the targets come from (planning
figures of the recommended tier in `13-pipeline-level-study.md`, no per-stratum calculation), separates sample size from
diversity, gives design-only sample-size tables with hypothetical parameters, and lists decisions for the owner. The
approved targets are unchanged.

**Mutation status of Update 11 (focused measurements, development feedback; not release certification).** Threshold L3 95 percent.

| Module | Generated | Killed | Survived | Suspicious | Timeout | No tests | Raw score |
|---|---:|---:|---:|---:|---:|---:|---:|
| `acquisition.py` (whole module) | 862 | 836 | 22 | 3 | 1 | 0 | 97.0 percent |
| `xes_stream.py` | 281 | 267 | 12 | 1 | 1 | 0 | 95.0 percent |
| `target_framework.py` | 513 | 488 | 19 | 2 | 4 | 0 | 95.1 percent |
| `parquet_reader.py` (earlier run) | 154 | 152 | 2 | 0 | 0 | 0 | 98.7 percent |
| `experimental_views.py`, 33 functions added in this and the previous update | 2663 | 2132 | 525 | 5 | 1 | 0 | 80.1 percent (below 95) |

Suspicious and timed-out mutants are counted as not killed. The remaining `acquisition.py` survivors are header-name
case changes (`USER-AGENT`, `range`), which urllib normalises, the unused `fp`, `msg` and `headers` arguments passed
to the standard redirect handler, the read-chunk size of one MiB and the case of the `utf-8` codec name: all inert on
this platform and library version, listed here as candidates only; no equivalence is approved. In
`experimental_views.py` the pure view functions score between 88 and 100 percent while the builders that write
files and manifests score lower, because their tests assert the data and the checksums but not every manifest text;
`_gtfs_spec` had no direct test when measured (104 survivors) and has one now, not remeasured. The module is below the
threshold and is not certified. The full-module measurement (56922 mutants) was started and stopped as impractical in
this session; the figures above come from a function-restricted run. No full `make verify-deep` was run.


## Update 12: approved target framework, provenance audit of C1 and C2a, clinical relational sources (2026-11-21)

**Decisions implemented** (owner decisions A to E, details in `dataset_target_methodology.md` section 10): three-tier targets;
provisional quotas C1 36, C2a 30, C2b 30, C3 40, C4 28, C5 36, C6 30 (sum 230 category participations); Holm at familywise
alpha 0.05 for prespecified families; provisional smallest effects (0.05, 0.05, 0.02, and 20 percent relative on the log
ratio); diversity guardrails of 3 domains and 2 families (exploratory) and 5 domains and 3 or 4 families (generalisation planning). The
variance pilot is designed in `variance_pilot_design.md` and not executed; the experimental freeze is unchanged.

**C1 and C2a re-audit** (`research/provenance_audit.py`, evidence `provenance_audit_c1_c2a.json`): historical tables are grouped by
shared creators (transitive closure; twins share a source). C1: 115 tables, 94 sources, 80 provenance groups, 8 domains,
4 mechanism families. C2a: 40 tables, 40 sources, 40 groups, 7 domains, 4 families. These are candidate groups, not ready groups:
they have not been run through the v2 readiness contract and many C2a tables are small or toy tables (T437), so they do not
count as experiment-ready.

**New acquisitions.** MIMIC-IV Clinical Database Demo and eICU Collaborative Research Database Demo (PhysioNet, ODbL v1.0 stated
on the project pages; open access): two hospital systems as separate C5 groups (6 and 5 key relations with 0 natural orphans, subject
ids re-salted, free text dropped). The table builder gained gzip tables by extension and per-column pseudonymisation recorded in the manifest.
Not acquired: the USGS earthquake catalogue (its copyright page refused automated access; the records are shallow).

**Coverage now** (readiness contract; groups per category, distinct domains and structural families of the approved criteria):

| Category | Ready groups | Quota | Gap | Domains | Families | Largest family (share) |
|---|---|---|---|---|---|---|
| C2b | 10 | 30 | 20 | 7 | 7 | contract award (0.3) |
| C3 | 11 | 40 | 29 | 11 | 10 | urban mobility counts (0.1818) |
| C4 | 13 | 28 | 15 | 10 | 4 | business process execution (0.5385) |
| C5 | 20 | 36 | 16 | 7 | 7 | timetable network (0.6) |
| C6 | 9 | 30 | 21 | 7 | 6 | procurement release (0.3333) |

54 distinct provenance groups, 35 domains, 20 curators and 26 schema families. All five audited categories pass the exploratory
tier and the domain and family minima of the generalisation tier; none meets its quota. Concentration is reported, not hidden: 12 of 20 C5 groups
are timetable feeds and 7 of 13 C4 groups are business-process logs.

**Mutation status (focused measurements; threshold 95 percent; not release certification).**

| Module | Killed / total | Raw score | Met |
|---|---:|---:|---|
| `acquisition.py` (whole module) | 836 / 862 | 97.0 percent | yes |
| `xes_stream.py` | 267 / 281 | 95.0 percent | yes |
| `parquet_reader.py` | 152 / 154 | 98.7 percent | yes |
| `target_framework.py` | 739 / 789 | 93.7 percent (43 survived, 7 timeouts) | no |
| `provenance_audit.py` | 390 / 420 | 92.9 percent (29 survived, 1 timeout) | no |
| `experimental_views.py`, 33 new functions | 2431 / 2697 | 90.1 percent (257 survived, 9 suspicious) | no |

The `experimental_views.py` survivors: about 20 percent are string literals of file paths whose upper-case variants are not detected
because the development file system is case-insensitive, about 10 percent are `sys.path` manipulations that the tests make irrelevant,
the rest are manifest texts and numeric limits; none is approved as equivalent. `target_framework.py` timeouts are infinite loops in
mutated search loops. Thresholds, classifications and exclusions are unchanged; the three modules below 95 percent are open work.
The `experimental_views.py` figure was measured before the clinical table additions; a first `target_framework.py` rerun crashed in the harness
(child exit -10) and was repeated.


## Update 13: C1 and C2a in the readiness contract, revised pilot design, Price Paid, mutation (2026-11-21)

**C1 and C2a.** The repository tables audited in Update 12 were assessed with `research/flat_readiness.py` and entered the common
seven-stage readiness contract (details and thresholds in `dataset_target_methodology.md` section 11). Initial candidates: C1 80 and
C2a 40 provenance groups; 71 and 38 had a local checksum-matched table (11 sources have no file). Experiment-ready: C1 52 (quota 36, met) and
C2a 12 (quota 30, gap 18). Rejected: privacy review pending for 37 tables that list personal attributes, small or duplicated tables, and tables
with too few categorical columns. The C1 quota is met by groups of one curator and one schema family and is not evidence of domain
generalisation.

**C2b.** HM Land Registry Price Paid Data (OGL stated by the publisher; first 30 MiB of the 2024 file, 180229 sales, addresses dropped,
postcode reduced to its district): a second property-sale system beside the French register. The City of Chicago taxi data were read
literally (no licence grant, a user indemnification clause) and are recorded as unclear, not acquired.

**Pilot design** (`variance_pilot_design.md` section 10): recall at a matched alert budget is the primary outcome with protocol-specific
detection units; AUPRC at a standardised prevalence, AUROC, alert burden and cost are secondary; pairing at the provenance group;
five Holm families with 16 planned primary comparisons derived from the research questions; pilot and confirmatory groups disjoint with
linked sets kept apart; 24 pilot slots allocated by a seeded draw over ready groups (22 distinct groups in a dry run), which leaves
confirmatory holdouts of 6 to 16 groups in the scarce categories, so category-level confirmatory claims are not supported by the current
inventory. The 1.40 bound holds only for independent normal differences; clustering widens it (1.50 to 2.04 at design effects of 1.3 to 3.0).
The pilot was not run.

**Coverage** (readiness contract; unclassified areas are not counted):

| Category | Ready groups | Quota | Gap | Domains | Families | Largest family (share) |
|---|---|---|---|---|---|---|
| C1 | 52 | 36 | 0 | 7 | 4 | computational or derived features (0.2885) |
| C2a | 12 | 30 | 18 | 6 | 4 | administrative or survey records (0.25) |
| C2b | 11 | 30 | 19 | 7 | 7 | contract award (0.2727) |
| C3 | 11 | 40 | 29 | 11 | 10 | urban mobility counts (0.1818) |
| C4 | 13 | 28 | 15 | 10 | 4 | business process execution (0.5385) |
| C5 | 20 | 36 | 16 | 7 | 7 | timetable network (0.6) |
| C6 | 9 | 30 | 21 | 7 | 6 | procurement release (0.3333) |

119 provenance groups, 45 domains, 21 curators, 27 schema families.

**Mutation status** (focused measurements, development feedback, threshold 95 percent, not release certification):

| Module | Killed / total | Raw score | Survived | Suspicious or timeout | Met |
|---|---:|---:|---:|---:|---|
| `acquisition.py` | 836 / 862 | 97.0 | 22 | 4 | yes |
| `xes_stream.py` | 267 / 281 | 95.0 | 12 | 2 | yes |
| `parquet_reader.py` | 152 / 154 | 98.7 | 2 | 0 | yes |
| `provenance_audit.py` | 387 / 402 | 96.3 | 14 | 1 | yes |
| `flat_readiness.py` | 679 / 708 | 95.9 | 21 | 8 | yes |
| `target_framework.py` | 853 / 890 | 95.8 | 26 | 11 | yes |
| `experimental_views.py`, 37 new or changed functions | 2636 / 2892 | 91.2 | 246 | 10 | no |

For `experimental_views.py` the deficit at this denominator is 112 kills. About 45 survivors are upper-case path literals that a
case-insensitive file system cannot distinguish, about 19 are numeric size limits of the extraction helpers, about 20 are
text of error or note strings, and the rest are keyword arguments of file writes and pandas calls; none is approved as equivalent.
`acquisition.py` and `xes_stream.py` figures predate this update's work and the modules were not changed. The first `provenance_audit.py`
runs in this session were below the threshold and were fixed by tests and by removing dead branches and per-function path edits.


## Update 14: final pilot design, view-builder mutation and portability (2026-11-21)

**Pilot design** (`variance_pilot_design.md` section 11, design only, no detector run): primary alert budget 1 percent of the eligible test
units of a source and problem (sensitivity 0.5, 2 and 5 percent), integer allowance floor(B x N) shared by paired detectors, no
minimum-one-alert exception, deterministic tie-break, handling of detectors without scores, the budget-prevalence ceiling on recall;
AUPRC reported as average precision with an operating-characteristics standardisation at the reference prevalence of 1 percent
(sensitivity 0.5 and 5 percent) only where its assumptions hold; an audit of F1 to F5 that finds F4 redundant at a matched budget (false
positives are the budget minus true positives), F3 outside the matched-budget estimand, and F2 dependent on a best-learner choice that
may not use confirmatory data (two prespecified options, a fixed representative per family or a validation-only rule); corrected proposal
of at most 11 confirmatory comparisons (F1 3, F2 5, F5 3) instead of 16. Pilot of 16 distinct provenance groups by a seeded,
domain-aware allocation (`plan_pilot`, seed 20261121, evidence `pilot_plan_dry_run.json`): pilot / holdout per category C1 7/45, C2a 2/10, C2b 2/9,
C3 2/9, C4 2/11, C5 3/17, C6 2/7, 103 holdout groups in total; the 24-group alternative takes its 8 extra groups from C1. Category-level
confirmatory claims are not supported by holdouts of 7 to 17 groups (one comparison at sigma 0.10 and a difference of 0.05 needs 34); a pooled claim
over the holdout (about 30 to 38 effective groups under hypothetical schema-family correlations of 0.5 and 0.2) is conditional on the pilot SD, the design effect, the number
of Holm comparisons and a heterogeneity check.

**Mutation of the view builders.** The 37 new or changed functions of `experimental_views.py` were measured at 2636 of 2892 (91.2 percent) on the
development file system, which is case-insensitive. Tests were then added for the helpers and builders (types, limits, decoy archive
members, unreadable-file counts, XES trace limits and modulo, quoting and pseudonymisation of blank values, header lines of every written file, resolution
of sibling imports at import time instead of per builder) and the measurement was repeated with the tests running on a case-sensitive APFS
volume: 2767 of 2892 killed (95.7 percent), 112 survived, 13 suspicious; the threshold of 95 percent is met in this focused measurement. The
same tests pass on both file systems, so the code is portable to case-sensitive systems; the earlier upper-case path survivors were an artefact of the
case-insensitive volume, not of missing tests. The remaining survivors are keyword arguments with no effect in pandas for multi-key sorts
(`kind`), `index=None` writes, `low_memory`, and a few message strings; none is approved as equivalent. This is development evidence, not release certification.

**Coverage** (readiness contract; unclassified areas not counted):

| Category | Ready groups | Quota | Gap | Domains | Families | Largest family (share) |
|---|---|---|---|---|---|---|
| C1 | 52 | 36 | 0 | 7 | 4 | computational or derived features (0.2885) |
| C2a | 12 | 30 | 18 | 6 | 4 | administrative or survey records (0.25) |
| C2b | 11 | 30 | 19 | 7 | 7 | contract award (0.2727) |
| C3 | 11 | 40 | 29 | 11 | 10 | urban mobility counts (0.1818) |
| C4 | 13 | 28 | 15 | 10 | 4 | business process execution (0.5385) |
| C5 | 20 | 36 | 16 | 7 | 7 | timetable network (0.6) |
| C6 | 9 | 30 | 21 | 7 | 6 | procurement release (0.3333) |

119 provenance groups, 45 domains, 21 curators, 27 schema families. No new group was added in this update.

## Update 15: online retail added to the transactional category (2026-11-21)

Online Retail (UCI 352, creator Daqing Chen, CC BY 4.0 stated on the repository page) was already downloaded and checksum-pinned in the second UCI
wave but never entered the readiness contract: the transactional audit found it as the only table with an invoice key, a time column and event
columns. A view builder (`retail_view`) now keeps 541,909 invoice lines with a salted invoice and customer, the item code, quantity, unit price,
line value, country and a cancellation flag (invoice numbers starting with C, negative quantities kept as published); the free-text product
description is dropped. It is registered as C2b under the provenance group `uci:352` (a retail e-commerce system, distinct from procurement and land
registers). C2b rises from 11 to 12 ready groups (gap 18); global distinct provenance groups rise from 119 to 120. The other categories are unchanged. Source
concentration: C2b is now 5 of 12 groups from public procurement and expenditure ledgers, 2 land registers, 1 bike-share, 1 road-fines log, 1 coatings
process log and 1 retail system. Anomaly mechanisms available on the retail lines: price and quantity faults, duplicate invoices, timestamp
faults; natural irregularities (cancellations, missing customer ids, negative quantities) stay baseline properties, not labels.

## Update 16: four new original generating systems (2026-11-22)

Four sources that were not in the corpus were acquired from their original publishers' statements and promoted to experiment-ready; the retail table of
Update 15 was a catalogued source and is counted separately. Global distinct provenance groups: 119 before this work, 120 after the retail promotion, 124 now.

| Group | Category | Original publisher and rights | Structure and size | New contribution |
|---|---|---|---|---|
| `paleobiology_database` | C2a | PBDB data service states CC0 (read at the service); Zenodo archive 24274793 cc-by-4.0, md5 verified | 201,107 occurrences (one in ten, file order), 31 columns, 22 categorical with up to 13,479 levels | palaeontology, high-cardinality taxonomy and geology with 3 to 96 percent structural missingness |
| `cubico_kelmarsh` | C3 | Cubico Sustainable Investments released the data under CC BY 4.0 (record text) | 314,496 ten-minute rows, six turbines, 2016, 16 signals | wind-energy generation; constant spacing; natural gaps |
| `wikimedia_wikidata` | C6 | Wikidata:Licensing states CC0 for structured data | 1,611 items (people excluded), depth up to 11, claims with qualifiers and references | community knowledge base, a third of the items scholarly articles |
| `pnnl_epri_bess` | C3 | PNNL and EPRI data collectors, CC BY 4.0 | 1,452,814 meter readings of two utility battery systems in elapsed hours | grid-scale energy storage; publisher quality flag on 6 percent of rows |

Counts after this update (machine-derived, `readiness.json`): C1 52, C2a 13, C2b 12, C3 13, C4 13, C5 20, C6 10; 124 distinct provenance groups. Gaps to the provisional
quotas: C2a 17, C2b 18, C3 27, C4 15, C5 16, C6 20. Concentration is unchanged for C1 (one repository), C4 (7 of 13 process-mining logs) and C5 (12 of 20 timetable feeds).

Limits recorded with the sources. The PBDB occurrences are every tenth row in entry order, not a random sample; the taxon table of the same archive was downloaded but
not turned into a C5 view, which would be a second participation of the same group and not a new group. The Kelmarsh view covers one year of a ten-year release and the six turbines are
one generating system. The Wikidata items follow an even identifier stride (about 11 percent of the requested identifiers do not exist). The battery files use elapsed time, so
calendar effects cannot be studied, and two of twelve systems of the release were taken. No natural anomaly labels are used for any of them; the publisher's quality flags are baseline properties.

Candidates examined and not acquired: NVD CVE records (the API returns deeply nested records, but the NVD terms pages are rendered client side and could not be read literally; recorded as
permission pending); NBG deposit transactions (real bank transactions; the record's depositor is a project member and the bank's own release statement was not found); the anonymised phone-call
records of INESC TEC (83 million rows with a natural blacklist label; the supplying operator is not named); the GTMD 2.0 mobility table (modelled estimates, not observations); the multi-source distributed-system
data of Nedelkoski et al. (an instrumented test bed, not an operational system); OpenSky 2020 (non-commercial licence).

**Focused mutation of the new view code (development feedback, case-sensitive volume, each group run separately because a combined run gave inconsistent survivor lists).**
Retail functions (`retail_view`, `_build_retail`): 194 of 202 = 96.0 percent. New functions of this update (`pbdb_occurrence_view`, `_build_pbdb`, `kelmarsh_view`, `_kelmarsh_header`,
`_build_kelmarsh`, `wikidata_view`, `_is_human`, `_build_wikidata`, `bess_view`, `_build_bess`): 644 of 686 = 93.9 percent, 8 kills below the 95 percent threshold (652). The L3 threshold is therefore
not met for this block. The 42 non-killed mutants are keyword arguments without effect on the output (`kind` of single-key or tie-free sorts, `index`, `ignore_index`, `low_memory`-like
settings, `encoding` on a UTF-8 system, `skiprows` and `na_values` whose effect is absorbed by the later dropping of unreadable timestamps and the NaN default) and one string replacement; none is approved
as equivalent. Closing the gap needs either owner-reviewed equivalence decisions or restructuring these arguments away, and was not done in this round.

## Update 17: mutation refactoring, CARE to Compare and the status of four requested candidates (2026-11-22)

**Mutation.** The eight-kill deficit of the ten view functions was closed by behaviour-preserving refactoring and tests, with no change to policy or scope. Arguments without effect were removed:
`na_values=["NaN"]` (a pandas default), `ignore_index` on concatenations whose index is never written, the `kind` argument of the multi-key sort in `bess_view` (pandas ignores it), the redundant `index` of a
constructor, and a `replace("", NA)` that became a `mask`. The Kelmarsh header is now read as bytes and decoded as UTF-8, so it no longer depends on the locale. Tests were added for the header
and the data rows passed to the view (skip rows, wanted columns), tie order of single-key sorts above the small-input threshold, the extraction limits, unreadable numbers, blank codes, human detection and read limits.
Result on the case-sensitive volume, each function group run separately: 654 killed of 667 (98.1 percent) for the ten functions (the earlier denominator was 686 because removed arguments removed mutants);
13 not killed: 10 survived, 2 suspicious, 1 timeout. The survivors are `index=None` of `to_csv` (equal to False), `kind="STABLE"` (pandas accepts any case), `rstrip(None)` and the 30 versus 31 header lines of the header scan, a string case of a
folder name and a glob. None was approved as equivalent. Retail functions: 194 of 202 (96.0 percent). New CARE functions (`zip_local_member`, `care_series_view`, `_build_care`): 263 of 273 (96.3 percent). This is development evidence, not certification.

**CARE to Compare (record 15846963, Fraunhofer IEE, CC BY-SA 4.0).** The record named in the request (14004425) is an enzyme-classification benchmark with protein and reaction tables and was rejected as irrelevant. The wind-turbine benchmark is 15846963: 95 datasets of ten-minute SCADA
from 36 turbines of three farms; farm A is EDP open data (terms unreadable, not used); farms B and C are anonymised German offshore farms released by the authors. Five of the 15 datasets of farm B were fetched by HTTP range requests of their zip members (the server answers 206):
279,733 rows, 63 average sensors, turbine status and the publisher's training and prediction phases; three of the five datasets lead to a labelled equipment fault (transformer cell temperature or bearing damage) and two are normal. The publisher's event file is kept as `events.csv`, apart from
the series. These are real equipment-fault annotations from the operator's records; they are not ETL or source-data faults and are not used as injection labels. Group `fraunhofer_iee_care_wind_b` (C3). Provenance groups are now 125.

**Candidate status.** NVD: the API works and returns deeply nested records, but the terms pages could not be read, so no rights were verified and nothing was acquired. OpenSky: the licence is a binding agreement (Swiss law, indemnity, publication copy to OpenSky, anonymisation of aircraft identifiers, deletion on completion);
accepting it is an owner decision; the data are flight records and support C2a, not C2b or C4. St. Gallen smart factory: three records, one physical testbed and one provenance group, accessible and eligible as an instrumented testbed (not acquired in this round). DataCenter-Traces: aggregated views of the Alibaba, Google and Azure traces, not a new
generating system, no event continuity. PBDB taxa: a second participation of the PBDB group (C5), not built.

## Update 18: NVD, EDP wind farm A, St. Gallen smart factory and the PBDB relational participation (2026-11-22)

Terms were read in a headless browser where the pages render client side. **OpenSky** stays blocked: the owner declined the agreement (ledger status `permission_pending`, class `research_only`, owner-contractual-acceptance blocker); nothing was acquired.

| Item | Rights evidence | Result | Counts as |
|---|---|---|---|
| NVD CVE records (C6) | NVD Terms of Use (use permitted, attribution notice, public rate limits), NVD FAQ (NIST publications are public domain), CVE Terms of Use (MITRE royalty-free licence, copyright notice and licence must accompany copies) | 4,194 records of four fifteen-day windows (2018, 2020, 2022, 2024), all pages complete; depth 9; optional weaknesses, configurations and CISA fields; five scoring generations; statuses Modified, Analyzed, Deferred, Rejected | new group `nist_nvd` |
| CARE wind farm A (C3) | EDP's own dataset page states CC BY-SA 4.0 (read 2026-11-22); the CARE record is cc-by-sa-4.0 and names the EDP platform; EDP asks for a registration on its own site, the CARE record is the open redistribution | 8 of 22 datasets, 437,750 ten-minute rows, 45 average sensors; four datasets lead to a logbook fault (transformer, hydraulic group, gearbox, generator bearing), four are normal; real equipment faults, kept in `events.csv`, not ETL faults | new group `edp_wind_farm_portugal`; independent of Kelmarsh (Cubico, UK) and of wind farm B (anonymised German offshore farms) |
| St. Gallen smart factory (C3 and C4) | cc-by-4.0 on record 14441997, the data release of the testbed's operators; 7440490 and 14998532 are the same installation | C3: 139,901 ten-hertz station messages of seven stations (36 minutes); C4: 1,727 Camunda activity instances of 176 process instances, 13 definitions, 2022-09 to 2023-04 (1,615 completed, 112 active) | one new group `unisg_smart_factory`, two category participations; evidence class: instrumented research testbed, not production; no faults documented |
| PBDB relational (C5) | as for the C2a view (CC0 at the PBDB data service) | 201,107 sampled occurrences referencing 95,846 taxa that include every ancestor; 0 unknown taxa, 5,241 occurrences without an accepted taxon and one ancestor identifier absent from the source (natural, not sampling) | new category participation only, group `paleobiology_database` unchanged |

Machine-derived counts after this update: C1 52, C2a 13, C2b 12, C3 16, C4 14, C5 21, C6 11; 128 distinct provenance groups. Gaps to the provisional quotas: C2a 17, C2b 18, C3 24, C4 14, C5 15, C6 19. Since the 119-group report: Paleobiology Database, Kelmarsh, Wikidata,
PNNL/EPRI battery storage, CARE wind farm B, NVD, EDP wind farm A and the St. Gallen testbed are new groups; the retail table and the PBDB relational view are promotions or participations, not new systems.

Focused mutation (development evidence, case-sensitive volume, each group run separately): NVD functions 118 of 119; St. Gallen functions 267 of 278 (96.0 percent); CARE farm functions 143 of 147; PBDB relational functions 252 of 255 (98.8 percent); earlier scopes as in Update 17. No equivalence was approved.

## Update 19: C4 and C3 corrections, the Formula One database, Backblaze drive telemetry and candidate decisions (2026-11-22)

**Corrections.** The St. Gallen workflow log is Camunda process execution: it is counted in the business-process family (C4 largest family now 8 of 14 = 57 percent) and adds a new generating system, domain and evidence class (instrumented
testbed), not a new event-generation mechanism. The 36-minute ten-hertz sensor log keeps its C3 readiness with recorded restrictions (`temporal_span`, `supported_fault_mechanisms`, `unsupported_fault_mechanisms`): window-local mechanisms only,
no seasonal, slow-shift or long-history mechanisms (`anomaly_protocols.md`). The same fields were added for the new Backblaze source. Readiness rules were not changed.

**New original generating systems.** (1) *Jolpica Formula One database* (C5): CC BY-NC-SA 4.0 in the project's terms (non-commercial academic use), the free delayed dump of 2026-11-07 verified against its published SHA-256; 11 tables, 13 foreign-key relations with no orphan, 745,127 laps;
driver names, birth dates and nationalities dropped. A season-round-session-entry-lap topology unlike timetable feeds. (2) *Backblaze Drive Stats 2014* (C3): free with citation (publisher's page read in a browser); 60 daily files, one drive in eight by salted hash with whole series, 3,749 drives, 206,941 drive-days, 31
real drive failures kept as a column (equipment failures, not ETL faults); the server ignores range requests so the 588 MB archive is stored locally.

**Candidate decisions.** NYC TLC: the TLC terms page denies automated access (not bypassed) and the NYC Open Data mirror carries no licence field; blocked until the owner reads the terms or the TLC confirms. OpenAlex: already ready as C5 and C6 under one group, no new group. RelBench: rel-f1 is the Ergast lineage of the Jolpica group, rel-stack and rel-trial derive from groups already present,
rel-salt (SAP SALT, CC BY-NC-SA 4.0 on a gated Hugging Face dataset) needs an account and acceptance (blocked, not bypassed through the mirror), rel-avito, rel-event and rel-hm are Kaggle competition data (account and acceptance), rel-amazon and rel-ratebeer unverified. CTU: unchanged, each database needs its own origin check.
Loghub: the existing group already holds the 16 systems and Loghub-2.0 re-annotates the same logs. The INESC TEC and NBG sources remain permission pending.

**Counts (machine-derived).** C1 52, C2a 13, C2b 12, C3 17, C4 14, C5 22, C6 11 (gaps 0, 17, 18, 23, 14, 14, 19); 130 distinct provenance groups, 129 generating systems, 130 producers, 25 curators, 54 domains, 37 schema families, 141 category participations; the largest schema family holds 49 percent of the groups.

**Focused mutation.** Backblaze functions 190 of 196 (96.9 percent); `_build_tables` after the per-source snapshot change 218 of 227 (96.0 percent); earlier scopes unchanged. No equivalence was approved.

## Update 20: NYC taxi fares, openFDA device reports, USDA food composition and the LANL access blocker (2026-11-22)

**Rights decisions.** NYC TLC was reassessed with the sources supplied by the owner and read in a browser: the NYC Open Data Technical Standards Manual quotes Local Law 11 of 2012 (data available without registration, licence requirement or usage restrictions) and the portal Terms of Use bind the user to the nyc.gov terms, give no warranty and ask republishers to identify source, version and modifications; the dataset's metadata declares no extra TLC terms. The TLC page itself still denies automated access and was not read, so a TLC-only condition cannot be excluded; this is recorded. The
download used the NYC Open Data API with TLS verification against the macOS system root store (the Python bundle lacks the GlobalSign R46 root); verification was never disabled. openFDA: the Terms of Service read in a browser state CC0 1.0 unless marked, with no signature, indemnity or account; large pages need an API key, which was not requested. USDA FoodData Central: CC0 1.0 stated by USDA.
LANL: both datasets carry a statement that LANL waived all copyright and related rights and an approval for public release, but the official download interface requires an email address and an intended-use statement; I did not submit personal details, so nothing was acquired (owner action).

| Group | Category | Structure | Counts as |
|---|---|---|---|
| `nyc_tlc` | C2b | three complete pickup days of March 2023, 320,320 yellow taxi trips with fare, extras, tax, tip, tolls, surcharges, total and payment type; 2,917 trips with zero or negative totals kept as published; no trip identifier, taxi-zone ids only | new group; transport-fare mechanism |
| `fda_maude` | C6 | every device adverse event report received on 2023-03-01 (7,355), depth 5, 71 keys with 8 optional, arrays of devices and patients; manufacturer contact persons and narratives dropped | new group, shares only the publisher and platform with the FAERS group (recorded as a dependence) |
| `usda_fdc` | C5 | SR Legacy April 2018: 7 tables, 6 relations with no orphan, 7,793 foods, 644,125 laboratory nutrient measurements, 14,449 portions | new group; measurement-fact topology |

Open Food Facts and OpenAlex were already represented (C6 and C5/C6) and were not re-acquired. LANL's host-event JSON lines are flat, so no C6 claim would be made for them; both LANL datasets are one enterprise and one group. NHTSA FARS (a strong C2a candidate) and the rest of the C2a backlog remain without verified rights.

**Counts (machine-derived).** C1 52, C2a 13, C2b 13, C3 17, C4 14, C5 23, C6 12 (gaps 0, 17, 17, 23, 14, 13, 18); 133 distinct provenance groups, 132 generating systems, 133 producers, 27 curators, 57 domains, 40 schema families, 144 category participations; the largest schema family holds 48 percent of the groups; C4 remains 57 percent business-process execution.

**Focused mutation.** TLC functions 153 of 159 (96.2 percent); MAUDE functions 114 of 117 (97.4 percent); no equivalence approved.

## Update 21: STATS19, EPA AQS, USGS water data and Wikimedia revision history; sources blocked or left to the owner (2026-11-22)

Local work only: no detector run, no frozen result touched, nothing pushed. Raw files stay under the gitignored `data/acquired/`.

| Group | Category | Rights evidence | Structure | Counts as |
|---|---|---|---|---|
| `dft_stats19` | C2a | Open Government Licence v3.0 (GOV.UK footer of the Road Safety Open Data page); contributory factors are withheld by the publisher and were not requested | 2023 complete release: 104,258 collisions, 189,815 vehicles, 132,977 casualties; 69 of 95 kept columns have at most 100 coded levels, published `-1` codes cover 6.1, 8.7 and 7.4 percent of cells; 0 orphans on `collision_index`; vehicle and casualty counts equal the child rows for every collision; the publisher's data guide is kept as the codebook; police reference numbers and home-area codes dropped | new group (road safety); the three tables are one generating system |
| `epa_aqs` | C3 | EPA AirData FAQ: AQS ambient monitoring data are public domain | hourly ozone 2022 and 2023, 12 monitors in 12 states chosen by an even stride over the 1,245 monitors present in both years; 162,829 values, 10.4 percent with a qualifier, two instrument methods; six monitors run all year, six only seven to nine months | new group; two annual cycles only, so yearly seasonality can be checked for presence, not stability |
| `usgs_water` | C3 | USGS Copyrights and Credits: USGS-produced data are in the U.S. public domain; no API key requested | discharge at four fixed gauges (Potomac, Colorado at Lees Ferry, Mississippi at St. Louis, Sacramento at Freeport), 2022 to 2023, 243,474 values at 15 or 30 minutes, 428 qualified, 0.01 to 2.4 percent of steps absent | new group; same domain and schema family as the Environment Agency gauges (not counted as new diversity), different agency and instruments |
| `wikimedia_simplewiki` | C4 | Wikimedia dumps licence page (free reuse; CC BY-SA 4.0 and GFDL; Terms of Use control) | prefix of the 2026-11-01 stub history: 296,916 revisions of 1,416 complete pages, 2001 to 2026, parent links with 0 dangling, 27.5 percent anonymous editors (salted hashes), 1.1 percent of pages with an out-of-order timestamp (natural); a non-business-process event mechanism with a limited event vocabulary (creation, minor, ordinary edit) | new group; shares publisher and MediaWiki platform with the Wikidata group (recorded dependence); not a random sample of the wiki |

No natural anomaly labels exist in any of the four; every fault will be a controlled injection.

**Blocked or not acquired.**

| Source | Reason |
|---|---|
| NHTSA FARS (C2a) | rights not verified: www.nhtsa.gov answers 403 to automated clients (not bypassed) and the data.gov records disagree (public-domain mark, CC0, "other restrictions", "non-public"); the primary NHTSA statement was not read. Owner or browser check needed |
| NOAA GHCNh (C3) | the files are reachable but no licence was found (liability disclaimer only), and GHCNh integrates many national upstream sources, so independence and international terms need a per-source check |
| NASA KSC HTTP logs 1995 (C4) | redistribution is free but the page asks for no analysis beyond general traffic patterns and the logs preserve originating hosts; whether fault injection and detection fit that wording is an owner decision, so nothing was downloaded |
| LANL cybersecurity logs (C4) | unchanged: the download interface needs an email address and an intended-use statement, which were not submitted; the host-event JSON lines are flat and would not count for C6 |
| Wikimedia live recent-changes stream (C4) | not used: a short live capture would be an artificial history; the dated dump gives 25 years of real history |
| OpenAlex (C5, C6), ClinicalTrials.gov (C6) | already represented by the groups `openalex` and `clinicaltrials_gov`; not re-acquired |
| USDA branded foods (C2a) | same provenance family as `usda_fdc`; not acquired |

**Counts (machine-derived, `readiness.py` then `target_framework.py`).** C1 52, C2a 14, C2b 13, C3 19, C4 15, C5 23, C6 12 (gaps to the provisional quotas 0, 16, 17, 21, 13, 13, 18; 98 category participations, 102 before); 137 distinct provenance groups (133 before), 136 generating systems, 137 producers, 29 curators, 59 domains, 43 schema families, 148 category participations; the largest schema family holds 46.7 percent of the groups; C4 remains 53 percent business-process execution (8 of 15), C5 52 percent timetable feeds.

**Verification.** Tests: `research/tests/test_experimental_views.py` and `test_view_builders.py` (new builders with unit tests, a golden manifest each, and the full-build fixture), plus the registry, readiness, target-framework and acquisition test files, all passing; `ruff check .` and `ruff format --check .` clean. Mutation testing was not run for the new view functions (`aqs_pick`, `aqs_hourly_view`, `_build_aqs`, `usgs_continuous_view`, `_build_usgs`, `wiki_revision_view`, `_wiki_row`, `gzip_members_lines`, `_build_wiki`; the STATS19 view is configuration of the existing table builder); they enter the next mutation round and carry no certification claim.
The manuscript and slides quote no group counts of this wave, so they are unchanged.

## Update 22: Catalog C2a fix, Update 21 mutation checks, and 13 independent groups across C6, C3, C2a, C2b, C4 and C5 (2026-11-22)

Local work only: no detector experiment was run, no frozen result was modified, nothing was pushed, and raw downloads remain under the gitignored `data/acquired/`.

**Update 21 audit and focused mutation.** Re-verification confirmed all four Update 21 snapshots (`dft_stats19_2023`, `epa_aqs_ozone_hourly`, `usgs_continuous_discharge`, `wikimedia_simplewiki_edits`) have zero missing or mismatched files (`Snapshot.verify() == []`) and match the recorded CSV SHA-256 digests in `experimental_views.json`. Two minor metadata notes in `acquisition_sources.json` remain non-blocking: `wikimedia_simplewiki_edits` records `observed` as `2003-2026` whereas the earliest revision in the stub history prefix is `2001-09-19`, and `dft_stats19_2023`'s privacy note refers to age bands while retaining published integer `age_of_driver`/`age_of_casualty` alongside public collision coordinates/OSGR/LSOA (police collision reference numbers and driver/casualty home-area LSOA codes are dropped). After removing no-op pandas/decode arguments and tightening test assertions (`554b7fa`), focused mutation on the Update 21 view functions (case-sensitive volume, 95 percent raw killed threshold, zero equivalent mutants approved) scored: AQS (`_aqs_id`, `aqs_pick`, `aqs_hourly_view`, `_aqs_chunks`, `_build_aqs`) **336/342 (98.25%)**, USGS (`usgs_continuous_view`, `_build_usgs`) **211/212 (99.53%)**, and Wikimedia (`wiki_revision_view`, `_wiki_row`, `gzip_members_lines`, `_build_wiki`) **342/349 (97.99%)**; STATS19 reuses `tables_view`.

**Catalog gap repair (`research/dataset_catalog.py`, `d175390`).** Added `"C2a": "categorical and mixed tables"` to `STRATA` and `"C2a": (15, 30, 45)` to `TARGETS` without changing scientific definitions or frozen results. `.venv/bin/python research/dataset_catalog.py gap` now exits 0 (`Distinct source families: 255`; `Licence classes (sources): open 233, research_only 22`). Focused mutation on `research.dataset_catalog.*` scored **773/782 (98.85%)**.

**Promoted and acquired independent generating systems (+13 groups).** All 13 carry verified open rights and privacy controls; none carry fabricated natural anomaly labels.

| Group (`view_id`) | Cat. | Rights evidence | Structure & privacy | Mutation (killed/total) |
|---|---|---|---|---|
| `crossref` (`crossref_works`) | C6 | Crossref REST API docs (open metadata reuse; abstracts excluded via API `select` leaving `0` abstract keys; `author` dropped) | 2,000 Crossref works JSONL (promoted from existing `2026-11-21` snapshot) | — (existing JSONL view) |
| `uniprot_kb` (`uniprot_kb_reviewed`) | C6 | UniProt REST API / FTP `LICENSE`: CC BY 4.0 | 1,500 reviewed Swiss-Prot entries across 6 model organisms (depth 11, 408 paths; `references` & `sequence` dropped; `0` emails) | 98/101 (97.03%) |
| `osv_go` (`osv_go_advisories`) | C6 | OSV.dev Go Vulnerability DB: CC BY 4.0 (strict `GO-*` prefix filter) | 4,820 `GO-*` advisories from 9,989 records (depth 9, 37 paths; `credits` dropped, `redact_emails`, `0` emails) | 101/102 (99.02%) |
| `gfz_potsdam_kp` (`gfz_kp_index`) | C3 | GFZ file header: CC BY 4.0 (external CC BY-NC sunspot/F10.7 file excluded) | 277,272 3-hourly `Kp`/`ap` rows (`1932-01-01` to `2026-11-21`; 277,104 definitive, `0` missing `Kp`) | 192/198 (96.97%) |
| `dwd_germany` (`dwd_hourly_climate`) | C3 | DWD CDC `Terms_of_use.txt`: CC BY 4.0 | 838,605 hourly rows across 12 strided TU stations (`2018-01-01` to `2025-12-31`; `-999` masked to `NaN`, `0` dupes) | 198/200 (99.00%) |
| `rte_france_grid` (`rte_eco2mix_national`) | C3 | ODRE `eco2mix-national-cons-def`: Licence Ouverte v2.0 Etalab | 70,120 half-hourly definitive rows across 32 series (2020–2023; 70,128 forecast-only quarter-hour rows & 8 DST dupes dropped) | 154/158 (97.47%) |
| `ademe_dpe` (`ademe_dpe_existant`) | C2a | ADEME Data-Fair `dpe03existant`: Licence Ouverte v2.0 | 50,000 rows x 21 cols (5 numeric, 16 categorical >=3 levels; `flat_readiness.reasons=[]`; BAN/RNB/addresses omitted; `numero_dpe` pseudonymised) | 122/125 (97.60%) |
| `dgal_alimconfiance` (`dgal_alimconfiance`) | C2a | DGAL OpenDatasoft: Licence Ouverte (Etalab) | 71,228 rows x 16 coded cols (12 categorical >=3 levels; `flat_readiness.reasons=[]`; names/SIRET/agrement/addresses/geo dropped; `numero_inspection` pseudonymised) | 108/112 (96.43%) |
| `ntnu_ev_charging` (`zen_ev_charging`) | C2b | Zenodo `13896176`: CC BY 4.0 | 35,377 charging sessions across 267 users & 12 residential sites (`session_id`, `user_id` pseudonymised; comma decimals parsed) | 190/199 (95.48%) |
| `microsoft_azure_compute` (`azure_packing_2020`) | C4 | GitHub `AzurePublicDataset` LICENSE: CC BY 4.0 | 38,995 VM allocations across 6,086 multi-VM tenants (`tenantId % 100 == 0`; 12,926 single-VM rows dropped) | 170/175 (97.14%) |
| `aoe_gameplay` (`zen_aoe_interactions`) | C4 | Zenodo `11060884`: CC BY 4.0 | 2,881 game traces / 290,046 player actions (XES zip prefix via `xes_stream`; `case_id`, `player_id`, `match_id` pseudonymised) | 218/222 (98.20%) |
| `uk_charity_commission` (`uk_charity_register`) | C5 | GOV.UK / CCEW OGL v3.0 (data.gov.uk `uk-ogl`) | 5 non-trustee extracts (`1-in-20` slice): 19,952 charities + 214,580 child rows, `0` orphans across 4 FKs; trustee extract never fetched; names/contacts/activities dropped | 107/110 (97.27%) |
| `japan_reconstructed_buildings` (`zen_japan_buildings`) | C5 | Zenodo `23166842`: CC BY 4.0 | Complete 7-table relational schema (1,014 buildings, 346 sites, 397 evidence sites, 279 designers, 1,151 links, 814 site-sources, 708 sources); `0` orphans across all 6 FKs (`5,032` links); names/authors/addresses/notes dropped | 88/89 (98.88%) |

**Blocked or excluded during screening.** Existing blockers remain unchanged (LANL email form, NHTSA FARS 403 and conflicting rights metadata, NASA HTTP analysis restriction and host identifiers, NOAA GHCNh missing licence and upstream mix, OpenSky agreement declined, SAP SALT gated account). Screening additionally excluded U.S. SEC/FAA/CFPB/FSA APIs (HTTP 403), FHWA NBI (TLS failure), GFZ sunspot/F10.7 file (CC BY-NC), and CCEW `publicextract.charity_trustee` (personal trustee extract).

**Counts and diversity (machine-derived, `readiness.py` then `target_framework.py`).** C1 52, C2a 16, C2b 14, C3 22, C4 17, C5 25, C6 15 (gaps to the provisional quotas 0, 14, 16, 18, 11, 11, 15; **85** remaining category participations vs 98 before; **161** total participations vs 148 before); **150 distinct provenance groups** (137 before), **149 distinct generating systems** (136 before), **150 producers** (137 before), **39 curators** (29 before), **69 domains** (59 before), **56 schema families** (43 before); effective independent groups at `design_effect=0.2` reach **71.9321** (**61.8074** at `0.5`). Overall largest-schema-family share fell from `46.7%` to `42.7%` (`0.4267`), C4 `business process execution` share fell from `53.3%` (8 of 15) to `47.1%` (8 of 17, `0.4706`), and C5 `timetable network` share fell from `52.2%` (12 of 23) to `48.0%` (12 of 25, `0.48`).

**Verification and publication status.** All 17 reviewed/acquired snapshots verified (`Snapshot.verify() == []`), all 30 files across those 17 experimental views matched `experimental_views.json` SHA-256 digests 100%, all 438 tests across the 10 regression test files passed, and `ruff check .` and `ruff format --check .` passed across 446 files. The manuscript (`paper/`) and slides (`slides/`) quote no Update 20–22 counts and remain unchanged under the active experiment freeze.

## Update 23 — Metadata integrity fixes, L3 mutation audit, and Wave 23 acquisitions (+16 groups)

This update resolves the three documented metadata discrepancies, audits all changed modules against `verification/mutation_risk_policy.json`, and integrates **16 new independent provenance groups** across all six non-C1 targets (`C3`, `C2b`, `C6`, `C2a`, `C4` non-BP, `C5` non-GTFS) while keeping the experiment freeze intact (`0` detector runs, `paper/` and `slides/` unchanged).

**Metadata integrity fixes (`4da1f8c`).** (1) Corrected `wikimedia_simplewiki_edits` `observed` span from `2003-2026` to `2001-2026` (earliest revision `2001-09-19`) in `acquisition_sources.json` and the snapshot `manifest.json` while preserving the non-random page-ID gzip-prefix description. (2) Replaced `dft_stats19_2023`'s age-band wording with an accurate five-part declaration (retained published integer `age_of_driver`/`age_of_casualty`, collision coordinates/OSGR and `lsoa_of_accident_highway`; dropped `collision_ref_no`, `lsoa_of_driver`, `lsoa_of_casualty`; none pseudonymised or generalised). (3) Disambiguated `rabobank_ict` (`Rabobank Group ICT incident management system`) and `volvo_it` (`Volvo IT Belgium incident management system`) in `source_attributes.json` so distinct concrete generating systems match independent groups cleanly while preserving `structure.C4 = "IT service incident log"`.

**Mutation policy audit and focused L3 results.** Under `verification/mutation_risk_policy.json`, all modified `research/` modules sit at tier **L3** (95% raw killed threshold; zero L4 modules touched; zero equivalent mutants approved; case-sensitive disk image `/Volumes/etlcs/repo`). Focused mutation on every new/changed Wave 23 view function passed cleanly:
- C3 (`a3badd3`): `noaa_coops_tides` `194/197 (98.48%)`, `noaa_gml_co2_weekly` `150/155 (96.77%)`, `zen_cnc_milling` `155/163 (95.09%)`.
- C2b (`d994640`): `_num_clean` `13/13 (100.00%)`, `wb_lending_projects` `222/232 (95.69%)`, `zen_queensland_petrol` `93/94 (98.94%)`, `inpi_bce_ratios` `122/125 (97.60%)`.
- C6 (`0ba782b`): `_write_jsonl` `18/18 (100.00%)`, `ror_organizations` `93/93 (100.00%)`, `rcsb_pdb_entries` `90/90 (100.00%)`, `nws_weather_alerts` `90/91 (98.90%)`.
- C2a (`d8f83a7`): `zen_port_noumea` `154/159 (96.86%)`, `zen_kanto_landslides` `98/99 (98.99%)`, `zen_nhif_hospital_cases` `144/149 (96.64%)`.
- C4 (`51b39a3`): `ingv_seismic_events` `163/170 (95.88%)`, `zen_gha_workflows` `174/175 (99.43%)`.
- C5 (`89374ca`): `wals_cldf` `110/111 (99.10%)`, `cordis_horizon_europe` `207/216 (95.83%)`.

**Wave 23 acquisitions (+16 independent provenance groups; zero natural anomaly labels claimed).**

| Group (`view`) | Category | Verified primary rights | Slice, quality & privacy facts |
|---|---|---|---|
| `noaa_coops` (`noaa_coops_tides`) | C3 | NOAA CO-OPS `disclaimers.html`: U.S. Federal Public Domain | `157,823` hourly rows across 6 coastal stations (`2022–2024`), `4,943` missing observations, `5,417` non-`0,0` QC flags preserved, `0` duplicates |
| `noaa_gml_co2` (`noaa_gml_co2_weekly`) | C3 | NOAA GML `disclaimer.html`: U.S. Federal Public Domain | `2,740` weekly Mauna Loa rows (`1974–2026`), `20` negative sentinel weeks masked to `NaN` |
| `cnc_five_axis_milling` (`zen_cnc_milling`) | C3 | Zenodo `10853254`: CC BY 4.0 | `189,089` multivariate sensor rows across 13 milling runs (`2021–2022`, 20 common signals); `957` identical duplicate polls dropped |
| `world_bank_projects` (`wb_lending_projects`) | C2b | World Bank Public Licenses: CC BY 4.0 | `5,000` unique sovereign lending projects across 10 pages; `teamleadname`, free-text titles/URLs/docs dropped |
| `queensland_petroleum_production` (`zen_queensland_petrol`) | C2b | Zenodo `23122560` / `publicdata.json`: Queensland DNRM CC BY 4.0 | `1,028` half-yearly field production records x 21 cols (`14` numeric volumes); `authorized_holder`, `remark`, `secondary_strat_unit_name`, `field_name_prod_corr` dropped |
| `inpi_bce_ratios` (`inpi_bce_ratios`) | C2b | `data.economie.gouv.fr` INPI BCE: Licence Ouverte v2.0 Etalab | `23,012` public corporate filings from SIREN-ordered first `30,000` rows (`6,988` confidential dropped); `siren` pseudonymised |
| `ror` (`ror_organizations`) | C6 | Zenodo `24378467` ROR v2.16: CC0 1.0 | `10,154` records (1-in-15 deterministic stride across `152,297` orgs sorted by ROR id), depth `5`, `35` paths, `8` optional; `0` emails, `redact_emails` applied |
| `rcsb_pdb` (`rcsb_pdb_entries`) | C6 | RCSB PDB `usage-policy`: CC0 1.0 | `1,000` structures (`2024:350`, `2025:350`, `2026:300`), depth `6`, `38` paths, `15` optional; `audit_author` and citation authors omitted in GraphQL query; `0` emails |
| `nws_alerts` (`nws_weather_alerts`) | C6 | NWS `disclaimer`: U.S. Federal Public Domain | `2,000` unique CAP GeoJSON alerts across 4 cursor pages, depth `5`, `62` paths, `25` optional; `sender` stripped at all depths & `redact_emails` (`0` emails) |
| `port_noumea_stopovers` (`zen_port_noumea`) | C2a | Zenodo `17275425`: CC BY 4.0 | `7,335 x 26` maritime stopovers (`2005–2013`, Latin-1 decoded); `shipping_agent`, `vessel_operator`, `vessel_name` dropped; `vessel_imo` pseudonymised; `flat_readiness.reasons=[]` |
| `kanto_landslides` (`zen_kanto_landslides`) | C2a | Zenodo `19047350`: CC BY 4.0 | `21,814 x 8` 1923 Kanagawa landslide records; 99.8% blank `Note` dropped; `flat_readiness.reasons=[]` |
| `nhif_hospital_cases` (`zen_nhif_hospital_cases`) | C2a | Zenodo `22213249`: CC BY 4.0 | `43,503 x 13` (`1-in-75` stride over `3,262,662` inpatient rows, `2024–2026`); `facility_name` pseudonymised; `22.51%` natural `diagnosis_secondary` missingness preserved; `flat_readiness.reasons=[]` |
| `ingv_seismic` (`ingv_seismic_events`) | C4 | INGV ISIDe portal: CC BY 4.0 | `17,755` seismic events (`minmagnitude>=1.5`, `2022–2024`) across `1,096` UTC days (non-BP); `Author`, `MagAuthor`, `EventLocationName`, blank catalog cols dropped |
| `github_actions_workflows` (`zen_gha_workflows`) | C4 | Zenodo `20340547`: CC BY 4.0 | `85,430` CI/CD edit events across `1,272` complete repos (`2019–2026`, `6 MB` gzip prefix; `13` trailing partial-repo rows dropped, non-BP); `author_*`, `committer_*`, `commit_hash`, `uid` dropped; `repository` pseudonymised; `0` emails |
| `wals_cldf` (`wals_cldf`) | C5 | `github.com/cldf-datasets/wals` v2020.3: CC BY 4.0 | `7` core linguistic typology tables (`3,573` languages, `76,475` values), `7` FKs (`6` with `0` orphans, `languages.Country_ID` `290/2,652 = 10.94%` natural orphans kept); `contributors.csv`, `Contributor*`, `Source`, `Comment`, `Description`, `Citation` omitted |
| `cordis_horizon_europe` (`cordis_horizon_europe`) | C5 | EC CORDIS `legal`: Decision 2011/833/EU (CC BY 4.0) | `6` EU grant tables (`2021–2026`): `24,419` projects reconstructed cleanly across multiline quotes + `379,605` child rows across `5` FKs (`0` orphans); project titles/objectives/keywords and org names/addresses/URLs/contacts/VAT/geo dropped; `organisationID` pseudonymised |

**Screened and rejected in Wave 23.** Existing blockers remain unchanged (`LANL`, `NHTSA FARS`, `NASA HTTP`, `NOAA GHCNh`, `OpenSky`, `SAP SALT`). Additional Wave 23 exclusions: `openfema:nfip-v3` (contractual revocable terms / HTTP 403 on terms endpoint), `chicago:vendor-payments` (`SEE_TERMS_OF_USE`, no open licence, individual payees), `zenodo:11259259-auctions` (third-party eBay scrapes with raw bidder usernames).

**Counts and diversity (machine-derived, `readiness.py` then `target_framework.py`).** C1 52, C2a 19, C2b 17, C3 25, C4 19, C5 27, C6 18 (remaining deficits to provisional planning quotas 0, 11, 13, 15, 9, 9, 12; **69** remaining deficit vs 85 before; **177** total participations vs 161 before); **166 distinct provenance groups** (150 before), **166 concrete generating systems** (149 before Phase 0 disambiguation), **166 producers** (150 before), **48 curators** (39 before), **85 domains** (69 before), **72 schema families** (56 before); `effective_groups` at `design_effect=0.2` rose to **87.9321** (**77.8074** at `0.5`). Overall largest-schema-family share fell from `42.7%` (`42.67%`) to **38.55%** (`64/166`), C4 `business process execution` fell from `47.1%` to **42.11%** (`8/19`), and C5 `timetable network` fell from `48.0%` to **44.44%** (`12/27`). Catalog (`dataset_catalog.py gap`) records **271** distinct source families (`249` open, `22` research_only).

**Verification and publication status.** `/Volumes/etlcs` was torn down after mutation testing. All 18 audited/acquired snapshots passed `Snapshot.verify() == []`, all 31 view files across those 18 datasets matched `experimental_views.json` SHA-256 digests 100%, the 10-file regression test suite and `ruff check .` / `ruff format --check .` passed cleanly, and `readiness.py` / `target_framework.py` / `dataset_catalog.py gap` produced zero diffs. No detector experiments ran under the active freeze; the manuscript (`paper/`) and slides (`slides/`) cite no Update 20–23 interim counts and remain intentionally unchanged (`no-change` outcome recorded).

## Update 24 — Wave 23 taxonomy audit, WALS CLDF relational fix, sampling standardization, and Wave 24 acquisitions (+21 groups)

This update audits the 16 Wave 23 provenance groups for artificial taxonomy inflation, resolves the WALS CLDF `languages.Country_ID` orphan anomaly at its root cause, standardizes explicit non-random sampling descriptors across bounded acquisitions, and integrates **21 new independent provenance groups** across all six deficient categories (`C3 +4`, `C2b +4`, `C6 +4`, `C2a +3`, `C4 +3`, `C5 +3`) while keeping the experiment freeze active (`0` detector runs, `paper/` and `slides/` unchanged).

**1. Wave 23 taxonomy diversity and concentration audit (`63f8e3f`).**
- **Curator normalization (`48 -> 46` at the 166-group baseline):** Merged casing duplicate `"Zenodo"` (`queensland_petroleum_production`, `ror`) into `"zenodo"`, and corrected curator vs producer conflation on `noaa_coops` (`"noaa_coops" -> "noaa"`) and `noaa_gml_co2` (`"noaa_gml" -> "noaa"`), aligning both with existing `"noaa"` (`nws_alerts`).
- **Domain and schema-family consolidations and de-particularization (`85 -> 84` domains, `72 -> 71` schema families at the 166-group baseline):**
  - `noaa_coops`: retained `domain = "coastal tide and water-level monitoring"` (astronomical tidal mechanics and storm surge distinct from inland river discharge), but merged `schema_family` from `"coastal tide and meteorology hourly csv"` into existing `"gauging time series"` (`ea_hydrology`, `usgs_water`) because both represent fixed-station water-level/flow gauge telemetry with value and quality-flag columns.
  - `noaa_gml_co2`: merged `domain` from `"atmospheric greenhouse gas monitoring"` into existing `"environmental monitoring"` (`airquality_italy`, `dwd_germany`, `epa_aqs`) and generalized `schema_family` from `"atmospheric trace gas weekly flask/in-situ csv"` to `"atmospheric gas concentration time series"`.
  - Replaced source-named taxonomy strings with general scientific concepts: `cnc_five_axis_milling` (`schema_family -> "cnc machining process telemetry"`), `world_bank_projects` (`domain -> "multilateral development finance"`, `schema_family -> "development lending project ledger"`), `ror` (`schema_family -> "organization identifier registry json"`), `rcsb_pdb` (`domain -> "structural biology"`, `schema_family -> "macromolecular structure archive json"`), and `cordis_horizon_europe` (`schema_family -> "research grant relational tables"`).
  - Retained genuinely distinct mechanisms across the remaining nine Wave 23 groups (`queensland_petroleum_production`, `inpi_bce_ratios`, `nws_alerts`, `port_noumea_stopovers`, `kanto_landslides`, `nhif_hospital_cases`, `ingv_seismic`, `github_actions_workflows`, `wals_cldf`).
  - Because every merged family had size 1–2 while the dominant family (`uci flat tabular`, 64 groups) was untouched, the 166-group baseline largest-schema-family share (`38.55%`), C4 business-process share (`42.11%`), and C5 timetable share (`44.44%`) were unaffected by these taxonomy normalizations (`effective_groups` at `166` groups: `87.7351` at `0.2`, `77.6741` at `0.5`).

**2. Targeted scientific integrity checks (`63f8e3f`).**
- **Concrete generating-system identity (`rabobank_ict` vs `volvo_it`):** Verified in `source_attributes.json` that `rabobank_ict` (`Rabobank Group ICT incident management system`, BPI Challenge 2014) and `volvo_it` (`Volvo IT Belgium incident management system`, BPI Challenge 2013) represent two separate enterprise IT service management installations operated by independent organizations, while sharing `structure.C4 = "IT service incident log"`. `target_framework.py` does not enforce a hard equality invariant between concrete generating systems and provenance groups.
- **WALS CLDF relational consistency (`wals_cldf`):** Root-cause investigation of the 290/2,652 (`10.94%`) reported orphans on `languages.Country_ID -> countries.ID` identified two ingestion defects rather than upstream data corruption:
  1. `pd.read_csv(handle, dtype=str)` without `keep_default_na=False` parsed ISO-3166-1 alpha-2 `"NA"` (Namibia, present in `countries.csv` and 25 single-country rows of `languages.csv`) as `NaN`.
  2. In WALS CLDF `cldf-metadata.json`, `languages.Country_ID` is declared with `"separator": " "` (a whitespace-separated list of ISO-2 country codes for cross-border languages, e.g. `"PG ID"` in 290 multi-country rows), which cannot be checked as a scalar foreign key without normalization.
  - **Fix:** Updated `_build_wals_cldf` to pass `keep_default_na=False` across all tables and updated `wals_cldf_view` to emit the normalized 2-column junction table `language_countries.csv` (`3,023` `(Language_ID, Country_ID)` pairs) plus the self-referential FK `languages.Parent_ID -> languages.ID`. The resulting 8-table, 9-FK relational view has **`0` orphans across all 162,796 checked references** (`0.0%` orphan share). Focused L3 mutation scored `wals_cldf_view` **`37/37 (100.00%)`** and `_build_wals_cldf` **`100/102 (98.04%)`**.
- **Sampling and selection-bias metadata:** Audited and standardized explicit non-random sampling classifications across bounded/filtered sources in `acquisition_sources.json`, `readiness_facts.json`, and `experimental_views.py` (`inpi_bce_ratios` identifier-ordered prefix; `wikimedia_simplewiki_edits` page-ID gzip prefix; `zen_gha_workflows` repo-ordered gzip prefix; `zen_nhif_hospital_cases` stride-75 sample; `ror_organizations` stride-15 sample; `uk_charity_register` 1-in-20 slice; `epa_aqs_ozone_hourly` and `dwd_hourly_climate` strided station samples; `azure_packing_2020` modulo-100 tenant filter; `osv_go_advisories` `GO-*` prefix filter; `rcsb_pdb_entries`, `ingv_seismic_events`, and `noaa_coops_tides` date-restricted/fixed-station slices). No non-random acquisition is described as a random sample.

**3. Wave 24 acquisitions (+21 independent provenance groups; zero natural anomaly labels claimed).**

| Group (`view`) | Cat. | Verified primary rights | Slice, quality & privacy facts | Focused L3 mutation (view / builder) |
|---|---|---|---|---|
| `telecom_operator_kpis` (`zen_telecom_kpis`) | C3 | Zenodo `8147768`: CC BY 4.0 | `150,332` 5-min KPI rows across 14 real operator traces (`data_real/`); synthetic `data_series/` excluded | `27/27 (100.00%)` / `92/94 (97.87%)` |
| `danish_district_heating` (`zen_dk_district_heating`) | C3 | Zenodo `17398331`: CC BY 4.0 | `105,192` hourly UTC rows across 3 Danish DMAs (`2016–2019`), 10 joined smart-meter & weather variables | `77/78 (98.72%)` / `90/92 (97.83%)` |
| `german_water_demand` (`zen_water_demand`) | C3 | Zenodo `11045013`: CC BY 4.0 | `46,026` raw un-imputed hourly rows (`2016–2021`) preserving natural SCADA sensor `NaN` gaps; `5` spring-DST invalid local-hour rows dropped | `88/90 (97.78%)` / `81/82 (98.78%)` |
| `dmsp_ssj_auroral` (`zen_dmsp_auroral`) | C3 | Zenodo `3373812`: CC BY 4.0 | `68,034` orbital polar-pass boundary & energy-flux rows across `4,594` daily CSVs (`DMSP F16/F17/F18`, `2010–2014`) | `77/80 (96.25%)` / `114/116 (98.28%)` |
| `us_treasury_dts` (`us_treasury_dts`) | C2b | Fiscal Data FAQ: 17 U.S.C. 105 U.S. Public Domain | `91,119` daily federal operating-cash deposit/withdrawal rows (`2024–2025`, 19 API pages) | `24/24 (100.00%)` / `93/96 (96.88%)` |
| `fdic_bank_financials` (`fdic_bank_financials`) | C2b | FDIC `api.fdic.gov`: 17 U.S.C. 105 U.S. Public Domain | `18,402` Q4 year-end call-report filings (`2022–2025`) across `4,798` institutions (`CERT` salted-pseudonymised) | `51/53 (96.23%)` / `82/85 (96.47%)` |
| `sncf_tgv_regularite` (`sncf_tgv_regularite`) | C2b | SNCF Open Data: ODbL 1.0 (local only) | `12,907` monthly high-speed route rows (`2018-01..2026-09`) x 18 cols; `commentaire*` free-text cols dropped | `15/15 (100.00%)` / `82/83 (98.80%)` |
| `dgccrf_fuel_prices` (`dgccrf_fuel_prices`) | C2b | `donnees.roulez-eco.fr`: Licence Ouverte v2.0 Etalab | `32,699` melted active retail fuel postings across `9,593` salted-pseudonymised stations & 6 fuels; street addresses & coordinates dropped | `49/49 (100.00%)` / `106/107 (99.07%)` |
| `federal_register` (`us_federal_register`) | C6 | 17 U.S.C. 105 / 44 U.S.C. 1507 U.S. Public Domain | `2,000` 2025 regulatory documents (20 API pages), depth `6`, `1,145` paths, `1,120` optional; `redact_emails` (`0` emails) | `18/18 (100.00%)` / `66/67 (98.51%)` |
| `datacite_dois` (`datacite_dois`) | C6 | DataCite Policy: CC0 1.0 Universal | `1,000` 2025 dataset DOIs (10 API pages), depth `8`, `91` paths, `45` optional; `creators`, `contributors`, `descriptions` stripped (`0` emails); shares `domain = "scholarly metadata"` with Crossref/OpenAlex | `19/19 (100.00%)` / `68/68 (100.00%)` |
| `gbif_occurrences` (`gbif_cc0_occurrences`) | C6 | GBIF per-record filter: CC0 1.0 Universal | `1,500` 2024 CC0 biodiversity occurrences (5 API pages), depth `6`, `189` paths, `85` optional; collector/identifier/locality/media-creator PII stripped (`0` emails) | `23/23 (100.00%)` / `68/68 (100.00%)` |
| `chembl_molecules` (`chembl_molecules`) | C6 | EMBL-EBI ChEMBL: CC BY-SA 3.0 (local only) | `1,000` ChEMBL_37 small-molecule records (10 API pages), depth `5`, `71` paths, `26` optional (`0` emails) | `18/18 (100.00%)` / `67/67 (100.00%)` |
| `florida_bridge_inspections` (`zen_florida_bridges`) | C2a | Zenodo `18142339` / FHWA NBI: CC BY 4.0 & Public Domain | `12,986 x 33` bridge inspection records; FHWA `'N'` not-applicable codes preserved as categorical tokens; `bridge_id` salted-pseudonymised; `flat_readiness C2a=[]` | `19/19 (100.00%)` / `78/79 (98.73%)` |
| `wri_global_power_plants` (`wri_power_plants`) | C2a | WRI v1.3.0: CC BY 4.0 | `34,936 x 16` power plants across 167 countries; `name`, `owner`, `url`, `wepp_id` & >50%-missing secondary-fuel/year cols dropped; `flat_readiness C2a=[]` | `14/14 (100.00%)` / `92/93 (98.92%)` |
| `paris_urban_trees` (`paris_urban_trees`) | C2a | Ville de Paris Open Data: ODbL 1.0 (local only) | `25,000 x 10` `idbase`-ordered prefix of 220,279 municipal trees across 150 genera; addresses/coords/>50%-missing cols dropped; `flat_readiness C2a=[]` | `14/14 (100.00%)` / `81/83 (97.59%)` |
| `moodle_lms_events` (`zen_moodle_events`) | C4 | Zenodo `21410580`: CC BY 4.0 | `182,114` LMS clickstream events across `8,940` user-day sessions (`147` salted users, `54` English-mapped activities; non-BP) | `52/52 (100.00%)` / `101/106 (95.28%)` |
| `naoj_norp_solar_bursts` (`zen_norp_solar_bursts`) | C4 | Zenodo `21300266`: CC BY 4.0 | `4,239` solar radio bursts across `326` active year-months (`1988–2025`); `124` midnight-rollover bursts adjusted +1 day; non-BP | `105/109 (96.33%)` / `84/85 (98.82%)` |
| `fermi_blazar_flares` (`zen_blazar_flares`) | C4 | Zenodo `23039054`: CC BY 4.0 | `3,598` extragalactic gamma-ray flares across `565` blazar sources ordered by `source_id`, `start_met`; `"-"` parsed as `NaN`; non-BP | `25/26 (96.15%)` / `87/91 (95.60%)` |
| `wind_fragility_power_db` (`zen_wind_fragility`) | C5 | Zenodo `23399966`: CC BY 4.0 | `5` tables (`507` curves, `507` discretized, `1,988` parameters, `45,608` points, `52` sources = `48,662` rows), `5` FKs with `0` orphans; authors/titles/notes dropped | `10/10 (100.00%)` / `89/90 (98.89%)` |
| `terralore_chronicle_db` (`zen_terralore_chronicle`) | C5 | Zenodo `22059347`: CC BY 4.0 | `3` tables (`4,564` events, `3,922` sources, `8,268` `event_sources` junction rows = `16,754` rows), `2` FKs with `0` orphans; `keep_default_na=False`; summaries/titles/URLs dropped | `10/10 (100.00%)` / `81/83 (97.59%)` |
| `noaa_ncei_storm_events` (`ncei_storm_events_2024`) | C5 | NOAA NCEI: 17 U.S.C. 105 U.S. Public Domain | `3` tables (`69,802` details, `40,258` locations, `1,142` fatalities = `111,202` rows, 2024 release `c20261119`), `3` FKs with `0` orphans; narratives & fatality age/sex dropped | `10/10 (100.00%)` / `88/89 (98.88%)` |

**4. Screened and excluded in Wave 24 (13 candidates recorded in `candidate_ledger.json`).**
- `zenodo:23927968-ntsb-scrape` (C5): third-party multi-source scrape across NTSB/Wiki/FAA without first-party relational provenance.
- `zenodo:23936968-acai` (C5): 1.54 GB archive exceeds bounded reproducible acquisition budget.
- `zenodo:20818296-polish-electricity` (C3): single-column 300-row series below minimum unit and multivariate richness thresholds.
- `zenodo:24080064-aemo-nem` (C3): third-party compilation without verified upstream AEMO copyright waiver.
- `sec:edgar-financial-statements` (C5): `www.sec.gov` returns HTTP 403 Forbidden to automated requests.
- `fda:drugsatfda` (C5): shares FDA CDER agency/platform lineage with existing `openfda_faers` and `fda_maude`.
- `eurostat:sdmx` (C3): low-frequency monthly/quarterly macroeconomic aggregates rather than physical/operational telemetry.
- `energinet:dk` (C3): transmission-grid electricity series overlapping existing RTE `eco2mix` grid telemetry family.
- `artic:chicago` (C6): museum collection JSON schema family already represented by `met_museum_objects`.
- `musicbrainz:api` (C6): strict 1 req/sec rate limit and living-artist personal birth/death/alias attributes.
- `nasa:donki` (C4): space-weather flare notification mechanism covered with higher completeness and 37-year span by NAOJ NoRP (`zen_norp_solar_bursts`).
- `zenodo:22028206-openrail` (C5): single flat GeoPackage/CSV layer without multi-table foreign-key relationships.
- `nasa:meteorite-landings` (C2a): `data.nasa.gov` Socrata endpoint stalled >3 minutes without response across two acquisition attempts; replaced by City of Paris Municipal Urban Tree Inventory (`paris_urban_trees`).

**5. Counts, diversity, concentration, and effective groups (machine-derived, `readiness.py` then `target_framework.py`).**
- **Category coverage (`198` total participations vs `177` before; `48` remaining category deficits vs `69` before):**
  - `C1`: **52 / 36** (`0` remaining)
  - `C2a`: **22 / 30** (`8` remaining; was `19 / 30`, `-3` deficit)
  - `C2b`: **21 / 30** (`9` remaining; was `17 / 30`, `-4` deficit)
  - `C3`: **29 / 40** (`11` remaining; was `25 / 40`, `-4` deficit)
  - `C4`: **22 / 28** (`6` remaining; was `19 / 28`, `-3` deficit)
  - `C5`: **30 / 36** (`6` remaining; was `27 / 36`, `-3` deficit)
  - `C6`: **22 / 30** (`8` remaining; was `18 / 30`, `-4` deficit)
- **Taxonomy diversity:** **187** independent provenance groups (`166` before), **187** concrete generating systems (`166` before), **187** original producers (`166` before), **54** curators (`48` before Phase 0 normalization to `46`, `+8` in Wave 24), **104** domains (`85` before Phase 0 normalization to `84`, `+20` in Wave 24), **92** schema families (`72` before Phase 0 normalization to `71`, `+21` in Wave 24).
- **Concentration reductions:**
  - Overall largest schema family (`uci flat tabular`): **`34.22%`** (`64/187`, down from `38.55%` [`64/166`]).
  - C4 `business process execution`: **`36.36%`** (`8/22`, down from `42.11%` [`8/19`]).
  - C5 `timetable network`: **`40.00%`** (`12/30`, down from `44.44%` [`12/27`]).
- **Effective independent groups (`target_framework.json`):**
  - `design_effect = 0.2`: **`108.4083`** (up from `87.9321`).
  - `design_effect = 0.5`: **`97.9741`** (up from `77.8074`).
- **Catalog (`dataset_catalog.py gap`):** **292** distinct source families (`270` open, `22` research_only).

**6. Verification and publication status.**
- All 44 new/modified functions across `wals_cldf` and the 21 Wave 24 views passed focused L3 mutation testing on case-sensitive `/Volumes/etlcs/repo` (`>= 95.28%` raw killed on every function; `0` equivalent mutants approved), after which `/Volumes/etlcs` was cleanly unmounted.
- All 22 audited/acquired snapshots (`wals_cldf` + 21 Wave 24 sources) passed `Snapshot.verify() == []`, and all 37 view files across those 22 datasets matched `experimental_views.json` SHA-256 digests 100%.
- All **535** tests across the 10-file regression test suite (`test_acquisition.py`, `test_acquisition_validate.py`, `test_dataset_catalog.py`, `test_experimental_views.py`, `test_flat_readiness.py`, `test_provenance_audit.py`, `test_readiness.py`, `test_target_framework.py`, `test_view_builders.py`, `test_view_contracts_extra.py`) passed, `ruff check .` and `ruff format --check .` passed across 677 files, and consecutive runs of `readiness.py`, `target_framework.py`, and `dataset_catalog.py gap` produced zero diffs.
- No detector experiments ran under the active freeze. The manuscript (`paper/`) and slides (`slides/`) do not cite interim Wave 20–24 acquisition counts and remain intentionally unchanged (`no-change` outcome recorded).

## Update 25 — Wave 25 acquisitions (+5 groups) and the exclusion of five screened candidates

Five independent provenance groups were integrated through the existing pipeline (`acquisition_sources.json`, `experimental_views.py` builders, readiness facts, source attributes); no natural anomaly label is claimed for any of them. Everything below is derived from the regenerated `readiness.json`, `target_framework.json` and `stratum_gap.*`.

**1. Wave 25 acquisitions.**

| Group (`view`) | Cat. | Verified primary rights | Slice, quality and privacy facts | Focused mutation (view / builder) |
|---|---|---|---|---|
| `ourairports_db` (`ourairports_db`) | C5 | Repository `LICENSE` (Unlicense) and producer data page (Wayback copy; live page has an expired TLS certificate): Public Domain | Complete 2026-11-22 dump, `6` tables (`86,377` airports, `48,437` runways, `30,400` frequencies, `11,008` navaids, `249` countries, `3,987` regions = `180,458` rows), `9` FKs with `0` orphans; read with `keep_default_na=False` (ISO code `NA`); link and keyword text dropped; volunteer-curated, completeness varies by country | `10/10 (100.00%)` / `72/74 (97.30%)` |
| `cftc_cot_disaggregated` (`cftc_cot_disaggregated`) | C2b | CFTC web policy, Copyright: "Government information at the CFTC website is in the public domain" | `27,231` weekly contract-level rows (2024-01-02 to 2025-12-30, `346` contract names), `21` of `194` columns (all-period trader-class long/short/spread positions) | `34/34 (100.00%)` / `79/80 (98.75%)` |
| `ndbc_buoys_2023` (`ndbc_buoys_2023`) | C3 | NWS disclaimer (NDBC is an NWS centre): Public Domain; the NDBC-specific disclaimer page returned Access Denied to automated clients | Fixed-station selection of seven NDBC-operated moored buoys (`41002`, `41004`, `42040`, `44025`, `46013`, `46042`, `51001`), calendar 2023, `360,156` ten-minute rows; publisher missing codes mapped to NaN (wave columns about `68%` missing), empty `VIS` and `TIDE` dropped | `53/53 (100.00%)` / `73/74 (98.65%)` |
| `a_day_in_daylight` (`zen_daylight_events`) | C4 | Zenodo `24164071`: CC BY 4.0 | `events.csv` only: `1,763` contextual event intervals of `47` participants (single equinox-week campaign, convenience sample); ids re-pseudonymised, local timestamps dropped; light series, age, sex and coordinates not acquired | `21/21 (100.00%)` / `75/77 (97.40%)` |
| `cpsc_recall_notices` (`cpsc_recalls`) | C6 | CPSC Privacy and Security Notice (recall notices may be freely copied and distributed; third-party photographs excluded and not retained) and 17 U.S.C. 105; policy pages return HTTP 403 to the acquisition client and were read separately | `725` recall notices dated 2024-2025, depth `4`, `47` paths, `12` optional, `13` object-array fields; contact line, images and page link dropped, e-mails redacted | `19/19 (100.00%)` / `60/60 (100.00%)` |

**2. Screened and excluded (5 entries in `candidate_ledger.json`).**
- `zenodo:19370391-jirau-hydro` (C3): the Jirau generating-unit extract is seven event-centred windows of `130` to `769` rows (`1.4` to `8` days) with `10` events and trip events dated after the publication date; no meaningful chronological split per series. Raw data was fetched and not integrated.
- `chicago:food-inspections` (C2a): the portal licence field reads "See Terms of Use" and the terms contain a disclaimer only.
- `noaa:ibtracs` (C4): merges track records of several agencies, so the independence of the generating system is not established (same reason as GHCNh).
- `datagouv:catalogue-api` (C6): no retrievable licence statement for catalogue metadata; records carry user objects.
- `nih:reporter` (C6): the endpoint needs POST; the acquisition framework supports GET only and was not extended for one source.

**3. Counts, diversity, concentration and effective groups (machine-derived).**
- Category coverage (`203` participations vs `198`; `43` remaining deficits vs `48`): `C1` 52/36 (0), `C2a` 22/30 (8), `C2b` 22/30 (8, was 21), `C3` 30/40 (10, was 29), `C4` 23/28 (5, was 22), `C5` 31/36 (5, was 30), `C6` 23/30 (7, was 22).
- Taxonomy: `192` independent groups, `192` producers, `57` curators, `109` domains, `97` schema families.
- Concentration: largest schema family `33.33%` (was `34.22%`); C4 business-process execution `34.78%` (`8/23`); C5 timetable network `38.71%` (`12/31`).
- Effective independent groups: `113.4083` (design effect `0.2`), `102.9741` (`0.5`). Catalog: `297` distinct source families (`275` open, `22` research_only).

**4. Verification.**
- The 10-file regression suite (`test_acquisition`, `test_acquisition_validate`, `test_dataset_catalog`, `test_experimental_views`, `test_flat_readiness`, `test_provenance_audit`, `test_readiness`, `test_target_framework`, `test_view_builders`, `test_view_contracts_extra`) passed (`545` tests), `ruff check .` and `ruff format --check .` passed on `677` files, and a second run of `readiness.py`, `target_framework.py` and `dataset_catalog.py gap` produced no diff.
- The five new snapshots passed `Snapshot.verify() == []` and the built view files match the registered SHA-256 digests.
- Focused mutation (`mutmut`, case-sensitive volume, tests narrowed to the two view-test files and the five new groups) reached `>= 97.30%` on every new function; `0` equivalent mutants were approved. The survivors are pandas-equivalent mutants (`index=None` for `index=False`, `keep_default_na=None` for `False`). The first run showed `91.78%` to `94.59%` on four builders; the tests were strengthened (text kept as published, literal `NA` category, whitespace-aligned rows, non-numeric cells, empty input) and the code simplified (no timestamp parsing) rather than the bar lowered.
- Environment finding: the local `.venv` had drifted to pandas `3.1.1` and numpy `2.5.5` against the locked `3.0.6` and `2.4.6`, and its Python interpreter was missing (reinstalled with `uv python install 3.13`). Under the drifted pandas, five older views (`sncf_tgv_regularite`, `wri_power_plants`, `zen_blazar_flares`, `zen_dk_district_heating`, `zen_queensland_petrol`) serialize to different bytes with identical rows. Their committed digests were kept and re-confirmed under the pinned versions (all `15` rebuilt view files match). Views and mutation were therefore run in a venv pinned to the lock versions (Python `3.13`; the earlier focused runs used `3.11`).
- No detector experiments ran under the active freeze. The manuscript (`paper/`) and slides (`slides/`) do not cite interim acquisition counts and remain unchanged (`no-change` outcome recorded).

## Update 26 — Environment audit, CPSC rights evidence and Wave 26 (+1 group; NIH ExPORTER without POST support)

**1. Environment.** The canonical environment is the conda environment `etl-benchmark` (`environment.yml`, `verification/environment/conda-darwin-arm64.explicit.txt`): Python `3.11.17`, pandas `3.0.6`, numpy `2.4.6`, scipy `1.17.1`, scikit-learn `1.9.1`, pytest `9.1.1`; it matches the lock and was used for every Wave 26 build and test. The `.venv` (Python `3.13.18`, pandas `3.1.1`, numpy `2.5.5`) is not an environment of record; only its `ruff` was used. The mutation environment `~/.cache/etl-mutation-venv` carries the same pins for pandas, numpy, scipy, scikit-learn and pytest (Python `3.13.18`) and builds byte-identical views to the conda environment. No lock file and no digest was changed.

**Open finding (owner decision needed).** A full rebuild of all views under the locked pandas `3.0.6` reproduces `396` of the `412` committed view digests. The other `16` files (`4tu_bpic12`, `4tu_bpic18`, `bikeshare_capital`, six `flat_uci_*_C1`, `panels/rki_notaufnahme`, `series/uci_357`, `zen_care_wind_a`, `zen_care_wind_b`, `zen_kelmarsh`, `zen_metropt2`, `zen_unisg_factory`) were stamped on `2026-11-21` under the drifted pandas `3.1.x`, whose `to_csv` drops trailing zeros of fractional seconds (`22:38:44.546+00:00` against `22:38:44.546000+00:00` under `3.0.6`). The files on disk still match the committed digests; for `4tu_bpic12` and `4tu_bpic18` the content is identical after normalising fractional-second zeros. No digest was restamped. Until the owner decides whether to keep the committed bytes or regenerate those views under the lock (which would require replaying any experiment that read them), do not run the full `research.experimental_views` build into `data/experimental`; build new views one builder at a time.

**2. CPSC rights (`cpsc_recalls`, retained).** The CPSC Privacy and Security Notice (Copyright section) was read on `2026-11-22`: recall notices, including photographs of recalled items, may be freely copied and distributed without permission; other use of photographs may require the copyright holder's permission; users are asked to credit CPSC and not to imply endorsement. The Recall API and Data pages state no separate terms or rate limits. 17 U.S.C. 105 denies copyright protection to works of the U.S. Government but does not by itself cover third-party material, so it is cited as supporting, not sufficient. The retained view holds recall-notice text and structured lists only; `Images` (photographs and captions), `URL` and `ConsumerContact` are dropped and e-mail addresses are redacted. The rights text in `acquired_sources.json`, `acquisition_sources.json`, `candidate_ledger.json` and Update 25 was corrected accordingly; no data changed.

**3. NIH decision.** The RePORTER search API needs POST, but the official ExPORTER bulk file `RePORTER_PRJ_C_FY2024.zip` is a plain GET download that redirects to `public.era.nih.gov` (already supported through `redirect_hosts`). POST support was therefore not added and the request pattern, bounded size (`100 MiB` cap), timeout and retry policy are those of the existing framework. One download was made on a Sunday, within the published guidance (about one request per second; large jobs at weekends or 21:00 to 05:00 EST). No licence text could be retrieved (the ExPORTER page renders only through JavaScript and the NIH disclaimer returns HTTP 403); the retained fields are NIH-generated administrative award records (17 U.S.C. 105), and grantee-authored text, names and organisation identity are not retained. The ledger entry `nih:reporter` changes from `excluded` (C6) to `experiment_ready` (C2a; the CSV is flat, so no C6 claim).

**4. Wave 26 acquisition.**

| Group (`view`) | Cat. | Generating system and producer | Slice, quality and privacy facts | Focused mutation |
|---|---|---|---|---|
| `nih_research_grants` (`nih_reporter_projects_fy2024`) | C2a | NIH grant award administration (RePORTER ExPORTER), NIH | Complete fiscal-year 2024 file: `83,314` unique awards (`0` duplicates), `19` coded, date and cost columns (`154` activity codes, `40` institutes, `12` funding mechanisms, `406` study sections, `63` countries); natural missingness in cost, institution type and state kept; names, titles, terms, public health relevance, organisation identity, constant fiscal year and the high-cardinality spending-category lists dropped; application id pseudonymised | `111/112` killed (`99.11%`); the survivor is the pandas-equivalent `index=None` mutant, not approved |

No natural anomaly label is claimed (`controlled_injection`). The group is independent of the EU CORDIS register (different producer, award mechanism and schema), although both belong to the research-funding domain.

**5. Counts (machine-derived).** Category participations `204` (was `203`); remaining deficits `42` (was `43`): `C2a` 23/30 (7, was 8); other categories unchanged (`C1` 52/36, `C2b` 22/30, `C3` 30/40, `C4` 23/28, `C5` 31/36, `C6` 23/30). `193` independent groups, `193` producers, `58` curators, `110` domains, `98` schema families; largest schema family `33.16%` (was `33.33%`); C4 business-process execution `34.78%` and C5 timetable network `38.71%` unchanged. Effective groups `114.4083` (design effect `0.2`) and `103.9741` (`0.5`). Catalog: `298` distinct source families (`276` open, `22` research_only).

**6. Verification.** In the conda environment: `research/tests/test_experimental_views.py` and `test_view_builders.py` pass; the full `research/tests` run has one failure, `test_pool_contracts.py::test_result_files_use_sorted_keys_and_the_documented_layout[lb]` (`TypeError`, unexpected `seeds` argument), in a file this wave does not touch (it fails identically at `8a54cb4`). `Snapshot.verify()` returned no mismatches for the new snapshot and the rebuilt view digest equals the registered one. Readiness, target-framework and stratum-gap reports were regenerated. Mutation on the Update 26 builders needs `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` on this machine, otherwise `mutmut` aborts while listing tests.

No detector experiments ran under the active freeze; T424 is not authorised. The manuscript and slides do not cite interim acquisition counts and are unchanged (`no-change` outcome recorded).


## Update 27 — Historical view reproduction, pool-contract fix, NIH rights text and Wave 27 (+3 C3 groups)

**1. The 16 historical views (no committed file or digest changed).** The 16 files of Update 26 were rebuilt one builder at a time into a scratch directory outside the repository, with the committed `data/acquired` snapshots and the committed builder code. Under the historical generation environment (`.venv`: Python `3.13.18`, pandas `3.1.1`, numpy `2.5.5`, pyarrow `26.0.1`) all 16 reproduce byte for byte, with SHA-256 equal to the committed digests (`94` of `94` files of the ten affected builders match). Under the canonical lock (conda `etl-benchmark`: Python `3.11.17`, pandas `3.0.6`, numpy `2.4.6`, pyarrow `25.0.0`) the same ten builders reproduce `78` of `94` files; the 16 differing files have identical shape, columns and row order to the committed ones. No view remains irreproducible, but the reproduction needs the historical environment. The differences are of three kinds:

| Kind | Files | Cause (pandas `3.0.6` against `3.1.1`) | Value effect |
|---|---|---|---|
| Datetime text | `4tu_bpic12`, `4tu_bpic18`, `zen_unisg_factory` | `to_csv` of timezone-aware timestamps pads the fractional seconds to six digits (`.546000`) or drops a zero fraction (`.000`) | none: `3.0.6` and `3.1.1` text parse to equal timestamps in every cell (`262,200`, `487,270` and `3,446` cells) |
| Float text | `flat_uci_162/464/572/760/942_C1`, `panels/rki_notaufnahme`, `series/uci_357`, `zen_care_wind_a`, `zen_care_wind_b`, `zen_kelmarsh`, `zen_metropt2` | the default `read_csv` float parser of `3.0.6` is not round-trip exact, so a value is re-written one or more digits short (`0.00582910956867457` becomes `0.0058291095686745`); `3.1.1` parses exactly (a toy check showed that `float_precision="round_trip"` makes `3.0.6` parse the sample strings exactly; it was not applied to the 16 files) | none after re-parsing in `3.0.6`, but the stored text differs in `8` to `1,189,942` cells per file |
| Float values | `bikeshare_capital` (`duration_min`, `175` of `607` differing cells), `flat_uci_864_C1` (`6` of `12`) | the same parser difference in a column that is then computed or aggregated | at most `5.4e-15` relative (a few units in the last place) |

Semantic equivalence therefore holds for the datetime and most float differences, and not strictly for the `181` cells of the last row (last-digit differences). Byte equivalence holds only under `3.1.1`. No compatibility code was added and no experiment was replayed; new views keep using the canonical environment and one builder at a time. The remaining concern for release certification is that the canonical lock does not rebuild the committed bytes of these 16 files. The owner may keep the committed bytes with this documented environment (current state), or regenerate under the lock and replay the experiments that read them; neither has been done. The mutation environment `~/.cache/etl-mutation-venv` (pandas `3.0.6`) shares the canonical behaviour.

**2. Pool-contract test.** `test_pool_contracts.py::test_result_files_use_sorted_keys_and_the_documented_layout[lb]` failed with `TypeError: unexpected keyword argument 'seeds'`. Cause: the test replaced `run_job` with `lambda job, methods=None`, while `labelled_benchmark.main` has bound `seeds` since commit `92d07aa` (the `--seeds` option). The production code is correct and no result file is involved; the stub now accepts `seeds=None`. The full `research/tests` suite passes in the conda environment.

**3. NIH rights text.** The retained NIH fields are administrative award records generated by the awarding federal agency; the rights basis is 17 U.S.C. 105, not any statement about material created by grantees (publications, data, software, abstracts), which can carry separate rights and none of which is retained. The `ADMINISTERING_IC` values also include awards administered by other federal components in RePORTER (for example VA `2,181` awards and CDC centres), which fall under the same basis; the registry text said NIH only and now says so. Coded applicant-entered fields (institution type, state, country) are factual administrative metadata. No data or view digest changed. The group stays retained; no new evidence reopens it.

**4. Candidate review.** `zenodo:820576` (AEGIS) is already integrated (`zen_aegis_vehicle`). `zenodo:12697471` (RKI vaccinations) shares the producer and publisher of the integrated RKI hospitalisation and emergency-department series, so it is not counted as an independent group. `zenodo:24397792` (DIVI intensive-care register inside an RKI deposit) is a different register operator but is published and curated through the same RKI deposit; it stays unintegrated pending an independence decision. `zenodo:6647220` stays blocked on missing documentation. Candidates examined and rejected this wave: BfS ODL gamma dose rate (the open WFS exposes the hourly layer for one week and the daily layer for one station only), USDA FoodData Central foundation file (the release lacks `food.csv` and `food_nutrient.csv`, so keys dangle), FAA aircraft registry (HTTP 503), BDG2 (595 MB archive reachable only as one Zenodo file with a slash in its key; deferred), BIDMC (relative time of eight minutes per patient).

**5. Wave 27 acquisition.**

| Group (`view`) | Cat. | Generating system and producer | Slice, quality and privacy facts | Focused mutation |
|---|---|---|---|---|
| `ecb_euro_fx_reference_rates` (`ecb_fx_reference_rates`) | C3 | ECB daily euro foreign exchange reference rate procedure, European Central Bank; free use with citation and statement of modifications (ECB copyright page, read `2026-11-22`) | complete history: `7,141` business-day rows, `1999-01-04` to `2026-11-20`, `41` currencies, `70,644` of `292,781` cells N/A kept as NaN; no personal data | `125/129` killed (`96.90%`) |
| `seattle_fremont_bridge_counter` (`seattle_fremont_bridge`) | C3 | Seattle DOT inductive-loop bicycle and scooter counter on the Fremont Bridge, City of Seattle; Public Domain (Socrata metadata) | complete hourly export: `122,675` contiguous hourly rows, `2012-10-02` to `2026-09-30`, local wall-clock time; `30` blank hours kept missing; east and west pathway counts and their total | `113/114` killed (`99.12%`) |
| `nsidc_sea_ice_index` (`nsidc_sea_ice_index`) | C3 | NOAA at NSIDC passive-microwave Sea Ice Index v4, NSIDC; free use with credit and data citation (NSIDC citation policies, DOI `10.7265/a98x-0f50`) | both hemispheres joined on date: `15,908` rows, `1978-10-26` to `2026-11-21`, every second day until `1987-08-20`, one 42-day gap ending `1988-01-13`; source file paths dropped | `178/184` killed (`96.74%`) |

No natural anomaly label is claimed (`controlled_injection`); the three groups come from different producers and share no generating system with an integrated group. Sampling is complete files, not subsets.

**6. Counts (machine-derived).** Category participations `207` (was `204`); remaining deficits `39` (was `42`): `C3` 33/40 (7, was 10); other categories unchanged (`C1` 52/36, `C2a` 23/30, `C2b` 22/30, `C4` 23/28, `C5` 31/36, `C6` 23/30). `196` independent groups, `196` producers, `61` curators, `113` domains, `101` schema families; largest schema family `32.65%` (was `33.16%`); C4 business-process execution `34.78%` and C5 timetable network `38.71%` unchanged. Effective groups `117.4083` (design effect `0.2`) and `106.9741` (`0.5`). Catalog: `301` distinct source families (`279` open, `22` research_only).

**7. Verification.** Focused mutation at the L3 threshold (`95%`) on the changed builders, after a first run (`85.2%` on the ECB view, `78.8%` on the sea-ice parser) led to removing redundant read arguments and adding tests for unreadable cells and the header rows; the survivors are not approved: the `index=None` mutant of each builder (pandas-equivalent), `dtype`, `errors` and `header`/`names` mutants of the readers that the fixtures cannot distinguish.  In the conda environment the full `research/tests` suite passes; readiness (`experiment_ready` for the three views), target-framework and stratum-gap reports were regenerated; each new snapshot verified with no mismatch and each rebuilt view digest equals the registered one. Mutation runs use `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` scoped to the single `mutmut` process: `mutmut` 3.8 forks without a start-method option, so no safer in-tool strategy exists; the variable disables a macOS safety check and is not evidence that arbitrary fork-after-initialisation is safe. No detector experiment ran under the active freeze; T424 is not authorised; certification stays pending. The manuscript and slides do not cite interim acquisition counts and are unchanged (`no-change` outcome recorded).


## Update 28 — Wave 28 batch A (+10 groups: C3 +1, C2a +5, C2b +4)

**1. Scope.** First internal batch of the final acquisition campaign. Snapshot `2026-11-23`; one builder per source in the canonical conda environment; no historical view rebuilt (all 10 new digests were recomputed after the last code change and match the manifest).

**2. New groups.**

| Group (`view`) | Cat. | Producer and licence evidence | Slice and privacy facts |
|---|---|---|---|
| `nasa_omni_near_earth_solar_wind` (`nasa_omni_solar_wind`) | C3 | NASA SPDF OMNI2; open distribution, acknowledgement requested (`omni2.text`) | 15 complete years 2010-2024, `131,496` hourly rows, fill values masked (`246` empty hours); Kp, Dst and sunspot columns dropped (other institutions) |
| `sffd_fire_incidents` | C2a | San Francisco Fire Department via DataSF; ODC PDDL (portal metadata) | calendar year 2023 window, `37,906` exposure rows; addresses and call numbers dropped, incident number hashed |
| `colorado_regulated_storage_tanks` (`colorado_storage_tanks`) | C2a | Colorado Division of Oil and Public Safety; Public Domain (portal metadata) | complete registry, `52,111` tank rows; names and addresses dropped, facility id hashed |
| `colorado_dam_safety_registry` (`colorado_dam_safety`) | C2a | Colorado Division of Water Resources; Public Domain | complete registry, `2,737` dams; names, coordinates and staff names dropped |
| `wa_ev_population` | C2a | Washington Department of Licensing; ODbL | identifier-ordered prefix of `30,000` of `304,258` vehicles (possible registration-order bias); VIN prefix and location fields dropped |
| `tx_hhsc_child_care_operations` (`tx_hhsc_child_care`) | C2a | Texas HHSC Child Care Regulation; CC0 1.0 (portal metadata) | complete register, `14,966` operations; names, addresses, contacts dropped, id hashed |
| `austin_surface_water_quality` (`austin_water_quality`) | C2b | City of Austin Watershed Protection; Public Domain | calendar year 2023 window, `22,887` laboratory results with units and qualifiers |
| `wa_ecology_ghg_reports` (`wa_ghg_reporting`) | C2b | Washington Department of Ecology; Public Domain | complete export, `2,521` facility-year reports in tonnes CO2e |
| `sfo_passenger_statistics` (`sfo_air_traffic`) | C2b | San Francisco International Airport via DataSF; ODC PDDL | complete monthly series, `40,803` rows, aggregates only |
| `tx_hotel_occupancy_tax_revenue` (`tx_hotel_occupancy_tax`) | C2b | Texas Comptroller of Public Accounts; Public Domain | complete export, `2,395` government-year rows, aggregates only |

Columns more than 50 percent empty are dropped from the C2a views (the convention of the Paris trees view). Two San Francisco departments (Fire, Airport) and two Texas agencies (HHSC, Comptroller) publish through one portal each; they are separate producers and generating systems, and the portal is recorded as curator. No natural anomaly label is claimed (`controlled_injection`).

**3. Counts (machine-derived).** Independent groups `206` (was `196`); `C2a` 28/30 (2 remaining), `C2b` 26/30 (4), `C3` 34/40 (6), `C4` 23/28 (5), `C5` 31/36 (5), `C6` 23/30 (7), `C1` 52/36; remaining deficit `29` (was `39`). Effective groups `127.4083` (design effect `0.2`) and `116.9741` (`0.5`); largest schema-family share `31.07%`.

**4. Verification.** Full `research/tests` run in the conda environment: no failure. Ruff check and format pass. Focused mutation (L3, `95%`) on the new code: `omni_view` `98.2%`, `_build_omni` `96.0%`, `socrata_table` `98.1%`, `_build_socrata` `98.7%`; the survivors are not approved. A first run (`78.7%`, `90.7%`) led to boundary, day-of-year, `NA`-string and leading-zero tests and to removing pandas-equivalent arguments. The Socrata builders are one spec-driven function (`SOCRATA_TABLES`) whose `columns` list also refuses an export with a changed schema.

**5. Next within Wave 28.** Vetted but not yet integrated: French BAAC road-accident tables (C5, Licence Ouverte), MITRE ATT&CK STIX bundle (C6), Seattle Fire 911 calls (C4, Public Domain). No detector experiment ran; the freeze and T424 status are unchanged; the manuscript and slides cite no interim counts (`no-change`).
