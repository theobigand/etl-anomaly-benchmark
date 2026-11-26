# Utilization ledger (issue #133)

Status: generated evidence, no detector run, no fault injected, no held-out outcome read. The
experiment freeze stays active. Source: `research/utilization_ledger.py`; output:
`verification/evidence/dataset_registry_v2/utilization_ledger.json` (one record per provenance
group, deterministic: two runs are byte-identical).

```
cd research && python utilization_ledger.py --output ../verification/evidence/dataset_registry_v2/utilization_ledger.json
```

The ledger needs the locally built views (`data/experimental/`, untracked); it is regenerated from
the registry evidence plus those views. `--no-dry-run` produces the metadata-only version.
Optional `--executions` and `--exclusions` files (group to record) are the only way a group can
reach the executed, evaluated, included or excluded stages; none exists.

## Stages and evidence levels

Seven stages per group, each `yes` or `no` with a reason when negative: acquired, structurally
compatible, executable, executed, evaluated, included, excluded. A later stage is refused without
the earlier one it needs.

| Level | Meaning | Scope |
|---|---|---|
| `metadata_only` | registry facts say the group fits a protocol | group |
| `adapter_dry_run` | the registered batch adapter loaded the group, rebuilt the audited batches and planned the evaluation, with no detector fitted or scored | group |
| `synthetic_end_to_end` | a detector ran on a synthetic fixture | path only (never a group) |
| `scientific_execution` | a registry-driven run produced a result for the group | group |

Executable means the adapter dry run succeeded on an approved (registered) path. Ingestion, loading
and metadata validation are never counted as evaluation.

## Counts (235 groups, 246 category participations, 231 linked clusters)

| Stage | Groups | Clusters |
|---|---:|---:|
| Acquired | 235 | 231 |
| Structurally compatible (metadata only) | 235 | 231 |
| Executable (adapter dry run succeeded) | 47 | 46 |
| Executed, evaluated, included, excluded | 0 | 0 |

Evidence level reached: 47 groups `adapter_dry_run`, 188 `metadata_only`. All 47 audited batch-eligible
groups passed the dry run; none failed.

| Category | Groups | Clusters | Executable | Executable clusters | Previous exposure | Natural labels |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 52 | 52 | 1 | 1 | 0 | 0 |
| C2a | 30 | 30 | 6 | 6 | 0 | 0 |
| C2b | 30 | 30 | 8 | 8 | 0 | 0 |
| C3 | 40 | 39 | 21 | 20 | 5 | 3 |
| C4 | 28 | 27 | 5 | 5 | 0 | 7 |
| C5 | 36 | 36 | 6 | 6 | 0 | 1 |
| C6 | 30 | 28 | 0 | 0 | 0 | 7 |

By protocol (groups, executable): P-TAB 115, 17; P-TS 40, 21; P-REL 36, 6; P-NEST 30, 0; P-SEQ 25, 3.
The protocol belongs to the participation (a group and a category): nine groups sit in two or three
categories under different protocols, so a group is counted under each of its protocols and
protocol rows are not additive. Category rows overlap too (246 participations over 235 groups). The 5 previously
exposed groups are the plumbing-pilot sources of the acquisition report (Update 32); exposure is
recorded, not counted as utilization.

## Execution paths

- `temporal_batch` (registered): adapter `registry_units.load_group` + `pipeline_batch.make_batches`
  + `plan_group`. Synthetic end-to-end evidence: `research/tests/test_pipeline_batch.py::test_a_source_run_finds_gross_faults_misses_silent_ones_and_the_random_floor_is_near_chance`.
  It is the only path any group can currently be executable on.
- `unit_level` (P-TAB, P-TS, P-SEQ, P-REL, P-NEST): injector mechanics exist (`fault_protocols`,
  synthetic conformance only). There is no registry-driven loader, partition or detector runner, so
  no group is executable on it, and no real-data adapter dry run is claimed for it.

## Implementation work before every suitable group can contribute

Counted over the 188 groups that are not executable (a group can need several items):

| Work | Groups |
|---|---:|
| Registry-driven unit-level runner for P-TAB (loader, partitions, detectors) | 98 |
| Registry-driven unit-level runner for P-NEST | 30 |
| Registry-driven unit-level runner for P-REL | 30 |
| Registry-driven unit-level runner for P-SEQ | 22 |
| Registry-driven unit-level runner for P-TS | 19 |
| Approve and implement the `document_batch` unit (no approved definition) | 30 |
| Approve and implement the `relational_load` unit (no approved definition) | 30 |
| Approve and implement the `event_window` unit (no approved definition) | 22 |
| Timestamped numeric table for the batch unit (reasons per group in the ledger) | 188 |

The unit-level runners (issues #134 and #135) are the main lever: they would make the 188 groups
executable on a path that does not need a timestamped numeric table. The proposed units need an
owner decision before any implementation counts (protocol amendment, #152 to #154).

## Verification

Tests: `research/tests/test_utilization_ledger.py` (stage logic, one failure path per stage,
dry-run success and failure, exact entry records, determinism, no detector or fault call). Focused
mutation of the new L2 module (policy: 90 percent): 729 of 742 killed (98.3 percent). The 13
survivors are equivalent or environment-only: message-only arguments (`load_group` group name in an
error message, the reason of a `yes` stage, the parser description), `defaultdict(None)` where no
missing key is read, and six file-name case mutants that survive only on a case-insensitive
volume (macOS) and die on the Linux runner. The run is development feedback, not release evidence.

Not checked: the real-data adapter dry run of unit-level protocols (no adapter exists), relational
key verification of the 33 P-REL groups, and any held-out outcome (frozen).
