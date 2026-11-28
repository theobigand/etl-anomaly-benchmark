# Proposed scientific specifications of the five protocol-defined units (S03, #154, D-13)

Status: 2026-11-27, proposal. These are drafts of the dated amendments that S03 requires. They are not signed, not
approved and not active; the owner records an amendment per unit (D-13). The experiment freeze stays active, and the
synthetic runners (`research/unit_runner.py`) are software validation only. A unit name alone is not an approval:
each column below must be accepted whole, or amended, before a runner is used scientifically.

Facts the proposals build on (committed registry): the unit definitions and operator lists of
`dataset_registry_v2/compatibility_model.json`, the injection mechanics of `anomaly_protocols.md` and the synthetic
operators of `unit_runner.py` (`inject_scale`, `inject_level_shift`, `swap_adjacent`, `break_foreign_key`,
`corrupt_path`). The registry lists no detector for any protocol-defined unit and counts only `tp`, `fp` and `fn`;
the detector interface, scoring and budget rows below are therefore new proposals, not recorded facts.

## 1. Common frame (all five units)

- Inference unit: the provenance cluster; all unit-level outcomes are aggregated as in
  `pilot_statistical_remediation.md` section 5.
- Budget: B = 1 percent, k = floor(B x N) over the eligible test units, the same k for both detectors of a pair, no
  minimum-one-alert exception; confirmatory only with at least 20 positives, k at least 10 (N at least 1,000).
  Maximum attainable recall is min(1, k / P).
- Ties: broken by the SHA-256 of the unit identifier, never by input order.
- Injection happens after the split, into test units only; injected labels are written to a sealed file before any score
  exists; natural defects of the source are the baseline, never labelled, and are reported separately.
- Fit and any threshold use training (and validation) units only. A detector that cannot score the unit is reported as
  not applicable for that group, never imputed.
- Failure modes common to all: a broken contract (ground truth outside the units, a unit changed that is not in the
  truth, input modified, non-determinism, wrong fault count) is a classified `ProcessingFailure`; a precondition that
  does not hold is an `InapplicableFailure`; fewer than the floor means the group is below the confirmatory floor, not an
  error.

## 2. Specifications

