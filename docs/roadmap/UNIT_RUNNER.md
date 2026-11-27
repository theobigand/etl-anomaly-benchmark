# Synthetic runner of the unit-level protocols (#135, #137, #138, #139)

`research/unit_runner.py` is the first registry-driven runner for the five unit-level protocols. It is software
validation on seeded synthetic fixtures. It reads no real view, fits and scores no detector, computes no metric and
changes no ledger count. Run it with `python research/unit_runner.py --seed 0 --faults 3`.

## What one run does

1. Builds the synthetic fixture of the protocol from a seed (`fixture`). The only accepted input is a `Fixture`; any
   other origin is refused, and a request flagged `scientific` is refused with the freeze reason.
2. Injects `k` faults with the operator of `fault_protocols` (the mechanics of `verification/anomaly_protocols.md`).
3. Checks the contract: the ground truth lies inside the units; exactly the truth units changed; the input was not
   modified; the run is deterministic for its seed; the fault count matches. A broken contract raises a classified
   `ProcessingFailure` naming the failed checks; a precondition that does not hold raises `InapplicableFailure`.
4. Reports the unit and its status from `compatibility_model.UNITS`, the unit count, the truth, and the natural
   baseline defects apart from the injected truth.

`coverage(protocols)` compares the runners with the registry's protocols and detection units, so a protocol without a
runner or with a different unit is reported rather than assumed.

## Protocol matrix

| Protocol | Issue | Unit (status) | Ground truth by injection | Operator | Metrics counted by the registry |
|---|---|---|---|---|---|
| P-TAB | #135 | `row` (protocol defined) | the rows scaled | `inject_scale` | tp, fp, fn |
| P-TS | #135 | `time_window` (protocol defined) | the windows of `WINDOW` points shifted | `inject_level_shift` | tp, fp, fn |
| P-SEQ | #137 | `event_sequence` (protocol defined) | the traces with two adjacent events swapped | `swap_adjacent` | tp, fp, fn |
| P-REL | #138 | `relationship` (protocol defined) | the child rows whose reference is broken; natural orphans are the baseline and never labelled | `break_foreign_key` | tp, fp, fn |
| P-NEST | #139 | `nested_path` (protocol defined) | the (record, path) pairs whose nested field is removed; nesting is kept | `corrupt_path` | tp, fp, fn |

The provisional batch-style units (`event_window`, `relational_load`, `document_batch`) are not implemented here and stay
provisional. The status shown above is the registry's; the unit definitions still need the dated amendment of S03
(#154) before any scientific use.

## Why C6 had no executable group, and what changed

C6 maps to P-NEST, whose unit `nested_path` had no runner and which has no route to the registered `temporal_batch`.
There is now a runner for `nested_path` that keeps the nesting (no flattening) and is exercised on synthetic nested
fixtures. C6 stays at zero executable groups in the utilization ledger: a group is executable only with an approved
execution path, and that waits for the unit approval (D-13 of [OWNER_DECISIONS.md](OWNER_DECISIONS.md)).

## What this does not change

The utilization ledger is unchanged (executed, evaluated, included and excluded stay at zero). Mapping a group to a
runner is not executability. The next engineering step is a dataset adapter that feeds a real view to the same
`Runner` interface, which needs the owner's authorization for any run beyond the structural checks of
[UNIT_DRY_RUN.md](UNIT_DRY_RUN.md).
