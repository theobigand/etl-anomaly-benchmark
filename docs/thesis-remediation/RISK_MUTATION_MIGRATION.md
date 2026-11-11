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

The scope checker now inventories all four governed roots and compares the native
patterns with the policy inventory. The current DEEP envelope and public mutation
gate require a bound native campaign rather than a standalone aggregate count.
The DEEP Makefile target owns the native controller and retains existing native
exports until a new run replaces them. The version-2 release policy rejects a
legacy global envelope for a current certification. Workflow artifact contracts
still need the same migration.
Current certification is not implied by a new JSON policy, a passing arithmetic
test or an internally consistent stored campaign.

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

`verification/mutation_risk_policy.json` now inventories 92 canonical
source modules across the four governed roots: three L2, six L3 and 83 L4. The
initial 91-entry draft included two generated sandbox copies; these were removed
after relocation, the native-catalog adapter brought the count to 90, the
managed execution controller then brought it to 91, and the current DEEP
campaign reader is the 92nd governed module. No
whole module was found with only L1 consequences; L1 arithmetic is supported and
tested. Constants/package markers have explicit technical declarations. These
classifications await independent review and execution reconciliation; their
presence does not establish mutation compliance or replace the old release path.

## Native catalog and execution-binding checkpoint (2026-11-04)

The native 3.8.0 adapter reconciles generated span indexes, metadata, listing and
statistics without treating parsing as proof of execution. Current function
hashes must match generated functions, including nested-class identities. Native
exit 3 (internal runner error), unknown codes, interrupted cases and type-check-only
outcomes cannot become assertion kills. Read-only reconciliation against the old
5,102-entry cache finds 57 missing current module catalogs and 11 modules below
their prospective thresholds. This is a readiness projection, not a new campaign
or reinterpretation of historical results.

The execution-binding prototype records source/function/global hashes, test
hashes, execution configuration and supplied runtime metadata before and after
an attempt. It rejects stale generated functions, unbound metadata edits, external
cache aliases, malformed proofs and changed inputs during execution. A pending
attempt requires authoritative process checks before recovery; its presence or
age is not evidence that its process has stopped. Previously unbound results
cannot acquire current provenance merely by recording them retrospectively.

Changed functions reopen their transitive callers when the recorded dependency
map is usable. Missing dependency information or changed uninstrumented support
requires broader invalidation. After a nonzero native attempt, a source or test
change also triggers broader invalidation because its saved maps may be partial.
Unchanged bound settled results remain reusable, including after partial attempts.
Compliance policy files are evaluated separately: changing classifications or
thresholds alone does not force unchanged execution to repeat.

225 targeted cases pass, covering 531/531 executable lines and 264/264 branches
across the arithmetic, native-catalog and cache helpers. Four partial-proof and
scope/version regressions and two policy/proof-shape regressions failed before
their corrections. These are constructed software checks, not measured mutation
compliance. The old focused 403/469 failure belongs to its archived source/test
snapshot and is not restamped for these changes. Runtime collection, the managed
native execution command and evidence/release integration remain outstanding.

Remaining: explicit justified production inventory; native catalog parsing and
execution provenance; CLI/evidence/release integration; focused survivor analysis;
incremental full-scope reconciliation; negative certification tests; publication
and profile synchronization; applicable gates and independent review after a
tested frozen patch. Any missing or failing scope remains incomplete. Parent
issues and milestones remain open.

The current FAST gate passes: 1,557 tests, 1,790/1,790 measured core/experiment
lines and 350/350 branches. This coverage scope does not include all research or
verifier modules. The targeted helper measurements above are separate. The paper
build has 23 pages; all 41 slides pass bounds/footer and keyboard-navigation
checks at 1280×720, and the changed publication pages were inspected rendered.
The manuscript manifest updates only its TeX/PDF hashes and source revision.

The complete TOOLS gate also passes: 2,475/2,475 verifier lines and 970/970
branches. No verifier exclusion was added. The [checkpoint record](evidence/risk-native-cache-checkpoint-2026-11-04.json)
and [SHA-verified source/check archive](evidence/risk-native-cache-verification-2026-11-04.tgz)
preserve these bounded checks with `promotion_eligible: false`. The local typing
checker and stubs are unavailable; the pinned typing gate is not reported as
passed. Current native mutation compliance and independent review remain pending.

## Managed native execution checkpoint (2026-11-04)

`verification/mutation_run.py` is L4 (98%): it exclusively owns the cache through
an operating-system file lock, checks the configured scope against the classified
inventory and launches a native process group. A parent exit does not establish
that its workers stopped. Live or uninspectable groups, interrupted waits, pending
attempts, changed inputs and changed inventories prevent a new execution binding.
Each started attempt keeps a separate log and completed attempts preserve their
proof snapshots. A nonzero native return remains explicit, including settled
partial results; none of these records is a compliance verdict.

