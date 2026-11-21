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

## Result (2026-11-21)

Experiment-ready: Melbourne pedestrian counts (C3), 16 Loghub systems (C4, one curator), OpenAlex
(C5 and C6, one source), openFDA adverse-event reports (C6). Details per dataset:
`verification/evidence/dataset_registry_v2/readiness.json`.

Stopped before the end, on purpose:

| Dataset | Stops at | Reason |
|---|---|---|
| Stack Exchange, 10 sites | structurally_valid | user text and display names not yet removed (privacy unreviewed), no view |
| Open Food Facts | structurally_valid | contributor names present, no view |
| 15 Monash families | acquired | upstream terms not read |
| Monash sunspot | rights_verified blocked | CC BY-NC 4.0 upstream: allowed as `research_only`, not yet assessed further |
| Vehicle trips, Bitcoin | rejected | upstream terms unclear |

Limits of the four ready datasets are part of their record: the openFDA sample covers two receipt
dates, so its split is by hash of the report id and not chronological; the OpenAlex sample is one
snapshot of 1000 works; Loghub samples have 2000 lines and no native labels; the pedestrian series
come from one city.
