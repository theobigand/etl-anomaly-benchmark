# Reusable anomaly protocols by structure (T434-T437)

Status: specification only. No injection was run and no detector was benchmarked. Protocol
definitions are machine-readable in `verification/evidence/dataset_registry_v2/anomaly_protocols.json`.

Rules for every protocol:

- Injected anomalies are controlled faults in real data. They are never described as natural
  anomalies. Natural labels exist only where a source publishes them (SKAB, NAB), and none of the
  newly acquired sources does.
- Properties that the source already has (optional fields, natural orphans, missing values, deleted
  references, sampling-induced missing references) are a baseline measured before injection and
  excluded from labels.
- Injection preserves unaffected data byte for byte and records what changed (record or window,
  field or path, original value, fault, severity).
- A fault is valid only if its precondition holds for the dataset.
- Severity grid, injection positions and seeds are fixed before any detector sees the data, and are
  independent of any detector. Positions are drawn uniformly over the allowed region.
- The unit of statistical inference is the independent source group, never a seed, fault variant,
  table or sample.

## Protocols

| Id | Structure | Detection unit | Mechanisms | Preconditions |
|---|---|---|---|---|
| P-TAB | flat and transactional tables | row | univariate and multivariate outliers, invalid category codes, missing values, duplicate rows, cross-field violations, abnormal entity behaviour | row-local values; entity behaviour needs a repeated entity key and events (see T437) |
| P-TS | time series | time window | point, contextual and collective anomalies, level shift, gradual drift, seasonal deviation, missing interval, delayed arrival, prevalence change | a regular or documented time index; contextual and seasonal faults need enough history |
| P-SEQ | logs and event sequences | event sequence | order violation, missing event, unexpected sequence, rare pattern, duplicate event, abnormal transition | event order and type; gap and delay faults need real timestamps (not available in the Loghub samples) |
| P-REL | relational | relationship | referential violation, invalid relationship, broken entity dependency, inconsistent aggregate, duplicate entity, relationship anomaly | complete keys and a measured foreign-key baseline |
| P-NEST | nested | nested path | missing required field, invalid nested type, structural inconsistency, unexpected array or object, broken hierarchy, schema-evolution violation | records kept unflattened with nested objects and arrays |

## Detection unit and matching

A prediction matches ground truth when it names the same unit: row index (P-TAB), a window that
overlaps the injected interval by at least half of the shorter of the two (P-TS), a sequence id
(P-SEQ), a (table, key, relation) triple (P-REL), a (record, path) pair (P-NEST). A row-level
detector is not applied to relational or nested faults whose unit it cannot output; where it is
applied through a documented lifting (for example, flagging a record that contains the path), the
lifting is part of the method and is reported as such. Local-information faults (outlier, type) are
distinguished from faults that need context (a relation, a sequence history, a pipeline run), and
results are reported separately.

Fairness: operating points are compared at an equal alert budget on a validation partition that
contains no test fault; rule-based, classical, deep and specialised methods get the same
partitions; contaminated reference data is a separate arm. Pipeline-execution ground truth is not
invented from static data: the batch-level pipeline study keeps its own protocol.

## Applicability matrix

Rows are datasets at their highest status; N = natural label, I = controlled injection applicable,
B = natural property to baseline (not a fault), X = not applicable, - = not assessed.

| Dataset | Outlier | Missing | Duplicate | Type or category | Order | Temporal gap | Referential | Nested structure | Natural labels |
|---|---|---|---|---|---|---|---|---|---|
| Melbourne pedestrian (C3) | I | I, B (sensor outages) | I | X | I | I | X | X | no |
| Loghub, 16 systems (C4) | I (rare events) | I (missing event) | I | X | I | X (no real timestamps) | X | X | no in the 2k samples |
| OpenAlex (C5) | I | I | I | I | X | X | I, B (references leave the sample) | X | no |
| OpenAlex works (C6) | I | I, B (optional) | I | I | X | X | X | I | no |
| openFDA events (C6) | I | I, B (optional) | I | I, B (type variation) | X | X | X | I | no |
| Stack Exchange, 10 sites (C5) | I | I | I | I | I | I | I, B (5 to 29 percent of votes point to deleted posts) | X | no (privacy review pending) |
| Open Food Facts (C6) | I | I, B | I | I, B | X | X | X | I | no (privacy review pending) |
| Monash families (C3) | I | I, B (missing up to 40 percent) | I | X | I | I, B | X | X | no (upstream terms pending) |
| Online Retail (C2, transactional) | I | I | I | I | I | I | X | X | no |

## Detector bias controls

Fault generators do not look at detector scores. Severity is defined in the data domain (percent
change, number of fields, number of records), not in detector units. Each mechanism uses several
generators where one is likely to favour a detector family (for example, both a shifted mean and a
variance change for outliers). Injection results that depend on one generator are reported as
conditional on it.


## Realism mapping: which failure each fault stands for

A mechanically valid fault is not automatically realistic. Each fault is tied to a plausible failure
and to its class: S = ordinary statistical anomaly (a value is unusual but the pipeline is correct),
T = ETL transformation failure (a step changes data wrongly), B = business-rule violation, O =
pipeline-operation failure (a run is late, partial or repeated). A fault is only claimed for the class
it is mapped to.

