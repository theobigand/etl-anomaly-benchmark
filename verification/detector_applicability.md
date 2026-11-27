# Detector applicability for the five protocol-defined units (#136 to #139, D-13)

Status: 2026-11-27, proposal and synthetic infrastructure. No dataset was read and no detector ran on benchmark data;
the freeze stays active. The machine-readable matrix is
`verification/evidence/dataset_registry_v2/detector_applicability.json` (`research/detector_applicability.py`); the
scoring contract and featurizers are `research/unit_scoring.py`, validated on `unit_runner` fixtures only.

## 1. How to read a cell

Each (detector, unit) cell has a technical state, a scientific state and a combined status.

| Technical | Meaning |
|---|---|
| `existing_adapter` | the detector already takes the unit's representation (a numeric row) |
| `adapter_implemented` | a featurizer makes it run; validated on synthetic fixtures only |
| `requires_implementation` | the detector or its rule does not exist yet |

| Scientific | Meaning |
|---|---|
| `pending_unit_approval` | the S03 amendment of the unit is not recorded (D-13) |
| `pending_representation_approval` | the featurizer is a proposal, not an approved method |
| `inappropriate` | using the detector would answer no meaningful question |

Statuses: `supported_existing_adapter`, `adapter_implemented_pending_approval`, `requires_implementation`,
`scientifically_inappropriate`. No cell is scientifically approved today.

## 2. Matrix summary

Detectors: 3 rules (`zscore`, `iqr`, `great_expectations`), 8 classical models, 6 neural models (the 17 of
`detector_inventory.md`; the temporal `drift` detector is opt-in and excluded), and three unit-specific deterministic rule
baselines that do not exist yet.

| Unit | 17 existing detectors | Unit-specific rule | Notes |
|---|---|---|---|
| P-TAB `row` | supported with the existing adapter (17) | none needed | numeric columns only; categorical codes, missing values and duplicate rows are invisible to the numeric representation |
| P-TS `time_window` | adapter implemented (17): window statistics | none needed | `seasonal_deviation`, `missing_interval`, `delayed_arrival` invisible; `point_outlier`, `contextual_anomaly`, `gradual_drift` limited |
| P-SEQ `event_sequence` | adapter implemented (16); `great_expectations` inappropriate | `sequence_constraints`: requires implementation | z-score and IQR degenerate when training traces have constant counts; the meaningful rule baseline is a sequence constraint rule |
| P-REL `relationship` | adapter implemented (16); `great_expectations` inappropriate | `fk_integrity`: requires implementation | `duplicate_entity` and `inconsistent_aggregate` need parent-child features not in the child-row representation |
| P-NEST `nested_path` | adapter implemented (16); `great_expectations` inappropriate | `schema_path_rules`: requires implementation | nesting is kept: the unit is a (record, path) pair, absent paths are units with `present = 0` |

The batch-level detectors registered for `temporal_batch` (`constraint_rules`, `volume_freshness`,
`distribution_distance`, the PyOD and compact variants and `random`) are not applicable to the unit-level units; they
keep their own protocol and are never pooled with these.

## 3. Deterministic rule baselines

A rule that detects an injected fault perfectly by construction is not invalid. Its interpretation depends on what it
receives and what the comparison claims.

| Case | Verdict |
|---|---|
| `fk_integrity` on `referential_violation`: the rule reads the declared key relation, never the injection | a legitimate deterministic baseline; its perfect recall is a ceiling check of the harness, not evidence of general superiority |
| a learned detector given the feature `reference_present` | oracle-like for key breaks: the feature is the constraint itself (`unit_scoring.REFERENCE_CHECK_NOTE`); excluded from a learned-versus-rule contrast on `referential_violation` |
| a learned detector on child attributes without the reference check | answers whether attributes alone reveal a broken reference, a different question |
| any detector reading the injection log, the truth file or the operator | forbidden; the fixtures and the contract keep truth out of the scoring path |
| a rule contrast on an operator the rule cannot see (`inconsistent_aggregate`) | the meaningful P-REL contrast; the deterministic rule needs a parent-child aggregate rule to compete |

A rule is the rule-based side of a contrast only where it is a meaningful baseline: a statistical rule on a featurized row
or window, or, for sequences, relationships and nested paths, the unit's deterministic constraint rule. A z-score of bigram
counts is reported in the matrix but does not count as the sequence rule baseline.

## 4. Scoring contract (implemented, `unit_scoring.py`)

One numeric row per detection unit, indexed by the unit identifier; a detector fitted on training features returns one
score per unit (higher is more anomalous); the alert set has `k = floor(B x N)` units, the same for every detector, ordered
by score and then by the SHA-256 of the unit identifier; no minimum-one-alert exception; a missing score is an error; recall
at k is capped at `min(1, k / P)`. A synthetic end-to-end path (`synthetic_validation`) fits a detector on a clean fixture,
injects faults into another and reports recall at the budget. Its numbers describe the fixtures, never a detector.

## 5. Potential contrast eligibility

Provenance clusters that are unexposed, meet the structural size floor, are not in the balanced 24-cluster pilot and take
part in a protocol where both sides of the contrast can be run. A structural upper bound only: not verified eligibility, not
mechanism- or size-checked per contrast, not paired observations.

| Contrast | Protocols runnable now | Clusters, registry exposure rule | Clusters, outcome-exposed excluded | After the missing rules exist |
|---|---|---:|---:|---:|
| F1a rule vs classical | P-TAB, P-TS | 85 | 62 | 119 / 95 |
| F1b classical vs neural | all five | 119 | 95 | 119 / 95 |
| F1c rule vs neural | P-TAB, P-TS | 85 | 62 | 119 / 95 |

The pool is 119 clusters under the registry rule and 95 when every outcome-exposed cluster is excluded (provisional
planning rule, D-02 and D-08). With 85 or 62 potential clusters, a family of three is feasible only for sigma-hat of about
0.07 to 0.10 and no confirmatory dependence inflation; with 62 it is infeasible whenever the requirement is above 62 (for
example sigma-hat 0.10, k = 3: 104). These counts are before the P-TAB and P-TS mechanism limits above and before any
paired-outcome loss, so they overstate what a contrast can use.

## 6. Remaining requirements

1. S03 amendment per unit (D-13), including the featurizer as part of the unit's method.
2. Implementation of `sequence_constraints`, `fk_integrity` and `schema_path_rules` (declared constraints only).
3. A unit-level mechanism list per contrast (which operators carry the contrast) before eligibility is verified.
4. Owner decisions D-02 and D-08 on exposure, which change the pool from 119 to 95.
