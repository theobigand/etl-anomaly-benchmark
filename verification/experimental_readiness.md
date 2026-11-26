# Experimental readiness after the acquisition closure (2026-11-25)

Status: preparation only. The experiment freeze is active, no detector ran on a registry source, no
scientific result was generated, nothing was sealed, and release certification is pending. Every
recommendation below is a proposal, not an owner decision.

## 1. Acquisition closure

- Counts reproduce from the committed inputs (`readiness.py`, `target_framework.py`, byte for byte):
  C1 52/36, C2a 30/30, C2b 30/30, C3 40/40, C4 28/28, C5 36/36, C6 30/30; 246 participations, 235
  independent groups, 235 producers, 88 curators, 150 domains, 138 schema families.
- The targeted review (`dataset_acquisition_report.md`, Update 32) changed no group. It found one
  shared upstream column (Bloomington water plant and solar sites), partial identifier overlap
  (GHSA, OSV-Go, NVD) and one related event population (Cincinnati calls and fire dispatch). They are
  recorded as linked sets for the panel split, not merged. Two descriptions were corrected: the FEC
  orphan baseline (98.6 percent of the "orphans" are candidate identifiers; 1,212 of 703,181 remain)
  and the BAAC key rule (use `id_vehicule`).
- Acquisition can stay closed. Reopening needs a verified defect in existing coverage.

## 2. Task matrix (issue #131; canonical list `docs/thesis-remediation/13-pipeline-level-study.md`)

| Task | Acceptance (short) | Status | Remaining / owner authorization |
|---|---|---|---|
| T416 | protocol dated before any result | done: `pipeline_batch_faults.md` (2026-11-21, Amendment 1 before compact result) | none |
| T417 | batch unit and profile; estimands separate | implemented in `research/pipeline_batch.py`, tested | none |
| T418 | eight operators, truth, three severities | implemented, tested | no referential operator (T425) |
| T419 | label-free constraint baseline | implemented (`constraint_rules`, `volume_freshness`) | none |
| T420 | learned detectors, not-applicable recorded | implemented; neural arms recorded as not run (fewer than 200 reference batches) | none |
| T421 | label-free alert budget, false alerts per clean batch | implemented | none |
| T422 | contaminated-reference arm | implemented | none |
| T423 | plumbing pilot on eight real series | partial: results for UCI 275, 360, 374, 560, 849, 851; 247 is excluded (536 rows, below the 1,500-row unit rule, recorded); 799 is eligible (371,122 rows) and not run: execution on a benchmark source is blocked by the freeze (recorded here) | running 799 needs the freeze lifted; nothing else is open |
| T424 | variance pilot, then dated sample-size addendum | not run; batch-level design addendum proposed (`batch_pilot_addendum_proposal.md`), not approved | owner approves the addendum, then authorizes the pilot |
| T425 | relational sources and referential operator | partial: operator (`relational_faults.py`) and key declarations done: 139 plain foreign keys of 32 relational views were recomputed on the local tables and equal the counts recorded by the builders (`relational_keys.json`); a provisional `relational_load` rule runs on synthetic tables (`relational_units.py`); FEC `OTHER_ID` (polymorphic) and two `zen_3pfl` conditional references are listed as not modelled | the `relational_load` unit is not approved (addendum 10.6); running it on a source is a detector run |
| T426 | search for real ETL incident data | searched 2026-11-25 (two public web queries): no labelled public corpus of pipeline incidents with a stated licence; only practitioner write-ups and postmortem summaries. Outcome: none found, no download made | partner outreach is an owner action |
| T427 | claim wording follows the evidence tier | wording rule fixed in `DESIGN_DECISION_2026-11-21.md`; manuscript and slides not rechecked in this pass (no new claim) | final wording after results |
| T428 | realism check on natural labels | not started | needs results |
| T429 | manuscript, slides, coverage, evidence index | no-change now (no result exists); mapping in section 7 | after results |
| T430 | source families in the coverage matrix | done for generation: `research/study_coverage.py` writes `study_coverage.json` (per group: categories, protocol, local view, unit-level compatibility, approved and provisional batch units, labels, cluster, exposure; 235 groups, 231 clusters); the manuscript matrix is updated with the results (T429) | none before results |
| T381 to T387 | semi-realistic ETL data, collective, conditional, cross-table, schema evolution, seasonal | not implemented as defined; `schema_drop`, `silent_corruption` and `stale_batch` cover parts of T386, T384 and T383 | scope decision with T425 |
| T431 to T437 | acquisition | done and re-verified (section 1) | none |

T416 to T422 are marked done in the checklist and in issue #131 on the evidence in this table (code,
tests, dated protocol, pilot files); T423 to T430, T381 to T387 and the acceptance criteria stay open.