The first actual smoke attempt stopped before execution because the historical
Conda environment contains conflicting distribution metadata for ten packages.
No numerical package was changed to remove this failure. A clean local verification
environment instead pins mutmut 3.8.0 and pytest 9.1.1 for a constructed two-mutant
example. Both mutants were killed, and an unchanged subsequent run reused both
verdicts with zero mutation executions. This validates the controller path only,
not mutation adequacy of the thesis modules or reproducibility of their results.

A constructed project-local `mutmut` package exposed an entrypoint-shadowing
defect. The corrected native command uses Python 3.11 safe-path startup (`-P`)
and an empty child `PYTHONPATH`, while preserving the fixed hash seed and thread
settings. The installed runner then executes despite the shadow package.
See the official [Python 3.11 safe-path semantics](https://docs.python.org/3.11/using/cmdline.html#cmdoption-P)
and [process-group behavior](https://docs.python.org/3.11/library/subprocess.html#popen-constructor).

Execution-binding format 2 additionally binds native generated source and span
indexes. Changed native artifacts reopen the active verdicts; settled results
without their generation artifacts cannot receive a binding. Prototype format-1
proofs are rejected, not upgraded by hashing present-day artifacts retrospectively.
For the constructed example only, the old proof was copied intact after verifying
that no pending attempt or native process group remained; removing its active
pointer caused an explicit bootstrap reset of two results. Native generation and
execution then revalidated them under format 2. The following unchanged run kept
two and reset zero. The global thesis cache was not reset or executed.

255 combined targeted cases pass with 641/641 measured lines and 288/288 branches
across the four mutation helpers. The 12 initial controller failures, two attempt/
inventory regressions, three generation-binding failures and entrypoint negative
control preceded their corrections. Typing initially reported six new verifier
errors; annotations and a local variable rename resolve them without changing
the 17-entry scientific baseline. The pinned checker/stubs (mypy 2.4.0 and
pandas-stubs 3.0.5.260914) pass in an isolated overlay of the existing environment;
the historical numerical installation is unchanged.

Remaining integration: DEEP orchestration, risk-scoped CLI/evidence/release and
bundle/workflow enforcement, present-snapshot mutation adequacy, final publication
and profile reconciliation, and independent review. The environment metadata
conflict remains a blocker for a trustworthy new global campaign in that specific
environment; a clean pinned full scientific environment is required before reuse
as current certification evidence. No canonical task or parent acceptance is
closed by the constructed smoke test.

Final intermediate checks: 255 targeted cases, now 645/645 lines after typing-only
annotations expanded local declarations, and 288/288 branches. FAST passes 1,587
tests with unchanged 1,790-line/350-branch core measurements. A subsequent test-
worker cleanup change has 24 passing controller cases and a full TOOLS rerun:
2,589/2,589 lines and 994/994 branches. No scientific source or result changed.

Focused controller mutation: **259/318 killed (81.4465%), L4 FAIL**, 59 survivors,
zero exclusions. Native catalogs/outcomes and survivor diffs are retained in the
[checkpoint record](evidence/risk-controller-checkpoint-2026-11-04.json) and
[SHA-verified archive](evidence/risk-controller-verification-2026-11-04.tgz). Both
remain promotion-ineligible. Initial triage identifies missing assertions on
actual child environment, captured stderr, runtime keys, pending/audit pointers,
configured technical scope and CLI defaults/parallelism. Diagnostic-only and
platform-dependent survivors are not silently excluded or called killed.

## Controller contract follow-up (2026-11-04)

The final lint check at f636bf3 found SIM105 in test-worker cleanup, after FAST and
TOOLS had run. The command sequence nevertheless committed; this was not a
passing style gate. The follow-up uses explicit exception suppression only for
cleanup of an already-terminated constructed worker, then checks lint and format
before committing. The original archive is retained unchanged.

Strengthened contracts observe the actual child environment and stderr, default
and explicit worker limits, pending-log pointers and immutable audit-log hashes,
source/runtime identity fields, and separately configured technical no-mutant
units. The same production code now has 259 passing targeted cases with 645/645
lines and 288/288 branches; lint and format pass. No production code changed.
The modified test file legitimately reopened all 318 focused verdicts in the
same persistent cache. The global cache was untouched.

The new result is **295/318 killed (92.7673%), L4 FAIL**, 23 survivors, zero
exclusions. Thirty-six additional mutants are detected. Remaining diagnostic,
platform-dependent and potentially equivalent changes remain raw survivors; no
equivalence disposition is inferred. The [follow-up record](evidence/risk-controller-contracts-2026-11-04.json)
and [verified archive](evidence/risk-controller-contracts-2026-11-04.tgz) preserve
this negative result and the cache invalidation counts. Full-gate figures remain
those of the preceding checkpoint, not a new certification.

Publication review: no new benchmark result, native-smoke result or methodological
claim changed. The manuscript and slides already describe the constructed
two-mutant reuse check and incomplete release integration. Their content and
artifact hashes therefore remain unchanged for this test-only follow-up.

## Recorded reports and current execution inputs (2026-11-04)

`evaluate_snapshot` checks recorded policy declarations, source-hash maps and
per-module arithmetic without requiring the old source tree. `evaluate` still
checks the actual production inventory and technical exclusions against source
bodies. A consistent snapshot cannot establish that those exclusions or the
current execution are valid. These checks share the same integer comparisons;
there is no alternative threshold or global-score fallback.

`validate_execution` checks a saved binding against current source/test/configuration
inputs, meaningful native verdict metadata, generated source/index hashes and
dependency/test maps. Missing or pending attempts and mismatched settled counts
are rejected. A consistent partial attempt retains its nonzero native exit; this
function does not independently attest execution or certify mutation compliance.

The missing snapshot and binding interfaces first failed 17 and 13 checks,
respectively. The combined suite now passes 291 cases, covering 685/685 lines and
310/310 branches across the four helpers. Pinned typing passes with the unchanged
17-entry baseline. CLI/evidence/release integration remains required.

The arithmetic module's changed source and test selection require a new focused
result: **470/535 killed (87.8505%), L4 FAIL**, with all 65 survivors retained and
no exclusions. The previous 469-mutant cache was preserved before regeneration;
its 469 verdicts were invalidated in that focused cache and the new catalog was
evaluated separately. This does not reset the global campaign or restamp the
older 403/469 report. The manuscript and slides distinguish recorded consistency
from current-source validity; no benchmark result changed.

The complete TOOLS gate passes on this checkpoint: 2,629/2,629 lines and
1,016/1,016 branches. The [record](evidence/risk-snapshot-binding-2026-11-04.json)
and [verified source/check archive](evidence/risk-snapshot-binding-2026-11-04.tgz)
retain the failed mutation result and earlier focused cache. The paper has 23
pages and the deck 41 slides; changed pages were inspected rendered and slide
bounds/navigation checks pass. The classification and exact per-module arithmetic
criteria are checked in #116; its eight remaining criteria stay open.

## Classification review (2026-11-07)

The inventory holds 92 modules: 83 L4, 6 L3, 3 L2 and no L1. Every entry has a
written reason, and no unit was reclassified for this review. The weighting
towards L4 is deliberate and conservative: nearly all production code here
either defines labels and partitions, computes a reported metric, binds a result
to its inputs, or generates a manuscript table from archived results. Three
groups are arguable and are recorded rather than changed:

- result-to-paper generators (`research/paper_tables.py`, `paper_appendix.py`,
  `typed_figures.py`, `pool_extension_paper.py`): classed L4 because an
  alignment error silently misstates a published number, although they compute
  no new result;
- data acquisition entry points (`experiments/fetch_cardio.py`,
  `generate_synthetic.py`): classed L4 for source and label identity;
- `src/etl_benchmark/logging_setup.py` and the CLI dispatcher keep their lower
  tiers because they cannot alter a reported number.

A reclassification downwards is permitted only through a reviewed change to
`verification/mutation_risk_policy.json`; it changes the policy digest, so it
cannot be used to rescue a failing module without the change being visible in
the compliance record. Over-classification costs more mutants at the strictest
threshold; it never weakens the gate.

The mutation configuration also exposed three environment dependencies that are
recorded here because they decide whether a campaign can start at all:

- mutmut 3.8.0 reads `Item._nodeid`, which pytest 9.2.0 no longer provides; the
  campaign environment must use pytest 9.1.1. The pins live in the workflow
  install command, not in `[project]`, because the scientific fingerprint hashes
  that table.
- the native stats run executes the test selection in the `mutants/` sandbox,
  which contains `src`, `experiments`, `research`, `verification` and
  `environment.yml` only; tests that read other repository files must be excluded
  from the selection or fail the whole stats run.
- on a clean checkout `mutants/` does not exist before the deep target writes
  its controller record into it.

## First complete native campaign (2026-11-07, revision c8e3917)

The managed controller ran the native mutmut 3.8.0 campaign over all four governed
roots in a clean environment (Python 3.11, mutmut 3.8.0, pytest 9.1.1, macOS
arm64, exit 0) and the public gate evaluated it with the version-2 per-module
policy. The verdict is **FAIL**. This is a measured diagnostic, not a certification,
and the record is marked `promotion_eligible: false`
([record](evidence/risk-native-campaign-2026-11-07.json), SHA-verified
[archive](evidence/risk-native-campaign-2026-11-07.tgz)). The historical
95% figures keep their original criterion and denominators.

| Level | Required | Killed / eligible | Score | Modules (pass / fail / incomplete) |
| --- | --- | --- | --- | --- |
| L4 | 98% | 18,400 / 28,107 | 65.5% | 26 / 31 / 25 |
| L3 | 95% | 848 / 1,704 | 49.8% | 1 / 1 / 4 |
| L2 | 90% | 0 / 0 | n/a | 0 / 0 / 1 |

Native totals: 29,811 mutants, 19,248 killed, 3,010 survived, 7,501 without a
covering test, 6 timeouts, 46 segmentation faults (all in
`verification/real_acquire.py` and `research/full_registry.py`). Timeouts,
segmentation faults and no-test mutants stay in the denominator and never count as
kills. Twenty-seven modules meet their own threshold (every core scientific module
under `src/etl_benchmark`, plus several experiment entry points), 32 fall below
it and 30 are incomplete. No aggregate compensates for a failing module.

### Defects found by the first execution

Constructed examples had not exposed these; each was fixed test-first or with a
regression test and is on this branch:

- `only_mutate` patterns are matched by mutmut with `fnmatch`, in which a star
  crosses directories; `research/*.py` selected 24 test files (9,906 mutants of
  test code). The scope checker used `Path.glob` and agreed with the wrong scope.
  It now uses the native matching and the configuration excludes `research/tests/*`.
- The campaign environment needs pytest 9.1.1: mutmut 3.8.0 reads `Item._nodeid`,
  which pytest 9.2.0 removed. The pin is in the workflow install command.
- `make verify-deep` wrote to `mutants/` before creating it on a clean checkout.
- The mutation test selection ignored `tests/verifier`, the only tests of the
  cache and controller, and ran the research scripts without attribution because
  their tests import them by flat name. The selection now includes `tests` and
  `research/tests`, the sandbox holds the documents and workflows the tests read,
  and a finder serves the flat names from the package modules.
- `research/tests` (245 tests) was not part of the default test path; it is now.

### Remaining work before any level can pass

1. 7,501 mutants have no covering test, concentrated in the research summary,
   paper-table and pool modules, `verification/claims.py` and
   `verification/release.py`. Each needs tests that exercise the code, not an
   exclusion.
2. 3,010 survivors need assertions that detect the change or a documented
   reviewed equivalence; they are listed per module in the record.
3. `src/etl_benchmark/__main__.py` and `logging_setup.py` receive no native
   mutants although they contain functions, so they stay incomplete: the policy
   accepts a technical declaration only for modules without functions. This needs
   an owner and reviewer decision (for example a declaration validated against the
   native generation index), not a silent exemption.
4. The 46 segmentation faults come from native or subprocess code reached by the
   mutated path; they need a bounded reproduction.
5. The hosted `release-deep` job cannot finish a 29,811-mutant campaign within its
   180-minute limit on a standard runner; the local campaign took about 1.5 hours
   on ten cores with a cleared cache. The release path needs a persistent or
   sharded cache before it can be exercised remotely.
6. Independent review of the enforcement migration after these changes.

Until these are resolved, the version-2 release policy correctly refuses a
current certification.

### Focused survivor work (development feedback, not evidence)

Contract tests were added for the two leakage-critical research modules, using
the native engine on each module alone with the existing cache:

| Module | Before | After | Remaining survivors |
| --- | --- | --- | --- |
| `research/pool_preprocessing.py` | 203 / 248 (81.9%) | 238 / 248 (96.0%) | 10 |
| `research/pool_train_only.py` | 234 / 332 (70.5%) | 325 / 332 (97.9%) | 7 |

The new tests pin exact refusal messages, threshold boundaries, report fields, the
arguments handed to the detector builder (including the training-prevalence
contamination), output formatting and the CLI contract. Every remaining survivor
was reviewed and is behaviorally equivalent: a default argument written
explicitly (`errors="raise"`, `index=None` for `False`), a case-insensitive
package-name lookup, or an empty-array dtype that broadcasts away. Both modules
stay below 98% under the arithmetic as written, which shows a design question the
owner must decide: the policy has no mechanism for reviewed equivalents, so a
module with more than 2% equivalent mutants cannot pass unless its source is
rewritten to avoid generating them. These figures come from a development run of
two modules and are not bound to a campaign; they do not change the recorded FAIL.

## Reviewed equivalence, zero-mutant modules and sharding (2026-11-08)

**Zero-mutant modules.** `src/etl_benchmark/__main__.py` and `logging_setup.py` are
inside the configured scope and mutmut 3.8.0 does generate mutants for them (39
and 10 on the source alone). The campaign produced none because the engine mutates
only lines the test run covers and no test called `main()` or `setup_logging()`.
This was a missing-test defect, not an engine limitation. After adding
`tests/test_cli_entrypoint.py`, focused native runs give 35 of 36 killed for
`__main__` (L3) and 10 of 10 for `logging_setup` (L2). No technical
`NOT_APPLICABLE` classification was needed or introduced.

**Reviewed equivalence (policy mechanism, version 1).** `verification/mutation_policy.py`
accepts an optional record file, `verification/mutation_equivalence.json`, bound
into the campaign verdict and its artifacts. A record is accepted only for a
surviving mutant, with the mutant identity, module, function, diff, original and
mutated behavior, risk level, reason, supporting evidence, source and module-catalog
SHA-256, author, a different approving reviewer, ISO review date and the policy
version. Any mismatch rejects the whole evidence; nothing is classified
automatically and no record exists yet. Raw counts and the raw score are always
reported; the adjusted score removes only accepted equivalents from the eligible
denominator and never counts them as killed. Historical reports are unaffected.
Proposed equivalents are pending an independent reviewer; the survivors listed for
`research/pool_preprocessing.py` and `research/pool_train_only.py` are candidates,
not accepted exclusions.

**Sharded execution.** `verification/mutation_shards.py` plans a deterministic
partition of the mutating modules (balanced by the weights in
`verification/mutation_shard_weights.json`), builds a per-shard evidence manifest
from a native cache, and aggregates manifests fail-closed: every shard of the plan
exactly once, one shared context (revision, tests, configuration, tool versions),
current source hashes, no unknown or duplicate mutant, then the per-module and
per-level thresholds. A shard with failing scores is valid diagnostic evidence; a
missing, stale or foreign shard rejects the campaign; a nonzero native exit or
missing module can never pass. `.github/workflows/mutation-shards.yml` runs the
plan, one job per shard (each saves its evidence and a uniquely keyed cache even
when scores fail) and the aggregation. It is manual and separate from the release
workflow; wiring the aggregate verdict into the release gate is still pending, and
the hosted workflow has not been dispatched yet.

A real shard (1 of 6, 15 modules, 5,618 mutants, native exit 0) was executed
locally end to end with the same commands and its manifest built by the CLI
([plan](evidence/shard-plan-6-2026-11-07.json),
[manifest](evidence/shard-e2e-1-of-6-2026-11-07.json.gz)). It is a feasibility
record and diagnostic evidence only, not a campaign result.

### Timeouts and segmentation faults (investigation, 2026-11-08)

- **Six timeouts.** The three inspected cases are mutations that change how many
  rows a block bootstrap samples (`research/paired_bootstrap.py`, `research/temporal_decision.py`),
  so the mutated code runs far longer than the original. They are mutation-induced
  slow paths, not runner faults, and stay outside the killed count. A direct test
  of the bootstrap result on a small input is the intended way to detect them.
- **46 segmentation faults.** All occur in the forked native runner, in
  `verification/real_acquire.py` (44, including every `GuardedRedirects.redirect_request`
  mutant) and `research/full_registry.py` (2). Run directly, the same mutant under
  the same tests fails an ordinary assertion and is killed, both in a plain process
  and in a forked child, with and without `OBJC_DISABLE_INITIALIZE_FORK_SAFETY`. The
  crash is therefore not an application defect in the exercised code, and it is not
  reproduced by a simple fork. The cause (a platform or worker-pool interaction of
  the runner on macOS arm64) is unresolved. They remain incomplete outcomes; a Linux
  shard run will show whether they are platform-specific. No segmentation fault is
  counted as a kill.

## Release-gate integration of sharded campaigns (2026-11-08)

A complete sharded campaign and a complete monolithic campaign now share one
evidence contract: a `deep` envelope whose result has `format_version: 2`, the
classified policy, the full mutant catalog, every outcome, the reviewed-equivalence
file when present, the native exit status, the runtime and the artifact paths.
`verification.evidence_schema deep-shards` builds it from a shard plan and the
shard manifests. The same arithmetic (`mutation_campaign.status`) decides the
verdict, and the same validation re-derives the result from the current plan,
manifests, policy, source, tests, configuration and tool versions and rejects any
difference, so stale, foreign, duplicated, tampered or forged evidence cannot be
accepted. Policy version 2 still rejects historical global evidence.

A sharded campaign is deliberately **not able to pass yet**. Shards are run with
the plain native command, without the controller's execution-binding proof (source,
function, global and test hashes before and after an attempt, and process-group
checks) that the monolithic path requires. The result states
`execution_binding: "unbound"` and its status is capped at INCOMPLETE; a failing
campaign is still reported as FAIL. Giving sharded runs the same proof, or an
equivalent verifiable record, is the remaining step before a sharded campaign can
contribute to a certification. The legacy file-scope check was also skipped for
format-2 evidence in the release assessment because those results reconcile their
scope through the policy inventory; previously a passing monolithic campaign
would have been rejected by it.

The deep-profile typing and coverage gates also cover the new modules: the pinned
typing check (mypy 2.4.0, pandas-stubs 3.0.5.260914) found five errors in the
first version of the shard planner, which were fixed, and the REAL profile passes
locally on the three research datasets.

## First hosted sharded campaign (2026-11-08, run 42393637254, commit 20342c2)

The manual workflow ran on PR #117 (label `run:mutation-shards`, same-repository,
read-only token) on `ubuntu-latest`, Python 3.11.18, mutmut 3.8.0, pytest 9.1.1:
plan, six shards, aggregation and the release-contract evidence wrapper all
completed. Every shard finished successfully and uploaded its manifest; the
aggregate reconciled the complete catalog and returned **FAIL** (a quality
result, not an execution failure). The record is
[hosted-sharded-campaign-2026-11-08.json](evidence/hosted-sharded-campaign-2026-11-08.json)
with the [full aggregate](evidence/hosted-sharded-campaign-full-2026-11-08.json.gz);
it is marked `promotion_eligible: false` (shards are not yet execution-bound).

