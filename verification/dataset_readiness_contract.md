# Dataset readiness contract (T434-T437, issue 131)

A dataset holds the highest status whose checks, and every earlier status's checks, pass
(`research/readiness.py`, `python research/readiness.py`). The checks read recorded facts; the number
of tests or scripts run is not a criterion. `experiment_ready` means a protocol can use the data. It
does not mean an experiment was run, and none was.

| Status | Passes when |
|---|---|
| discovered | the source and an identifier are recorded |
| rights_verified | licence class is `open` or `research_only`, and either the publisher is the original producer or the original publisher's terms were read (`upstream_status: verified`) |
| acquired | the stored files match the checksums of the acquisition manifest |
| structurally_valid | the structural validator for the stratum passed and the entry was not judged ineligible (ordering and timestamps for C3 and C4; key and foreign-key baseline for C5; nesting, arrays and optional fields for C6) |
| scientifically_eligible | an independent source group is named; personal-data handling is `not_needed` or `handled`; the expected source properties are recorded as a baseline; the anomaly origin is declared (natural or controlled injection); the table has the minimum number of detection units |
| protocol_ready | a protocol id, a detection unit and an evaluation partition scheme are defined |
| experiment_ready | a checksummed experimental view exists with recorded preprocessing, and no personal field remains in it |

Views are built by `python research/experimental_views.py` into the gitignored `data/experimental/`;
their checksums are in `experimental_views.json`. Pseudonyms are salted hashes that keep joins
working. They do not make the data anonymous, and the data protection obligations of the original
data remain.

## Result (2026-11-21, second update)

Experiment-ready, by independent source group: transactional (C2b) two UK public ledgers (MHRA,
NHSBSA); time series (C3) Melbourne pedestrian counts; logs (C4) the Loghub collection (one curator);
relational (C5) OpenAlex and Stack Exchange (10 sites, one group); nested (C6) OpenAlex, openFDA events
and Open Food Facts. Per dataset: `verification/evidence/dataset_registry_v2/readiness.json`.

Not ready, and why:

| Dataset | Stops at | Reason |
|---|---|---|
| 13 Monash families | acquired | upstream terms not read or unresolved (AEMO, FRED, Saugeen, US births) |
| Monash sunspot | not assessed | CC BY-NC 4.0 upstream, no protocol facts declared |
| Charity Commission ledger | rejected | 45 usable rows, below the minimum number of detection units |
| NICE, Ofsted ledgers | deferred | spreadsheets saved as CSV; banner layout |
| Tate ledger | rejected | the host's TLS certificate chain does not verify; checking was not disabled |
| Instacart 2017 | not downloaded | the dataset terms state that access is not a licence grant |
| NYC TLC trip records | discovered | official open data without use restrictions by city law, but the agency terms page refused automated access and was not read; not collected |
| Open Contracting registry | discovered | licence is per publication; none read yet |
| Vehicle trips, Bitcoin | rejected | upstream terms unclear |

Limits that stay on the ready datasets: the openFDA sample covers two receipt dates; the OpenAlex
sample is one snapshot of 1000 works; Loghub samples have 2000 lines and one curator; the pedestrian
series are from one city; the UK ledgers are two organisations that publish on the same government
template (their ledger systems are treated as independent but the template is shared); MHRA returns are
not contiguous months; Stack Exchange and Open Food Facts views are derived databases under share-alike
licences, so they stay local.