## 3. Readiness of the batch study

- Pipeline, operators, detectors, alert budget, contaminated arm, per-source result files and the
  summary script exist and their tests pass (`research/tests/test_pipeline_batch*.py`).
- **The eight-series limit is removed for planning and loading.** `research/registry_units.py`
  resolves registry groups to the registered unit through the one rule of `batch_panel.py`, loads an
  eligible group's table with the cleaning of `pipeline_batch.load_table`, plans batches and
  evaluations (`plan`), states per group which units apply (`compatibility`) and runs the harness
  only with an authorization record naming the step and every group (`run`). `pipeline_batch.main`
  itself is unchanged and still iterates the eight UCI series. The unit is defined for a timestamped
  table with at least four continuous columns and 1,500 clean rows; the time column is found by
  content. Over the registry: **47 of 235 groups are eligible** (before the audit change and the view
  restoration: 40): C1 1, C2a 6, C2b 8, C3 21, C4 5, C6 0, C5 6. Exclusions of the other 188 groups, each counted once by its first recorded reason: no parseable time column 109, fewer than four continuous columns 35, nested layout 35, fewer than 1,500 clean rows 9; counting every recorded reason gives 111, 46, 35 and 11, which overlap. All 234 view files now match their registered digests (Update 33).
- Five of the 47 (`airquality_italy`, `candanedo_umons`, `seoul_bike`, `steel_korea`,
  `tetouan_power`) were seen by the plumbing pilot, whose full-profile outcome informed Amendment 1.
  They cannot be confirmatory evidence (variance pilot design section 7); the addendum proposes to
  use them in the pilot. Linked sets are in `linked_sets.json`; 47 groups form 46 clusters.
- No special treatment exists for any dataset; the audit applies one rule to every view.
- Statistics (`research/batch_statistics.py`, synthetic-tested): linked-cluster assignment, clustered
  seeded pilot draw that keeps linked groups and exposed groups apart, cluster bootstrap,
  one-way ICC, two-way variance components, paired-difference SD, factor-structure counts. Holm and
  `paired_sources` stay in `target_framework.py`. Not implemented: a REML mixed model (no
  `statsmodels` in the lock; over the eligible frame domain and schema family have 42 and 39
  singleton levels out of 44 and 41, so those effects are not estimable anyway).
- Remaining technical blockers: units for event logs, relational and nested sources (protocol
  amendment); key declarations for relational sources; a measured runtime.

## 4. T424 and the sample size

The pilot is mandatory under the registered protocol. Evidence: T424 requires the pilot and then "a
dated addendum before the confirmatory run"; the acceptance list requires the addendum to predate
the confirmatory run; `DESIGN_DECISION_2026-11-21.md` says the pilot replaces the assumed sigma;
`dataset_target_methodology.md` calls the targets planning figures that are not statistical
requirements. The reached acquisition minima are therefore not an alternative path, and no clause
waives the pilot. Authorization to run it and approval of its result are separate gates
(`variance_pilot_design.md` sections 8 and 12.5).

Inconsistencies the owner must resolve in a dated design addendum before the pilot:

1. Size and estimand: T424 says 24 to 48 sources at batch level; `variance_pilot_design.md` 12.5
   fixes 16 provenance groups for the unit-level families F1 to F5 (1 percent budget); the batch
   protocol uses a 5 percent budget. These are different studies (unit level and batch level), not
   one requirement; the 1 percent budget is not attainable with 16 to 20 clean validation batches.
   `batch_pilot_addendum_proposal.md` section 1 reconciles them.
2. Population: 47 eligible groups form 46 clusters; with five exposed ones in the pilot, a pilot of P
   clusters leaves 46 - P. A single contrast needs 34 sources at sigma 0.10 and delta 0.05 (45 for
   three, 90 for delta 0.03), so the frame meets it only for a pilot of about 12 and sigma at most
   0.10. Options (protocol amendment to further units, a narrower claim, or exploratory status) are a
   scientific decision for the owner (addendum section 5).
3. `pilot_plan_dry_run.json` predates Wave 28 (119 groups, seed 20261121) and belongs to the
   unit-level study. The batch pilot panel is drawn by `batch_statistics.py pilot-plan` once P, the
   per-category minimum and the seed are fixed. Not drawn here.

Prepared for the pilot: selection by `batch_statistics.draw_clustered_pilot` (seeded, provenance
only, linked groups together); estimators and intervals per design sections 6 and 10.6; recalibration by
`paired_sources` with Holm level alpha over family size (section 8); outputs are variance
components with intervals and a dated addendum; no new thresholds were introduced.

## 5. C1 surplus and the panel policy

