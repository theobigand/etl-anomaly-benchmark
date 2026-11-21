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
