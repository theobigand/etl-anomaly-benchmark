# Structural dry run of the unit-level protocols (#135, #137, #138, #139)

`research/unit_dry_run.py` checks, for every registry participation, that the view of a source has the structure the
experimental unit of its protocol needs, and records a source-specific reason when it does not. The result is
[`structural_dry_run.json`](../../verification/evidence/dataset_registry_v2/structural_dry_run.json). Regenerate it with
`python research/unit_dry_run.py --output verification/evidence/dataset_registry_v2/structural_dry_run.json` (about 10
seconds; the views are local and not tracked).

## What it is and is not

- It is a structural verdict: files match the digests of the view manifest, a table has the columns and the row floor
  the protocol needs, a log has an order and an event type, documents keep nested paths, a relational view declares
  foreign keys whose tables and columns exist.
- It is not an execution. It fits, scores, injects and selects nothing, computes no metric, and returns no cell value.
- It does not change the utilization ledger. A group is *executable* only when an approved execution path with a
  detector runner accepts it; none exists for the unit-level protocols, and the units other than the registered
  temporal batch stay provisional (S03, #152 to #154). Executed, evaluated, included and excluded remain zero.

## Access and exposure

The owner authorized read-only structural dry runs on real views on 2026-11-27 within the limits above. The run reads,
per view: the whole file once to compute its SHA-256 (compared with the manifest, never interpreted), the header and
at most 5000 leading rows of each CSV table to learn column kinds, and at most 5000 leading lines of the first
JSON-lines file to collect structural paths. Columns whose name belongs to the ground-truth vocabulary (the redaction
vocabulary of `obs_redaction`) are never read. The views carry no label columns in any case: ground truth of the
unit-level protocols is created by controlled injection, which has not been run.

Exposure in the registry (`linked_sets.json`, `exposed_groups`; pilot design section 6) means that a detector or an
injection touched the group. No detector or injection was involved, so no group changed exposure status, the five
exposed groups are unchanged, and no held-out outcome could be seen. The same record is stored in the output
(`access`).

## Results (2026-11-27, 246 participations of 235 groups)

| Category | Protocol | Participations | Structurally pass | Do not pass |
|---|---|---:|---:|---:|
| C1 | P-TAB | 52 | 52 | 0 |
| C2a | P-TAB | 30 | 30 | 0 |
| C2b | P-TAB | 30 | 30 | 0 |
| C3 | P-TS | 40 | 37 | 3 |
| C4 | P-SEQ | 28 | 26 | 2 |
| C5 | P-REL | 36 | 31 | 5 |
| C6 | P-NEST | 30 | 29 | 1 |

A participation is a (group, category) pair; nine groups appear in several categories under different protocols, and
each is judged under its own. Passing is not executability and not scientific suitability.

The 11 participations that do not pass, with the reason recorded for each:

- **C3, 3 groups** (`pnnl_epri_bess`, `telecom_operator_kpis`, `vif_aegis`): the time axis is a numeric elapsed time, and the
  adapter recognizes only parseable instants. This is an adapter limitation, not a data defect.
- **C4, 2 groups** (`fermi_blazar_flares`, `github_actions_workflows`): the order is a numeric epoch or a non-monotonic
  integer; the same limitation.
- **C5, 5 groups** (`georgia_procurement`, `openalex`, `paleobiology_database`, `stackexchange`, `zambia_procurement`):
  the view manifest declares no foreign key, so the relational unit has no relationship to build. The complete
  foreign-key baseline that P-REL needs is missing for these sources; building it is a data task, not a runner task.
- **C6, 1 group** (`openalex`): the nested view holds no JSON-lines document file.

## Why C6 had no executable group

C6 was not blocked by the data. Its two candidate units, `nested_path` (protocol-defined) and `document_batch`
(provisional), have no runner and no detector profile in the registry, and an executable group needs an approved path
that accepts it. The structural dry run shows 29 of 30 C6 participations have documents that keep nested paths, so the
missing piece is the approved unit and the runner (#139, #154), not the sources.

## Per issue

| Issue | Covered here | Still open |
|---|---|---|
| #135 | a dry run with a reason for every P-TAB and P-TS participation (C1, C2a, C2b, C3); no result produced or stamped | the dry run does not extend the ledger count; typed-injection execution waits for the freeze and the unit decisions |
| #137 | a structural dry run of every C4 participation | unit definition, ground truth and metrics documented as provisional; runnable on synthetic fixtures with fault operators; approval requirement in S03 |
| #138 | a structural dry run of every C5 participation, with a reason where the foreign-key baseline is missing | provisional relational unit document and reconciliation with T425 (#131) |
| #139 | a structural dry run of every C6 participation | provisional unit document, path-aware profile and operators on synthetic fixtures |