| Fault | Plausible failure mechanism | Class |
|---|---|---|
| Value scaled by a factor (P-TAB, P-TS) | unit or currency conversion applied twice, thousands/millions mix-up | T |
| Unusual amount without a rule being broken | a genuine large purchase | S |
| Duplicate rows or events | a retried load or a replayed batch without idempotency | O |
| Missing rows, events or intervals | a partial load, a dropped partition, a failed extract | O |
| Delayed arrival, level shift, drift | late upstream data, a sensor or source recalibration, a changed upstream definition | O, T |
| Invalid category code | an enumeration changed upstream and a mapping is stale | T |
| Cross-field violation (date before order) | a join on the wrong key or a timezone error | T, B |
| Event order swapped or event dropped (P-SEQ) | out-of-order delivery or a lossy collector | O |
| Foreign key to an absent parent (P-REL) | a parent table loaded late or filtered, an orphaning delete | O, T |
| Duplicate entity with a new key | a merge or deduplication failure | T |
| Missing required nested field (P-NEST) | a schema change or a mapping that drops a path | T |
| Nested type change | a serialisation or schema-evolution error | T |

Not covered because static data cannot support the ground truth: late publication timing, partial
runs of a real pipeline, and operational metadata (run ids, row counts at load). The batch-level
pipeline study keeps those under its own protocol. Controlled injections are never described as
natural anomalies.

## Injection realism by anomaly family (review, 2026-11-21)

Severity ranges are proposed design ranges, not measured failure rates; they are fixed before any
detector runs. No range here is evidence about real pipeline failure frequency.

| Family | Failure mechanism | Applicable structures and needed source information | Proposed severity range | Ground truth | Detector-specific bias to control | Interaction with natural irregularities | Limits on interpretation |
|---|---|---|---|---|---|---|---|
| Scale or unit error | conversion applied twice, thousands/millions mix-up | numeric amount columns with a known unit (ledger amounts, award values, durations) | factors 10, 100, 1000 and 0.1 on 0.1 to 5 percent of rows | row ids changed | a single factor favours distance detectors; use several factors and a cell fraction grid | credit notes and zero values are natural extremes: exclude rows already negative or zero | the factor is a design choice, not a measured error |
| Duplicates | retried load, replay without idempotency | any table with a row id or a natural key; for OCDS one row per process, so a repeat is clean | 0.1 to 5 percent appended copies | positions of copies | rule detectors catch exact duplicates trivially; add near-duplicates with a changed non-key field | NHSBSA multi-line payments share numbers legitimately: duplicate on the full row, not on the number | exact duplicates are the easy case |
| Missing rows, events or intervals | partial load, lost partition | time-indexed or ordered data; X for sources that are censored views (UK ledgers) | drop 1 to 20 percent of a window or whole intervals | removed units recorded | volume detectors win by construction; keep the unit-level truth separate from volume truth | MHRA gaps between returns are not missing data | not applicable where the source is already censored |
| Level shift, drift, delay | upstream recalibration, changed definition, late data | regular time index | shift 1 to 5 standard deviations, windows of 1 to 10 percent of the series | series and window | window length changes difficulty more than size; vary both | natural seasonality in pedestrian counts must be baselined before shifting | no natural drift labels |
| Invalid category or code | stale mapping after an upstream enumeration change | categorical columns with a closed vocabulary (expense type, rideable type) | 0.1 to 5 percent of cells | cells | frequency detectors favour rare replacement codes: also replace with a frequent wrong code | rare valid codes exist naturally | vocabularies are inferred, not published |
| Event order and drops | out-of-order delivery, lossy collector | sequences with an order that has meaning (log event ids); not trips | one swap or drop per sequence, or 1 to 10 percent of sequences | (sequence, position) | sequence models see order only if sequences are long enough: Loghub samples are single 2000-event streams | repeated events are normal in logs | no real session boundaries in the samples |
| Broken reference | late parent table, filtered or deleted parent, orphaning delete | tables with native keys: OpenAlex, Stack Exchange, OCDS awards and contracts | 0.1 to 5 percent of references | (table, key, relation) | join-based rules detect all of them; a learned detector must be given join context to be fairly compared | natural orphans (deleted posts, 7 Zambia contracts, sampling-induced `referenced_works`) are a baseline and never selected | OpenAlex references to works outside the sample are sampling artefacts |
| Missing required nested field, type change | schema change or mapping that drops a path; serialisation error | nested records with a field present in nearly all records (nested paths with presence above 0.95) | 0.1 to 5 percent of records, one path | (record, path) | schema validators detect all of them; statistical detectors need path-level features | optional fields are natural variation: only paths that are almost always present are eligible | required-ness is inferred from presence, not from a published schema |
| Distribution shift, volume change | upstream population or batch size change | any table with a time order | shift of a column mean or a batch size change over a window | window | batch statistics detect volume shifts directly | seasonality and business cycles | not the same as concept drift in labels |

Cross-cutting rules: injections draw rows only from the test partition (checked by
`fault_protocols.conformance`); the reference partition is never touched; the same seed and the same
data give the same truth; a fault whose precondition fails raises instead of silently doing nothing; the
interaction columns above are checked against the natural-property baseline of each dataset before the
injection set is frozen. Reusable mechanisms live in `research/fault_protocols.py` by structure, not
per dataset.
