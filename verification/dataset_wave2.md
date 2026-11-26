# Second acquisition wave: protocol (strata not covered by the first pool)

Written before the selection is run. The first pool (`dataset_pool.md`, 152 tables) is unchanged
and its archived manifest is not rewritten; this wave has its own selection and manifest under
`verification/evidence/dataset_registry_v2/`.

## Why

The first pool excluded time series, sequential and transactional tables because its labelled and
typed protocols could not use them, and it holds no log, relational or nested sources. The
batch-level pipeline study (`pipeline_batch_faults.md`) needs real timestamped tables and
transactional and categorical sources, and the design review set structural strata with
independent-source targets (`docs/thesis-remediation/DESIGN_DECISION_2026-11-21.md`).

## Rule

A UCI table enters the wave if all hold: its own page states CC BY 4.0 or CC0 1.0 (the rule of the
first pool, read from the page, not from the catalogue API); it is not in the first pool; 300 to
3,000,000 rows and 3 to 300 features; it is not image or text; a download URL exists; and it serves
an uncovered stratum: a time-series characteristic, a sequential characteristic, a business-domain
table of at least 500 rows (transactional), or categorical-only features. No label is required:
the batch study injects its own faults, and ground truth is by construction.

## What a table is then used for

Each fetched table is pinned by checksum and screened for a real time column (`time_scan`). Only a
table with a verified single-series time variable can be replayed as batches; others serve the
row-level fault protocols. Eligibility for each protocol is decided by that protocol's rule, never
after seeing results. Independence follows source families: tables from one producer are one
source.

## Not in this wave

Log, relational and nested sources are not on UCI. Their candidates (for example system logs,
relational repositories, JSON event archives) have terms that must be read from the source before
any download; none is integrated here unless its licence is verified. See T425 and T426 in
`docs/thesis-remediation/13-pipeline-level-study.md`.