All 52 C1 sources stay in the registry. The existing protocol settles: the unit of inference is the
provenance group; groups are averaged over mechanisms and seeds and weighted equally in the pooled
estimand; category claims are exploratory unless the eligible holdout is large enough; selection uses
provenance and structure only, never detector output; pilot groups do not return as confirmatory
evidence. It does not settle category weighting or equal category sizes, and equal sizes are not
required.

C1 is one curator and one schema family: effective groups 4.6 (rho 0.2) or 2.0 (rho 0.5). Equal
group weights let C1 supply 21 percent of participations while adding little independent
information. Proposal for approval: option 1 (all eligible groups) with random effects for domain,
schema family and curator and a category-balanced sensitivity estimate; a seeded subset of C1 is
unnecessary and would add a selection rule. Option 2 (a smaller primary panel) is acceptable only
with a seeded, provenance-only rule frozen before the pilot. For the batch study the question is
moot today: C1 has one eligible group.

## 6. Historical view reproducibility

`release_policy.json` requires reproduction for `cardio` (archive, two runs, an environment rebuilt
from the lock); it contains no requirement that every historical view be regenerated under the lock,
so there is no release blocker from the 16 files. Artifact reproduction is checked by SHA-256 of the
preserved files against `experimental_views.json` (all 16 match locally; generation provenance is
Update 27: `.venv`, pandas 3.1.1, byte-identical). Regeneration under pandas 3.0.6 gives the
differences of Update 27 and is not a reproduction; `bikeshare_capital` (175 cells) and
`flat_uci_864_C1` (6 cells, up to 5.4e-15 relative) are not strictly equivalent. Nothing was
rebuilt, restamped or replayed. If the owner later requires one environment for every artifact, that
is a policy change with a replay cost, not a silent waiver.

## 7. Runbook for the next authorized phase (commands exist; run in `etl-benchmark`)

Environment: `export PATH=/Users/theo/miniconda3/envs/etl-benchmark/bin:$PATH` (Python 3.11.17,
pandas 3.0.6). Do not use `.venv` for scientific runs. Run from `research/` for the scripts below.
Steps 1 to 5 read tables and provenance only and may be run during the freeze; steps 6 onward need
the named authorization.

1. View integrity (no detector): hash every file of `experimental_views.json` against its digest. A
   missing view is rebuilt by its own builder step into a scratch directory and compared before it
   is copied (never run `experimental_views.py` itself: its `main` rewrites the manifest).
2. Eligible frame: `python batch_panel.py` (about 3 minutes; writes `batch_eligibility.json`).
3. Coverage and compatibility: `python study_coverage.py --output FILE` (both studies, per group); `python relational_units.py --output FILE` (recomputes the declared foreign keys); `python registry_units.py compatibility --output FILE` and `python
   registry_units.py plan [--groups ...] [--compact] --output FILE` (batches per split and
   detector evaluations per group; 47 groups, 124,080 evaluations in the full profile).
4. Dependence: `python batch_statistics.py structure --output FILE` (clusters, exposure, levels of
   domain, schema family and curator).
5. Pilot panel (after the owner fixes P, M and S): `python batch_statistics.py pilot-plan --total P
   --minimum M --seed S [--reuse-exposed] --output FILE`; commit the file before any run.
6. Variance pilot (authorization record `{"step": "T424-pilot", "groups": [...]}`): `python
   registry_units.py run --step T424-pilot --authorization FILE --groups ... --output DIR [--compact]`
   (clean and contaminated arms; default seeds 42, 1, 2, 3, 4, `--seeds` for fixtures). Existing historical entry point, UCI series
   only: `python pipeline_batch.py --output DIR [--only IDS] [--compact]`.
7. Summary: `python pipeline_batch_summary.py --results DIR [--compact-results DIR2]`; its file
   naming is by UCI identifier, so registry results need the same summary keyed by group (not yet
   adapted: results of `registry_units.py run` are one JSON per group with the same `arms` layout).
8. Sample size: `batch_statistics.variance_components`, `icc_oneway`, `paired_difference_sd`,
   `cluster_bootstrap` on the per-group results, then `target_framework.paired_sources` with Holm.
   No CLI exists for this step; it is library code, tested on synthetic data.
9. Confirmatory panel and run: the holdout of step 5, same `run` command with the step name of the
   confirmatory authorization.
10. Verification and sealing: `make verify-fast verify-tools verify-types verify-faults verify-real
    verify-deep verify-reproduce verify-release`, then `python -m verification.claims archive --id
    <id> --platform "<machine>"`; slides with `make slides` and `make verify-slides`.
11. Governed mutation (`make verify-deep`, L1 80, L2 90, L3 95, L4 98 percent) only on the final
    release HEAD.

