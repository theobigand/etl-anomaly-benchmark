# Scoped LSTM equivalence diagnostic

The subsequent hosted result is recorded in
[DIAGNOSTIC_43718624552.md](DIAGNOSTIC_43718624552.md). It applies to its
specified tested commit and does not replace full-campaign validation.

The mutation-shards workflow can validate the existing owner equivalence file
for an LSTM diagnostic after its native shard run. This is a single-shard
report, not full-campaign aggregation, DEEP, release approval or certification.
It does not modify any owner record. A diagnostic deliberately skips cache
restoration, runs the selected plan shard natively, and then invokes
`verification.mutation_shards diagnostic-equivalences` in that same runner.
The existing official `mutation_policy.accepted_equivalents` function validates
the checked-out equivalence document against the shard's actual catalog,
outcomes, source digests, risk policy, governance and observed package versions;
the existing policy arithmetic supplies raw and authorized adjusted scores.

Before that call, the path rejects a foreign policy or equivalence document,
tracked worktree changes, untracked test inputs, absent or incomplete mutant
outcomes, an execution whose current sources, Python tests, configuration,
native metadata, generated artifacts or test maps differ from its recorded
proof, an attempt record that differs from the saved execution proof, and a
runtime inconsistent with the shard context. It records the policy file,
validator, equivalence file, catalog and source digests, runtime and a direct
filesystem case-sensitivity probe. The diagnostic archive now retains the
native log, execution record, saved execution context, native test map,
metadata, spans and generated Python files. It must not be treated as a
substitute for the full aggregate.

The native proof format does not itself contain the Git revision. The reported
commit attribution relies on the workflow's fresh runner, disabled diagnostic
cache restore, use of the just-produced controller attempt, and HEAD checks
before and after native execution. The proof also does not bind every
non-Python or external test input; see
`CAMPAIGN_PROVENANCE_GAP_2026-11-15.md`. Do not promote a separately supplied
old attempt as exact-HEAD evidence merely because its tracked source and test
hashes still match.

The scoped path was tested locally with constructed isolated fixtures, including
changed tracked files, untracked test inputs, a clean later commit with changed
tests, foreign policy/equivalence content, a dependency mismatch, missing and
incomplete results, an empty catalog, changed metadata, changed generated
mutant source, and a differing attempt proof. These fixtures exercise refusal
and arithmetic; they are not experimental campaign evidence. The focused
shard/workflow test group achieved 100% line and branch coverage for
`verification/mutation_shards.py`. This verification-infrastructure change
requires independent review, for which the current session has no remaining
model-review authorization.

No current Linux validator result is claimed until the new workflow actually
runs and its report and artifacts are inspected. The earlier run 43641178258
is documented separately and cannot be retroactively upgraded by this change.
To invoke a fresh PR diagnostic, use the established `run:mutation-shard-diagnostic`
label; it targets the current plan's LSTM shard and skips the aggregate. Remove
the label after the run if further pushes should not repeat it. The owner
records and release gate remain unchanged.
