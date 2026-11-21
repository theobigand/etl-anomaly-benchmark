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