| Level | Required | Killed / eligible | Score |
| --- | --- | --- | --- |
| L4 | 98% | 19,117 / 29,387 | 65.1% |
| L3 | 95% | 856 / 1,740 | 49.2% |
| L2 | 90% | 10 / 10 | 100% (PASS) |

Totals: 31,137 mutants, 19,983 killed, 3,891 survived, 7,252 without a covering
test, 11 timeouts, **0 segmentation faults**. The 46 faults of the local macOS run
therefore came from that platform's runner, not from the code. Modules: 20 pass, 43
fail, 27 incomplete, 3 declared technical.

Shard wall times were 19.5, 26.7, 35.6, 42.6, 48.9 and 49.3 minutes, so the
mutant-count weights balance counts (about 5,000 each) but not time; the longest
shard is 2.5 times the shortest. The largest cost is the repeated native test
collection and the slow research and verification suites rather than the number of
mutants. Rebalancing should use measured per-module durations, which the next run's
manifests can record. This run used no restored cache (first run for this key); the
caches saved by each shard are keyed by run id and will be the restore source for the
next run.

Not yet exercised on hosted runners: cache restoration, a second incremental run,
and failure recovery of a single shard.

## Shard execution proofs and cache behavior (2026-11-08)

**Execution binding.** Shards now run through the managed controller
(`python -m verification.mutation_run --names <shard patterns>`), which holds the
cache lock, binds source, function, global, test, dependency and runtime hashes
before and after the attempt and refuses to bind if any input changes during it. A
shard manifest built with `--attempt` carries a verified summary of that proof:
proof and attempt digests, the native command (which must equal the shard's own
patterns), exit status, per-module source and verdict-metadata digests, test and
dependency digests and the runtime. Aggregation rejects a shard whose summary
contradicts its manifest, the plan, the sources or the shared context, rejects shards
that ran different test or dependency sets, and marks the campaign bound only when
every shard carries a proof. A bound campaign can pass; an unbound one stays
INCOMPLETE; a bound campaign below threshold fails. Eighteen regression tests cover
missing, forged, stale, foreign, contradictory and mixed proofs.

