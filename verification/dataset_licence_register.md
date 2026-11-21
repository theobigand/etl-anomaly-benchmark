# Dataset licence register (tasks T434–T437, issue 131)

Classes: `open` (identified open licence), `research_only` (source-authoritative terms permit academic
research with stated conditions), `unclear` (not established), `restricted` (use prohibited or
authorisation not obtained). Only `open` and `research_only` sources enter experimental runs. A
repository's software licence is never taken as the licence of its data. Raw `research_only` data is
never committed; sources are acquired from a pinned URL and checksum.

Evidence date: 2026-11-21. Counts: `python research/dataset_catalog.py gap`.

## Accepted

| Source | Stratum | Class | Authoritative text | Sources counted |
|---|---|---|---|---|
| Loghub 2k samples, 16 systems (pinned commit `dd61d09`) | C4 | research_only | logpai/loghub README, "License": "freely available for research or academic work"; cite the Loghub paper; same wording on Zenodo 3227177 and 8275861 | 16 |

Manifest with checksums: `verification/evidence/dataset_registry_v2/loghub_manifest.json`.
Limitations: redistribution is not stated, so raw files stay in the gitignored `data/loghub/`; logs are
described as unsanitised (no personal-data review done); upstream terms of the individual logs are not
stated; the sixteen systems are independent systems but come from one curator, so corpus-level
dependence is a limit of any claim over C4. Timestamps span under a week in 15 of 16 samples (some
carry no year), so these are ordered event sequences, not time-verified series: they do not count in
C3. Loghub-2.0 (large corpora, Zenodo 8275861) is not fetched.

## Not accepted yet

| Source | Stratum | Class | Reason |
|---|---|---|---|
| CTU Prague relational repository (148 databases) | C5 | unclear | the repository "About" page states no licence or terms; third-party listings disagree (CC BY-SA 4.0 on one, "research use" on another); each database needs its upstream permission, or a written answer from the maintainers |
| RelBench `rel-hm`, `rel-avito` | C5 | research_only candidate | upstream Kaggle terms, non-commercial academic use; the user accepts the competition terms; not yet read at source |
| RelBench `rel-amazon`, `rel-stack`, `rel-f1`, `rel-event`, `rel-trial` | C5 | unclear | no per-dataset licence text found; upstream terms (Amazon review dump, Stack Exchange, Ergast, Hangtime, AACT) not yet read; `rel-stack` has personal data |
| Monash forecasting archive | C3 | unclear | a CC BY label on one mirror and none on another; each Zenodo record must be read; also overlaps with sources already counted |
| GH Archive derivatives (open-data-on-github, CDLA-Permissive-2.0; open-index, ODC-By) | C6 | unclear | the second is a flattened derivative (not nested); upstream GH Archive terms not read |
| Wikidata, openFDA, Yelp | C6 | unclear | no terms read; Yelp is research-restricted by its own terms and is not accepted without them |

C5 (relational) and C6 (nested) remain at 0 sources. No flat table is converted to JSON, and several
tables of one database count as one source.

## Open questions for the thesis claims

1. The category minimum (15 sources) is met for C1 to C4 only. C5 and C6 cannot be claimed.
2. C1 (92) and C2 (42) exceed their targets by a coarse schema criterion; T437 is still open.
3. C4 rests on one curator; state it with the claim.

## Update 2026-11-21 (acquisition wave 3)

Accepted after verification at the publisher: Monash records (Zenodo `cc-by-4.0`, compiler only),
openFDA (CC0, open.fda.gov/terms), Stack Exchange dump (CC BY-SA, Stack Overflow public network terms),
Open Food Facts (ODbL, not yet collected). Details, stages and rejections:
`verification/dataset_acquisition_report.md`. OpenAlex: not verified, the API needs a key tied to an
e-mail address that was not provided. The "Not accepted yet" table above still holds for CTU and RelBench.

## Update 2026-11-21 (OCDS publishers, bike-share)

| Source | Class | Evidence at the publisher | Notes |
|---|---|---|---|
| Georgia, State Procurement Agency (OCDS) | open (CC0) | the Agency's own Publication Policy page states that the data is published as Open Data under CC0 in OCDS 1.1; read in the Wayback Machine copy of 2023-02-28 because `odapi.spa.ge` does not present a verifiable TLS chain (certificate checking was not disabled); the Terms of Service allow content to be exposed to third parties without restriction and forbid circumventing API limits | the registry export ends in 2019; the policy says simplified procurements and some dates are absent; ocid prefix of the acquired file matches the registry's prefix for this publisher |
| Zambia Public Procurement Authority (OCDS) | open (ODC-PDDL) | `zppa.org.zm/ocds-license` (read live) states ODC-PDDL; the Publication Policy limits personal data to what the Public Procurement Act authorises and excludes security and defence contracts | the OCP registry's metadata says CC BY 4.0: a curator-versus-publisher discrepancy, both permit this use; the publisher's statement governs |
| Netherlands (TenderNed / Ministry of Economic Affairs, OCDS) | unclear | TenderNed's dataset page says that announcements are public and offers the datasets, and its terms of use state no reuse licence; the registry's CC0 is not found at the publisher; the registry export is a transformation of TenderNed data | public availability is not permission; kept out of counts |
| Capital Bikeshare | research_only | Data License Agreement read live: any lawful purpose, analysis allowed; the data may not be hosted or published as a stand-alone dataset; analyses may be published for non-commercial purposes; no correlation with rider identities | raw files and views stay local |
| Citi Bike (Jersey City files) | research_only | the same agreement text on `citibikenyc.com/data-sharing-policy` | same operator and schema as Capital Bikeshare |
| USAspending | open by law, not acquired | 17 U.S.C. 105 (public domain); Treasury licence notice not retrievable | the archive host's TLS chain does not verify with the Python trust store; not disabled |