Scale, as arithmetic from the audit: per group 2 arms x 5 seeds x 8 mechanisms x 3 severities x 11
detectors (full profile) = 2,640 evaluations; 47 eligible groups give 124,080. The largest table has
437,744 rows and 45 columns (about 158 MB as float64); the 47 tables total 3.7 million rows, so one
group at a time fits in 16 GB. Result files are about 70 KB per source. Runtime is not measured in the
repository (pilot logs carry no timings), so no estimate is given; measure one small group after
authorization and plan the M4 Air budget from that. Groups are independent and parallelize by group;
`run` writes one atomic file per group but does not skip existing ones, so a resume is a rerun with
`--groups` for the missing ones. Stop conditions: any digest mismatch, any change to a frozen
partition or seed, a result file for a group outside the approved panel.

Manuscript and slides after results: benchmark description and coverage (235 groups, 47 batch
eligible), provenance and diversity (linked sets), methodology and operators, statistical analysis,
results, threats (eligible population, exposed pilot sources, controlled faults), reproducibility
(view provenance), conclusions, claim and evidence hashes. No edit was made now (`no-change`: no
result and no new claim exist).

## 8. Verification performed

- Views: every file listed in `experimental_views.json` hashed against its digest (234 views; 0
  missing, 0 mismatched after the restoration of Update 33). The 139 foreign keys of 32 relational
  views were recomputed on the local tables and equal the recorded counts.
- New code with tests (`etl-benchmark`; synthetic fixtures only, no registry source run through a
  detector): `registry_units.py`, `relational_faults.py`, `relational_units.py`,
  `batch_statistics.py`, `study_coverage.py`, `batch_panel.py` (time detection by content), plus a
  test of the finite-sample alert budget. A synthetic group runs end to end through the real
  `pipeline_batch.run_source` in `test_registry_units.py`.
- `research/tests`: **2,270 passed**, exit status 0. Ruff check and format pass on `research` and
  `verification`.
- Focused mutation on the final sources (case-sensitive volume, narrowed mutmut,
  `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` for that process only; no equivalent approved):
  `relational_faults` (L4, 98) 183 of 183; `batch_panel` (L3, 95) 418 of 418; `registry_units` (L3)
  415 of 419; `batch_statistics` (L3) 564 of 570 (5 survived, 1 timed out); `relational_units` (L3)
  306 of 314; `study_coverage` (L2, 90) 364 of 368. Survivors are disclosed: argument-default mutants
  that pandas, numpy and argparse treat identically, `flush` flags, and a loop mutant that does not
  terminate. Earlier scores below the thresholds led to restructuring and stronger tests, not to
  approvals.
- Mutation governance: `test_the_committed_weights_cover_exactly_the_mutating_modules` now passes.
  The 21 older research modules that had no shard weight were given the mutant count that mutmut
  recorded for them (`exit_code_by_key` of the generated mutants); the new modules were given the
  counts measured in this pass. Weights balance shards only; no score depends on them.
- Hosted CI on PR #132 failed at `test` because `pyarrow` (a declared dependency since the SURF
  Lisa view) was missing from the Linux hash lock; it was added with the hash of the
  `manylinux_2_28_x86_64` cp311 wheel of the pinned version (25.0.0, the version in the local
  environment). Not fixed: `tests/test_environment_lock.py::test_the_lock_pins_every_direct_dependency_and_python`
  fails because the macOS conda explicit lock also lacks `pyarrow`; regenerating that lock is a
  dependency decision for the owner.
- Governance tests of `tests/` selected by name (mutation, risk, policy, shard, environment, lock):
  1,178 passed, 1 failed (the macOS lock above).
- Type gate: `mypy==2.4.0` and `pandas-stubs==3.0.5.260914` (the CI pins) were installed in a scratch
  environment. The gate covers `src`, `experiments` and `verification`, none of which changed in
  code; it could not be reproduced locally (baseline entries differ under a non-CI environment, and the
  untracked `cardio-env-audit` directory is walked by mypy), so it is not claimed to pass. The hosted
  job is the reference.
- Not checked: manuscript and slide builds (no claim changed), the Linux deep campaign, any detector
  behaviour on a registry source, runtime on any registry group.

## 9. Decisions that need the owner (in order)

1. Approve or amend the batch-level pilot design addendum (`batch_pilot_addendum_proposal.md`
   section 9: contrasts, pilot size, per-category minimum, seed, exposed groups in the pilot, the
   population option, whether other units and the referential operator enter by amendment,
   mixed-model dependency, the Cincinnati link). Then authorize the variance pilot, naming step and
   groups.
2. Approve the sample size and the panel (C1 treatment, linked sets, exclusion of exposed pilot
   sources) only after the pilot result exists.
3. Lift the experiment freeze, scoped to named steps.
4. Authorize confirmatory execution.
5. Release certification (future, on the final HEAD).
