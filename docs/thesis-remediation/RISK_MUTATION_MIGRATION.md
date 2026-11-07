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
