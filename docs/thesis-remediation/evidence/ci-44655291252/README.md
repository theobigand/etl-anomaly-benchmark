# Release verification of main at 2dca21f (run 44655291252), 2026-11-20

`verify-release` (workflow_dispatch, `fresh_mutants=true`, `approved_sha` = the commit) on `main` at
`2dca21fc6c3d77be74a241d240d9d3048d85e4f4`. Verdict **CERTIFIED**: fast, deep, faults, real, tools, types and
reproduction all PASS, attestation `ci-run:44655291252 (not independently attested)`. `release.json` is the report;
`campaign-summary.json` is the per-module outcome of the mutation campaign (45 shards, 37,759 mutants, 37,248 killed, 505
survived, 6 timeouts; L2 98.41%, L3 98.56%, L4 98.67% raw and 99.00% adjusted with the 98 recorded equivalences).
The shard artifacts are not archived here (they stay with the run).

Attempts that did not certify, kept for the record (all on commits of the same series):

| Run | Commit | Result | Cause | Repair |
| --- | --- | --- | --- | --- |
| 44607789106 | 79fe9b8 | deep INCOMPLETE | the optional `reference` argument of `injection.inject` changed the source digest and mutant numbering, so the four accepted-equivalence records of that module no longer applied | PR #125 rebinds them (same mutation, new id and digests) |
| 44614776526 | fc01088 | deep INCOMPLETE, every mutant "not checked" | since #121 the temporal pilot record test has a new name while the mutation configuration still deselected the old one; in the mutation sandbox the fingerprint is computed on mutated scripts, so mutmut could not collect statistics | PR #126 deselects the current name |
| 44625721928 | cb6e37b | mutation campaign FAIL | `research/pool_train_only_replay.py` (L3) scored 301/365; the earlier local macOS measurement overstated it because the command test uses a real process pool | PR #127 adds tests of the command without a pool |

No threshold, risk level or policy was changed. The verdict concerns `2dca21f` only; later commits that add documentation
and archived evidence do not carry a separate run.
