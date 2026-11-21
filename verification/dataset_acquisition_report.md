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
