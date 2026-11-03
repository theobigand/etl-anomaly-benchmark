# Prospective mutation-policy migration

Tracking: [#116](https://github.com/theobigand/etl-anomaly-benchmark/issues/116),
coordinated with #100, #103, #110, #111 and historical #84. Baseline: `6b9f7c5`.
Status: **in progress; policy-v2 certification is not available**. The canonical
T001–T415 identifiers and their existing completion states are unchanged.

## Accepted prospective contract

The prospective thresholds are L1 80%, L2 90%, L3 95% and L4 98%. Classification
uses consequences, with the highest applicable level for a module containing
multiple responsibilities. L4 covers leakage prevention, metrics and alignment,
dataset/evidence identity, scientific consistency and certification decisions.
Uncertain scientific code defaults to L3 pending justified review. A lower risk
assignment must never be used to resolve a failing threshold.

Each required module must meet its own threshold; a passing aggregate does not
compensate for a failing module or higher-risk level. Exact integer comparisons
decide boundaries. Every legitimate catalog entry remains in the denominator.
Timeouts, suspicious outcomes and type-check-only outcomes are recorded separately
and do not count as killed assertions in the prospective arithmetic. Unchecked,
skipped, untested, interrupted or crashed cases make the affected scope incomplete.
Known failures remain failures when another scope is incomplete.

Every production file under the governed roots must be explicitly classified.
Test directories and generated caches are not production. A technical no-mutant
declaration requires a reason and cannot hide a function: package re-exports or
constants for which the engine generates no functions are distinguished from
executable logic. Source, experiment, research and verifier inventories must be
reconciled, including the explicit new pool-preparation modules.

## Enforcement boundaries

`verification/mutation_policy.py` initially provides only strict classification,
catalog/outcome reconciliation and arithmetic. Its result is **not** release
evidence by itself. Computing a current source or policy hash cannot make old
execution admissible. Promotion still needs current execution/test/configuration,
tool/dependency provenance and a catalog generated from the governed source.

The existing global classifier, scope checker, evidence envelope, release policy,
bundle allowlist and workflows must migrate together. Until that integration and
its acceptance checks pass, the legacy CLI remains historical behavior and must
not be called a policy-v2 certification path. Current certification is not implied
by a new JSON policy or by passing arithmetic tests.

## Historical preservation and cache policy

The d4304c5 historical figures and the later 4,972/5,102 local core campaign retain
their original 95% criterion and denominator. They are not reinterpreted as
four-level results. No sealed evidence, run record, scientific hypothesis or
experimental result is restamped by this migration.

Development uses a separately generated, single-module feedback sandbox and its
persistent mutation cache. The global `mutants/` cache remains separate. Policy
classification changes require new compliance evidence, not automatic re-execution
of unchanged admissible verdicts. Source/tests/tool/execution changes invalidate
the relevant execution. Native mutmut 3.8.0 source hashing and configuration
invalidation are retained; repository test hashing complements them. Configuration
or dependency changes can require broader invalidation, which must be reported.
The installed source was inspected alongside the official
[mutmut changelog](https://github.com/boxed/mutmut/blob/main/HISTORY.rst) and
[upstream implementation](https://github.com/boxed/mutmut/blob/main/src/mutmut/__main__.py).

## Ready, checks and remaining acceptance

Risk: L4 (98%). Mutation policy, counts and evidence acceptance can silently
invalidate scientific evidence. Before edits, 192 existing mutation/scope/evidence/
release tests passed. Tests for the missing prospective engine were added before
implementation; strict-version, malformed-level and aggregate-failure regressions
also failed before their corrections. The first arithmetic unit passes 69 checks
with 129/129 measured lines and 74/74 branches. These counts describe that unit,
not the whole repository or the finished migration.

The initial focused campaign killed 368 of 469 mutants (78.46%), below L4's 98%
requirement. Its 101 survivors are retained for analysis. Coverage did not detect
missing assertions on canonical hashes, report counters and statuses. Additional
contract checks exercise these weaknesses; no survivor is removed or relabelled
as killed. The strengthened suite currently has 75 passing cases with unchanged
129-line/74-branch coverage. The test-file change invalidated all 469 verdicts in
this small focused sandbox; the global cached campaign was not reset.

After explicit verifier-error outcomes were added test-first, 76 arithmetic
checks pass with the same measured coverage. The latest focused campaign remains
403/469 killed (85.93%): **L4 FAIL**. No diagnostic or equivalent mutant is removed
from that denominator. The [focused raw record and report](evidence/risk-policy-focused-2026-11-03.json)
bind the source/test/configuration hashes and explicitly prohibit promotion use.
The [initial evidence bundle](evidence/risk-policy-initial-verification-2026-11-03.tgz)
preserves negative results and original failures. These artifacts are development
feedback, not a completed certification or proof of scientific validity.

The combined arithmetic, historical mutation/scope/evidence/release and publication
regression runs 291 cases successfully. A preceding run failed because the feedback
sandbox was inside the `experiments/` production root: the inventory correctly
reported its generated Python copies as ungoverned. The complete sandbox/cache
was moved to local metadata storage outside production roots, without adding an
exclusion or weakening the inventory; the same regression then passed. Paper
build: 23 pages; slides: 41. New paragraphs/slides were inspected rendered; all
slides pass 1280×720 bounds/footer and keyboard navigation checks. Publication
manifest changes are limited to TeX/PDF artifact hashes and its source revision.
No scientific result table or sealed run record changed. Broader gates, final
mutation compliance and independent review remain pending the full migration.

`verification/mutation_risk_policy.json` is an initial explicit inventory of 91
source modules across the four governed roots: three L2, six L3 and 82 L4. No
whole module was found with only L1 consequences; L1 arithmetic is supported and
tested. Constants/package markers have explicit technical declarations. These
classifications await independent review and execution reconciliation; their
presence does not establish mutation compliance or replace the old release path.

Remaining: explicit justified production inventory; native catalog parsing and
execution provenance; CLI/evidence/release integration; focused survivor analysis;
incremental full-scope reconciliation; negative certification tests; publication
and profile synchronization; applicable gates and independent review after a
tested frozen patch. Any missing or failing scope remains incomplete. Parent
issues and milestones remain open.