The aggregator verifies the proof's internal hash chain and its agreement with the
plan, sources and context; it cannot re-inspect each shard's live cache, which is
only available on the shard runner. That is the same trust boundary as stored
monolithic evidence, but it means a shard runner with write access could fabricate a
consistent proof; independent re-execution is the only defense.

**Real shard check (local, controller-bound).** Shard 31 of a 45-way plan
(`research/lstm_detector.py`, `research/pool_check.py`) ran through the controller:
557 mutants (495 killed, 62 survived), native exit 0, manifest built and verified.
This is feasibility evidence, not a campaign result.

**Cache behavior on the same shard** (admission reports of the controller):

| Change | Verdicts kept | Reset |
| --- | --- | --- |
| none (rerun) | 557 | 0 (1 min instead of about 10) |
| one test file edited | 377 | 180 (mutants it covers) |
| one source function edited | 517 | 40 (function and transitive callers) |
| source reverted | 517 | 42 |
| one verdict edited in a `.meta` file | 377 | 180 ("unbound metadata change") |

Unchanged valid verdicts are reused, changed tests and functions invalidate only the
affected mutants, and an edited verdict is not trusted. A pending attempt left by an
interrupted run blocks the next attempt until its process group is confirmed gone,
as designed; recovery here followed that check. The hosted cache restore and
cross-run reuse remain to be exercised with the next hosted campaign.