| Item | P-TAB `row` | P-TS `time_window` | P-SEQ `event_sequence` | P-REL `relationship` | P-NEST `nested_path` |
|---|---|---|---|---|---|
| Unit identity | a row of a registered table view; id = view digest and primary key, else row ordinal | a window of W consecutive points of one series; id = series id and start offset | a case (trace): all events of one case id in timestamp order, ties by log order | a child row of a declared foreign-key relation; id = (child table, FK column, child row id) | a (record, path) pair of a nested document; id = (record id, path) |
| Boundaries | one row; no cross-row dependency inside the unit | non-overlapping windows, stride W; windows straddling a split boundary are dropped | complete traces only; truncated traces are excluded | the child row and its reference; parent tables are reference data, not split | leaf paths with array indices kept for localization; nesting is never flattened |
| Grouping | none inside the unit | one series per window set; several series of one source are one cluster | cases of one log are one cluster | child tables of one source are one cluster | records of one collection are one cluster |
| Eligibility | at least 1,000 test rows; 20 positives; k at least 10 | at least 1,000 test windows after dropping straddlers; ordered time axis | at least 1,000 test traces | a validated declared key (`relational_keys.json`); at least 1,000 test children | at least 1,000 test pairs; a recoverable schema |
| Split | hash of the row id, 70/15/15 (recorded partition) | chronological blocks 70/15/15 (a hash split leaks neighbours) | hash of the case id, 70/15/15, whole cases | hash of the child row id, 70/15/15; parents visible in all splits | hash of the record id, 70/15/15, whole records |
| Leakage prevention | no fit on test; duplicates across splits keyed by content hash | seasonal and level statistics from train only; no centred smoothing across the boundary | prefix and transition statistics from train traces only | no parent statistic computed from test children | schema and value statistics from train records only |
| Ground truth | ids of the rows altered by the operator | windows that overlap the injected interval | traces altered by the operator | child rows whose reference is broken or altered; natural orphans are baseline | (record, path) pairs altered by the operator |
| Operators (supported) | `univariate_outlier`, `multivariate_outlier`, `invalid_category_code`, `missing_values`, `duplicate_rows`, `cross_field_violation` | `point_outlier`, `contextual_anomaly`, `collective_anomaly`, `level_shift`, `gradual_drift`, `seasonal_deviation`, `missing_interval`, `delayed_arrival` | `order_violation`, `missing_event`, `unexpected_sequence`, `duplicate_event`, `abnormal_transition` | `referential_violation`, `invalid_relationship`, `duplicate_entity`, `inconsistent_aggregate` | `missing_required_field`, `invalid_nested_type`, `unexpected_array_or_object`, `broken_hierarchy`, `structural_inconsistency` |
| Fault localization | the row, plus the columns touched (recorded, not scored) | the interval, plus the windows overlapping it | the event index inside the trace (recorded, not scored) | the child row and the broken reference | the exact path |
| Detector interface | `fit(train rows)`, `score(test rows)`: one score per row, higher is more anomalous; a rule gives a violation count | one score per window; a rule gives a violation count | one score per trace; a rule gives a violation count | one score per child row, with the parent key available | one score per (record, path); features are path depth, type and value statistics |
| Scoring | per-unit score | per-unit score | per-unit score | per-unit score | per-unit score |
| Alert budget | k = floor(0.01 N), N test rows | N test windows | N test traces | N test child rows | N test pairs (large; k scales with N) |
| Tie handling | SHA-256 of the row id | SHA-256 of the window id | SHA-256 of the case id | SHA-256 of the relationship id | SHA-256 of record id and path |
| Metrics | primary: recall at k; secondary: precision at k, AUPRC at standardized prevalence | same | same | same | same |
| Aggregation | per-seed recall, then mechanism-severity cells, then cluster outcome (remediation section 5) | same | same | same | same |
| Unsupported | `stale_batch`, `partial_load`, `schema_drop`, `unit_change` (batch properties); `abnormal_entity_behaviour` without an entity key | `prevalence_change` (a property of a period, not a window) | `rare_pattern` (a natural property, not injectable) | `relationship_anomaly` (no operator defined) | `schema_evolution_violation` (a property of a collection, not a path) |
| Failure modes | constant column, no numeric column for an outlier operator, key absent for `duplicate_rows` | series shorter than 3 windows, irregular timestamps | one-event traces, case id absent | no declared key, key not unique in the parent | no recoverable schema, no leaf paths |

## 3. Points the owner must decide per unit (not assumed here)

- P-TAB: whether a defined detector set exists for tabular rows beyond the temporal-batch set; the row unit has no
  registered detectors today.
- P-TS: the window length W per source (a function of the series period) and whether overlap with the injected interval
  or containment defines a positive window.
- P-SEQ: the injected-operator mix, because `swap_adjacent` alone is detected by any order-sensitive rule.
- P-REL: a constraint rule detects every injected `referential_violation` by construction, so a rule-versus-learned
  contrast on that operator is a ceiling check, not a measure of difference. At least one operator that a rule cannot see
  (`inconsistent_aggregate`) must carry the confirmatory contrast, or P-REL is excluded from F1.
- P-NEST: whether the pair count N (very large per document) makes k = floor(0.01 N) a meaningful budget, or a budget per
  record is wanted.
- For every unit: the minimum cluster counts per mechanism, so that a contrast is eligible only where both detectors apply.

## 4. The provisional units

`event_window`, `relational_load` and `document_batch` cut a log, a child table or a document collection into
consecutive batches. They share the temporal-batch metrics (`recall`, `false_alert_rate`, `roc_auc`, `ap`) and operators
(`partial_load`, `duplicate_load`, `stale_batch`, `schema_drop`), have no ground-truth representation, no operators
defined at the unit and no runner. They are logical units, not natural ones, and are not equivalent to
`event_sequence`, `relationship` and `nested_path`, which are natural units with `tp`/`fp`/`fn` ground truth. They stay
provisional. If the owner wants them, each needs its own amendment with the same eight rows as above, and they must never
be pooled with the natural units.

## 5. What each amendment would authorize

An approved amendment authorizes scientific use of that unit by its registry-driven runner on real views, subject to the
separate gates for a pilot and for a confirmatory run. It authorizes no execution by itself, creates no ledger count and
does not lift the freeze.
