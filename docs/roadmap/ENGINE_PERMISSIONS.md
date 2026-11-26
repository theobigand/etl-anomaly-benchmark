# Experimental engine: what is permitted (#135 to #139, #154)

Read on 2026-11-26 from the issue texts of #135 to #139 and #154, the authorization gates of
[ROADMAP.md](ROADMAP.md) ("The experiment freeze is active. Engineering work uses synthetic fixtures and metadata
only") and the registry evidence. This is an assessment of existing rules, not a new rule and not an authorization.

## Permission matrix

| # | Activity | Status | Source of the rule |
|---|---|---|---|
| 1 | Architecture design | Permitted | ROADMAP gates list only approval of unit definitions as gated, not design |
| 2 | Interface definition | Permitted | same |
| 3 | Runner implementation | Permitted when it needs no approved unit; the unit definition it implements stays provisional | #137 to #139: "provisional definitions documented before use" |
| 4 | Synthetic fixture creation | Permitted | #137: "synthetic fixtures for tests"; #135: "dry-run adapters on synthetic fixtures" |
| 5 | Unit tests on synthetic data | Permitted | same |
| 6 | Integration tests on synthetic data | Permitted | ROADMAP: "engineering work uses synthetic fixtures and metadata only" |
| 7 | Metadata validation | Permitted | #135: "and metadata only" |
| 8 | Structural compatibility validation | Permitted (it is the compatibility model, #134, closed) | #134 |
| 9 | Adapter dry runs | Permitted on synthetic fixtures and metadata; a dry run that loads a benchmark view is not stated by any issue and needs the owner's explicit wording | #135 scope; #137 and #138 ask for "dry-run on every C4 / C5 group" without saying whether the group's data may be read |
| 10 | Access to actual benchmark data | Not authorized by any issue for this work | ROADMAP gates |
| 11 | Detector fitting | Forbidden while the freeze is active | #135 non-goal: "no detector evaluation on benchmark data while the freeze is active" |
| 12 | Benchmark execution | Forbidden: owner authorization | ROADMAP gates |
| 13 | Pilot execution | Forbidden: owner authorization, separate from approving the design (#153) | ROADMAP gates; `verification/pilot_statistical_design.md` section 7 |
| 14 | Scientific evaluation | Forbidden | same |
| 15 | Inclusion in scientific conclusions | Forbidden before approval of the unit definition (S03 / #154) | #137 to #139 non-goals |

Row 9 is the one open interpretation. The safe reading, used for any work started from this document, is that a dry run
works from the registry metadata (columns, types, declared keys, paths, row counts) and from synthetic fixtures, and
that it does not open a benchmark view. If the owner wants dry runs that read the real views to prove they can be
turned into units, that is a one-line authorization to record in #135, #137, #138 and #139.

## What each issue still needs

| Issue | Unit | Registry state (compatibility model, 2026-11-26) | Missing | Permitted next work | Approval boundary |
|---|---|---|---|---|---|
| #135 | typed-injection execution for unit-level-compatible groups | P-TAB, P-TS groups resolve to `row` and `time_window` with no unit-level runner | a registry-driven dry-run adapter and per-group reasons | adapter on synthetic fixtures plus metadata verdict per group | none for the dry run; none for results because none are produced |
| #136 | numeric and temporal batch coverage | 47 groups executable at `temporal_batch`; the other groups carry reasons from the audit | executable count reported apart from the 47; precise reasons | report from the existing audit and compatibility model | batch unit is registered; changing it needs S03 |
| #137 | event sequence and event window (C4, P-SEQ) | 25 groups on `event_sequence` and `event_window`, 3 C4 groups on P-TAB; none runnable at those units | provisional definition, ground truth, metrics, operators, fixtures | all of it as provisional; synthetic fixtures | approval of the unit before any scientific use (S03) |
| #138 | relational load (C5, P-REL) | 36 groups on `relationship` and `relational_load`; the registered batch unit runs on 6 | provisional definition; reconcile with T425 in #131 | referential-integrity operator already exists; unit and fixtures | approval before scientific use (S03) |
| #139 | document batch and nested path (C6, P-NEST) | 30 groups on `nested_path` and `document_batch`; none runnable | provisional unit, path-aware profile and operators | all of it as provisional; synthetic nested fixtures | approval before scientific use (S03) |
| #154 | amendments | blocked by #137 to #139 | one dated amendment per unit type | draft only | owner approval is recorded only by the owner |

## Why C6 has no executable group

C6 maps to P-NEST, whose two candidate units are `nested_path` (defined by the protocol, no runner) and `document_batch`
(provisional, no approved definition). Every other category also resolves to the registered `temporal_batch`, which is
the only unit with a profile and a runner (`DETECTOR_UNITS`), so P-NEST is the only protocol without a route to it.
Nested documents are not flattened into a table on purpose (#139 non-goal), so C6 stays at zero executable groups until a
path-aware unit is implemented (#139) and approved (#154). Nothing in the registry privileges a dataset: the model is
read from protocol, audit and unit tables.

## What this changes in the ledger

Nothing. The utilization ledger counts a group as executed, evaluated, included or excluded only on genuine evidence;
dry runs on synthetic fixtures and metadata verdicts produce none, so those counts stay at zero.