### Focused measurements of research modules (local development runs, 2026-11-08)

Native single-module runs after the sandbox selection fixes, before new tests for
them (not bound to a campaign):

| Module | Killed / total | Note |
| --- | --- | --- |
| `research/injection.py` | 323 / 336 (96.1%) | 13 survivors |
| `research/normalise.py` | 175 / 193 (90.7%) | 18 survivors (historical, leakage-relevant) |
| `research/uci_loader.py` | 157 / 186 (84.4%) | 29 survivors |
| `research/pool_full.py` | 223 / 515 (43.3%) | 265 no tests: `main` (197) and `run_job` (68); 27 survivors |
| `research/labelled_benchmark.py` | 112 / 475 (23.6%) | 361 no tests: `main` (204), `run_job` (70), `jobs` (62), `load_uci` (25); 2 survivors |
| `verification/claims.py` | 599 / 714 (83.9%) | was 5 / 714 before the sandbox selection fix |
| `verification/release.py` | 680 / 827 (82.2%) | was 557 before tests for the command wiring |

The uncovered mutants of the two pool pipelines are the orchestration entry points
(`main`, `run_job`, `jobs`); their tests need a tiny synthetic pool driven through
the real functions and an assertion on the aggregated, per-seed and per-partition
result, not on call order. That is the next test batch, followed by the survivors in
`normalise`, `uci_loader` and `injection`.

