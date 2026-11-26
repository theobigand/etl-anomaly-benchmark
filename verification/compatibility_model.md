# Compatibility model (issue #134)

Status: generated from the registry, no detector run, no fault injected, freeze unaffected.
Source: `research/compatibility_model.py`; output:
`verification/evidence/dataset_registry_v2/compatibility_model.json`.

```
cd research && python compatibility_model.py --output ../verification/evidence/dataset_registry_v2/compatibility_model.json
```

## What it states

One table over category x protocol x unit x operator x detector x metric, computed only from the
registry (`readiness_facts.json`, `readiness.json`, `anomaly_protocols.json`,
`batch_eligibility.json`) and `registry_units`. The protocol belongs to a participation (a group in
a category), as in the utilization ledger. No dataset, view or group name occurs in the module: a
test scans its string literals against the 275 registry facts, so no source has a privileged path,
including the historically prominent UCI sources, whose archived evidence is untouched.

## Unit labels

| Unit | Kind | Status | Basis |
|---|---|---|---|
| `row` (P-TAB) | natural | protocol defined | a row of a source table |
| `time_window` (P-TS) | logical | protocol defined | a window cut from an ordered series |
| `event_sequence` (P-SEQ) | natural | protocol defined | a case or trace of an event log |
| `relationship` (P-REL) | natural | protocol defined | a declared foreign-key relation |
| `nested_path` (P-NEST) | natural | protocol defined | a (record, path) pair of a nested document |
| `temporal_batch` | replayed | registered | timestamped records replayed in time order as loads |
| `observed_load` | natural | provisional | a load delivered with its own identifier and time (no registry group maps to it) |
| `event_window` | logical | provisional | consecutive events cut into windows |
| `relational_load` | logical | provisional | consecutive child rows in file order |
| `document_batch` | logical | provisional | consecutive documents in source order |

`natural` means the unit exists in the data as delivered, `replayed` that stored records carrying
their own times are replayed in time order, `logical` that the protocol cuts the unit from an order
it imposes. Every new unit is provisional until the protocol amendment (S03, issues #152 to #154);
a provisional unit is listed but never runnable and never given detectors.

## Participations by category, protocol and unit (groups, of which runnable)

| Category | Protocol | Own unit | `temporal_batch` | Provisional unit |
|---|---|---:|---:|---|
| C1 | P-TAB | 52, 0 | 52, 1 | none |
| C2a | P-TAB | 30, 0 | 30, 6 | none |
| C2b | P-TAB | 30, 0 | 30, 8 | none |
| C3 | P-TS | 40, 0 | 40, 21 | none |
| C4 | P-SEQ | 25, 0 | 25, 3 | `event_window` 25, 0 |
| C4 | P-TAB | 3, 0 | 3, 2 | none |
| C5 | P-REL | 36, 0 | 36, 6 | `relational_load` 36, 0 |
| C6 | P-NEST | 30, 0 | none (no table unit) | `document_batch` 30, 0 |

The 246 participations match the ledger. Runnable participations total 47 (one per executable
group). The own unit of each protocol is never runnable: no registry-driven unit-level runner
exists (issues #135 to #139).

Operators and detectors: the unit-level cells carry the protocol's mechanisms and no detector;
`temporal_batch` carries the eight batch operators and the 16 batch detectors of
`pipeline-batch-v1`, with recall, false-alert rate, ROC-AUC and average precision as metrics.

## Verification

`research/tests/test_compatibility_model.py` (11 tests): labels and statuses, provisional units are
never executable, per-participation units and matrix counts, refusal of a participation without a
fact or a protocol without a definition, determinism, no registry name in the module, and the
committed model equals a rebuild from the committed registry. Focused mutation (L2, policy 90
percent): 197 of 200 killed (98.5 percent); the 3 survivors are a parser description and two
file-name case mutants that survive only on a case-insensitive volume.

Not checked: execution on real data (frozen), the S03 decision on the provisional units.