## Hosted diagnostic shard, first execution (2026-11-08, run 42401769698, commit 034ea98)

A non-certifying diagnostic (label `run:mutation-shard-diagnostic`: one small shard,
31 of a 45-way plan, no aggregation) ran on a hosted runner with the controller. The
plan job, the checkout at the PR head SHA (verified in the job), the controller
(bootstrap admission, native command with the shard's own patterns, exit 0), the
manifest with its execution summary and the artifact transport all worked; the shard
took about 16 minutes. 557 mutants: 367 killed, 190 survived. The same shard run
locally on macOS gave 495 killed and 62 survived, so 128 mutants differ between
environments; the cause (platform-dependent tests, or tests that need local data) is
not yet identified and is recorded as an open question rather than averaged away.

### Hosted cache reuse (run 42403174357, commit d6641df)

The second diagnostic run of the same shard restored the cache saved by the first
(run-keyed key, restore by prefix). The controller's admission report was
`kept: 557, reset: 0, reasons: []`: every verdict was reused because source, tests,
configuration and tools were unchanged, and the shard again finished with native exit
0. Wall time stayed about 16 minutes because dependency installation and the native
stats collection are repeated regardless of reuse; the saving applies to the mutant
executions only. Hosted invalidation after a test or source change was shown locally
(see above) and has not been repeated hosted. The diagnostic label has been removed.

The mutation counts of the three recorded executions of this shard differ between
environments in one module: `research/lstm_detector.py` is killed 128 more times on
the macOS run than on the hosted Linux runs (all 128 mutants are in the PyTorch
detector). This is unexplained and must be resolved before hosted scores are
compared with local ones.

## Cross-platform discrepancy for `research/lstm_detector.py` (2026-11-08)

**Observation.** Shard 31 (`research/lstm_detector.py`, `research/pool_check.py`) gave
495 killed locally (macOS arm64) and 367 killed on the hosted Linux runner. By stable
mutant identity (557 shared identities, same catalog), the two runs agree on 429
mutants and differ on exactly 128, all `killed` locally and `survived` on Linux, all
in the PyTorch detector (`fit` 55, `settings` 26, `__init__` 24, `_reconstruction_error`
9, `score`, `validation_loss_now`, `_windows`, `_Network.__init__`). No mutant is
killed only on Linux, none is without tests and none has a different error or
timeout outcome.

**Environments.** The runs used different commits (3d6ae7c locally, 034ea98 hosted); `research/lstm_detector.py`, `research/pool_check.py`, the four mapped test files, `research/tests/conftest.py` and `pyproject.toml` are byte-identical between them (checked with `git diff`). Both used mutmut 3.8.0, pytest 9.1.1, Python 3.11,
numpy 2.4.6, pandas 3.1.1, scikit-learn 1.9.1 and torch 2.15.0 (CPU build on Linux).
The shared catalog and the same mapped tests (14 for `LSTMAutoencoder.fit`, from
`test_lstm_detector`, `test_deep_typed`, `test_cost_study`, `test_lstm_pilot`) apply
on both. Version differences therefore do not explain it.

**Reproduction.** For a random sample of 16 of the 128 mutants (and three inspected
in detail, for example `spread > 0` changed to `spread >= 0` in `fit`), the mapped
tests were run directly with `MUTANT_UNDER_TEST` set, in the mutmut order, in a
forked child after a collection warm-up, and with the controller's thread and hash
settings: all 14 tests passed for every sampled mutant, as they do unmutated. A
direct run therefore agrees with the hosted Linux verdict (survived). The local
native run reports those mutants as killed because a test fails in the forked worker
of the local macOS runner (`worker exit code 1`), a failure that does not occur
when the same tests run directly. The exact worker failure was not captured; the
evidence is the disagreement between the runner and direct execution, not a
diagnosed traceback.

**Status of the explanation.**

- Observed: 128 mutants differ between the two runs, all in the PyTorch detector.
- Observed: for 16 sampled mutants (three inspected in detail) the mapped tests passed when run directly with the mutant active.
- Observed: the hosted Linux campaign reported those mutants as surviving.
- Inferred: the local macOS forked worker produced test failures unrelated to the mutations.
- Unverified: the exact worker failure, and any relationship to the 46 macOS-only segmentation faults (which did not occur on Linux).

Because the local verdicts are not confirmed by direct execution, they are not used
as evidence that the tests detect those mutations; the hosted Linux verdict is the
one relied on, and `research/lstm_detector.py` needed behavioral tests (the
`scale_` zero-variance guard is an example).

**Policy consequence.** Release policy version 2 now carries `deep_platform: "Linux"`:
a risk-tiered campaign (monolithic or sharded) is accepted by the release gate only
if its recorded environment platform starts with `Linux`; macOS campaigns remain
usable as diagnostics only. Evidence records already bind the platform, Python and
the checked package versions, and the shard aggregator rejects shards from
different contexts, so Linux and macOS results cannot be combined. The earlier
local figures that include PyTorch-dependent modules (for example the 495/62 shard
record) are retained as diagnostics and are superseded by the hosted values for
those modules. No dependency lock was introduced: torch versions were identical.

### LSTM detector tests (2026-11-08)

`research/tests/test_lstm_contracts.py` (35 tests) pins constructor and `fit`
validation and boundaries, the population-spread training statistics and the
zero-variance guard, median imputation, the training-quantile threshold, the strict
flag comparison, window capping (boundary, distinctness, order), the seeded shuffler,
the configured learning rate, deterministic algorithms and threads, the early-stopping
arithmetic (row-weighted epoch loss, strict improvement, patience), the reported
settings, and the exact refusal messages. Because the local forked runner is
unreliable for PyTorch modules (see above), the 377 mutants of the module were
evaluated by running `test_lstm_detector.py` and the new file directly with each
mutant active: 343 were detected by the older suite alone, 367 of 377 (97.3%) with the
new tests. The ten survivors are default or case-insensitive variants
(`astype(None)` on float data, `dim=+1` on the last axis, `version("TORCH")`, a
stale counter reset on the first epoch, the validation cap with `>=` followed by a
sorted index selection that keeps the order, and `replace=None` in the sampler whose
behavior was not independently established); they are candidates for the equivalence
review, not accepted equivalents, and the sampler case needs a semantic argument. This direct evaluation is a diagnostic
and does not replace a hosted native campaign.

### Focused native Linux run of the LSTM module (hosted diagnostic, 2026-11-08, commit 61042c1)

Shard 31 on a hosted runner (diagnostic label, non-certifying, controller-bound, native
exit 0) with the new LSTM tests: `research/lstm_detector.py` 377 mutants: **332 killed,
43 timeouts, 2 survived** (88.1% killed; timeouts do not count as kills);
`research/pool_check.py` 180: 118 killed, 62 survived (65.6%). The cache reset 192
verdicts and kept 365 (the changed and added tests). The run took 58 minutes.

Comparison with the direct mutant-by-mutant evaluation (367 of 377 detected, 10
survivors) by stable identity: 332 detected directly and killed natively; 35 detected
directly but timed out natively; 8 survived directly but timed out natively; 2
survived in both. No mutant killed natively survived directly. All timeouts are in
`fit` (27), `_reconstruction_error` (13), `_Network.__init__` (2) and `_windows` (1),
that is training-heavy code. mutmut's CPU limit is `ceil((estimated test time + 1) *
multiplier * 2)` seconds with the default multiplier 15, estimated on a small
test-time measurement; the 35 mutants that a direct run detects within seconds hit
that limit on the hosted runner, so these are budget effects, not undetected
mutations. The timeout factor is now 60 (`pyproject.toml`; it reclassifies only
timeout verdicts in mutmut's cache) and the diagnostic shard must be rerun to confirm
the effect. The two native survivors and the eight timeout-only mutants are
inspected next; none is accepted as equivalent.

### Fork-server run of the LSTM shard (hosted, run 42433394723, commit d296f2f)

Diagnostic, non-certifying, controller-bound, native exit 0, cache cold (kept 0, reset 0).
`research/lstm_detector.py`: 377 mutants, **366 killed, 11 survived, 0 timeouts**.
With `process_isolation = "forkserver"` all 46 timeouts of run 42415522768 resolved (37 killed, 9
survived); PyTorch is documented as not fork-safe under mutmut's default isolation. Agreement with direct
execution is exact for 376 of 377 identities (366 killed in both; 10 survive in both); the one difference,
`fit__29` (`spread > 0` to `spread > 1`), was detected directly but survived natively because the older tests
only exercised data whose spread is near one, so the outcome depended on platform arithmetic. A test for a
column with spread below one now kills it, with the test of the non-improving first epoch that kills
`fit__86` (`stale` initial value). That makes 368 of 377 (97.6%) the expected result of the new tests, still
below 98% (370 needed). The nine remaining survivors are equivalence candidates with semantic arguments
(`EQUIVALENCE_CANDIDATES_LSTM_2026-11-08.md`); they are not accepted and the module stays below L4 until an
independent review accepts enough of them or further behavior is found. The expected 368 is a local direct
computation, not a hosted result. Other shard modules in this run: `research/pool_check.py` 118 of 180,
`etl_benchmark/atomic.py` 6 of 6, `transform.py` 2 of 2.

## Sole-author owner-review governance (2026-11-11, equivalence format version 2)

The thesis has one author who is also the repository owner and the only authorized approver, so the earlier rule that
a reviewer must differ from the author is replaced. The policy declares `governance: {review_mode:
"sole_author_owner_review", owner: "theobigand"}`. Equivalence records (document version 2) carry a verdict
(`proposed`, `accepted`, `rejected`, `inconclusive`), the approver, the decision date, the dependency versions the
argument relies on, and the supporting assessments (assistant or AI-model findings, labelled non-authorizing). Only an
`accepted` record signed with the declared owner, bound to the current source digest, module-catalog digest, risk level,
policy version and the campaign runtime's dependency versions, and naming a surviving mutant, removes a mutant from the
adjusted denominator; every other verdict is validated and ignored; any mismatch rejects the whole evidence, and the
raw outcome and raw score are always reported. The model is not independent peer review, and the approver is recorded text
rather than an authenticated signature, which the owner-decision packet states. Historical campaigns and records of format
version 1 are not reinterpreted. Nine LSTM candidates are proposed, none decided
(`EQUIVALENCE_REVIEW_PACKET_LSTM_2026-11-08.md`). The torch version joined the recorded runtime packages so that
equivalences relying on it can be checked.
