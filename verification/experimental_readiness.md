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
| T423 | plumbing pilot on eight real series | partial: results for UCI 275, 360, 374, 560, 849, 851; 247 is not eligible (536 rows); 799 is eligible (371,122 rows) but has no result and no recorded reason | running 799 is a detector run on a benchmark source: needs the freeze lifted |
| T424 | variance pilot, then dated sample-size addendum | not run; design drafted | see section 4; needs authorization and a batch-level design addendum |
| T425 | relational sources and referential operator | not implemented; harness reads timestamped numeric tables only | implementation after the owner decides the unit for relational data (section 3) |
| T426 | search for real ETL incident data | searched 2026-11-25 (two public web queries): no labelled public corpus of pipeline incidents with a stated licence; only practitioner write-ups and postmortem summaries. Outcome: none found, no download made | partner outreach is an owner action |
| T427 | claim wording follows the evidence tier | wording rule fixed in `DESIGN_DECISION_2026-11-21.md`; manuscript and slides not rechecked in this pass (no new claim) | final wording after results |
| T428 | realism check on natural labels | not started | needs results |
| T429 | manuscript, slides, coverage, evidence index | no-change now (no result exists); mapping in section 7 | after results |
| T430 | source families in the coverage matrix | started: `research/batch_panel.py` and `evidence/dataset_registry_v2/batch_eligibility.json` count eligible groups per category | link to families in the final matrix after the panel is approved |
| T381 to T387 | semi-realistic ETL data, collective, conditional, cross-table, schema evolution, seasonal | not implemented as defined; `schema_drop`, `silent_corruption` and `stale_batch` cover parts of T386, T384 and T383 | scope decision with T425 |
| T431 to T437 | acquisition | done and re-verified (section 1) | none |

T416 to T422 are marked done in the checklist and in issue #131 on the evidence in this table (code,
tests, dated protocol, pilot files); T423 to T430, T381 to T387 and the acceptance criteria stay open.

## 3. Readiness of the batch study

- Pipeline, operators, detectors, alert budget, contaminated arm, per-source result files and the
  summary script exist and their tests pass (`research/tests/test_pipeline_batch*.py`).
- **Dataset selection is the blocking gap.** `pipeline_batch.main` iterates only the eight
  `chrono_injected.TIME_SPECS` identifiers; no CLI runs a registry group. The unit is defined for a
  timestamped table with at least four continuous columns and 1,500 clean rows. Applied to the
  registry by `research/batch_panel.py` (no detector; time column found by name and parse, so a
  lower bound): **40 of 235 groups are eligible** (C1 1, C2a 4, C2b 7, C3 20, C4 3, C5 5, C6 0).
  Others fail for: no parseable time column 114, too few continuous columns 35, nested or non-CSV
  layout 27, too few rows 9, view not built locally 10. Ten views (for example `sffd_fire_incidents`,
  `wa_ev_population`, `nasa_omni_solar_wind`) have registry digests but no local file and must be
  materialised and digest-checked before the audit is final.
- Five of the 40 (`airquality_italy`, `candanedo_umons`, `seoul_bike`, `steel_korea`,
  `tetouan_power`) were seen by the plumbing pilot, whose full-profile outcome informed Amendment 1.
  They should stay out of any confirmatory panel (pilot sources are not reusable, variance pilot
  design section 7).
- No special treatment exists for any dataset; the audit applies one rule to every view.
- Statistical analysis for the batch study: `pipeline_batch_summary.py` is descriptive (hypotheses
  B1 to B5). Holm and `paired_sources` exist in `research/target_framework.py`; no code yet fits the
  random-effects model of the pilot design or the cluster bootstrap. That is implementation still to
  do, and only testable on synthetic data until the freeze is lifted.
- Technical blockers: (1) the registry loader for the batch harness; (2) the unit for event logs,
  relational and nested sources (T425); (3) the statistical model code; (4) the ten unbuilt views and
  five local view files whose bytes differ from the committed digests (`sncf_tgv_regularite`,
  `wri_power_plants`, `zen_blazar_flares`, `zen_dk_district_heating`, `zen_queensland_petrol`; local
  rebuilds of 2026-11-22, git-ignored, committed digests untouched).

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
   fixes 16 provenance groups for the unit-level families F1 to F5 (1 percent budget) and defers 24;
   `pipeline_batch_faults.md` uses a 5 percent budget. The batch study needs its own contrasts.
2. Population: with 40 eligible groups (lower bound, 35 after removing the five exposed ones), a
   pilot of 24 to 48 consumes most or all of them, so pilot and confirmatory sets cannot be disjoint,
   and the one-comparison need (34 sources at sigma 0.10, delta 0.05; 45 for three comparisons; 87
   for delta 0.03) is not met by a holdout of about 20. Options: extend the unit to other layouts
   (protocol amendment), narrow the batch claim to the stratum it supports, or treat it as
   exploratory. Choosing among them is a scientific decision, not made here.
3. `pilot_plan_dry_run.json` predates Wave 28 (119 groups, seed 20261121). It must be redrawn on the
   batch-eligible frame with a seed the owner freezes. Not redrawn here, because the frame itself is
   undecided.

Prepared for the pilot: selection by `draw_pilot` or `plan_pilot` (seeded, provenance only, no
detector output); estimators and intervals per design sections 6 and 10.6; recalibration by
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
pandas 3.0.6). Do not use `.venv` for scientific runs.

0. Preconditions: owner lifts the freeze for the named step; digest-check views; build the ten
   missing views one builder at a time into a scratch directory and compare with the manifest.
1. Eligible frame: `python research/batch_panel.py` (about 3 minutes, reads views, no detector).
2. Panel: draw with `target_framework.plan_pilot` on the batch-eligible frame (to be wrapped in a
   dated, committed script once the seed and size are approved; no CLI exists today).
3. Pilot and confirmatory runs: today only `python research/pipeline_batch.py --output DIR [--only
   IDS] [--compact]` (UCI TIME_SPECS only). Registry support is the missing loader of section 3.
4. Summary: `python research/pipeline_batch_summary.py --results DIR [--compact-results DIR2]`.
5. Statistics: `research/target_framework.py` (`paired_sources`, `holm_adjust`); the mixed-model and
   cluster-bootstrap code is still to be written and tested on synthetic data.
6. Verification and sealing: `make verify-fast verify-tools verify-types verify-faults verify-real
   verify-deep verify-reproduce verify-release`, then `python -m verification.claims archive --id
   <id> --platform "<machine>"`; slides with `make slides` and `make verify-slides`.
7. Governed mutation (`make verify-deep`, L1 80, L2 90, L3 95, L4 98 percent) only on the final
   release HEAD.

Size, as arithmetic: per source 8 mechanisms x 3 severities x 5 seeds x 2 arms = 240 evaluations,
each scoring up to 16 detectors on about 40 test batches. Result files are about 70 KB per source
(pilot: 432 KB for six). Runtime is not measured in the repository (pilot logs have no timings);
measure on one small source after authorization before planning the M4 Air (16 GB) budget. Sources
are independent, so they parallelize by source; `main` writes one atomic file per source but does
not skip existing ones, so resume is a rerun with `--only` for the missing identifiers. Stop
conditions: any digest mismatch, any change to a frozen partition or seed, a result file for a
source outside the approved panel.

Manuscript and slides after results: benchmark description and coverage (235 groups, 40 batch
eligible), provenance and diversity (linked sets), methodology and operators, statistical analysis,
results, threats (eligible population, exposed pilot sources, controlled faults), reproducibility
(view provenance), conclusions, claim and evidence hashes. No edit was made now (`no-change`).

## 8. Verification performed in this pass

- Reports regenerated and compared: `readiness.json`, `readiness_facts.json`, `source_attributes.json`
  and `target_framework.json` identical.
- 460 view files hashed against the manifest: 5 local mismatches, 10 views not built locally.
- Record-level checks listed in `dataset_acquisition_report.md` Update 32.
- New `research/batch_panel.py` with `research/tests/test_batch_panel.py` (25 tests), L3 entry in
  `verification/mutation_risk_policy.json`. Focused mutation (case-sensitive volume, narrowed
  mutmut, `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` for that process only): 420 of 420 mutants
  killed, no equivalent approved (a first run scored 80.4 percent and led to simplifying the module
  and strengthening the tests, not to approvals).
- Full `research/tests` run in `etl-benchmark`: exit status 0 (the per-test count was not printed).
  `ruff check` and `ruff format --check` pass on `research` and `verification`; the mutation
  governance tests in `tests/` pass.
- Not checked: manuscript and slide builds, the type gate, the Linux deep campaign, any detector
  behaviour, the ten unbuilt views.

## 9. Decisions that need the owner

1. Authorize the variance pilot (and its date), after approving the batch-level design addendum
   (size, estimand, population option from section 4).
2. Approve the sample size and the panel (C1 treatment, linked sets, exclusion of exposed pilot
   sources) only after the pilot result exists.
3. Lift the experiment freeze, scoped to named steps.
4. Authorize confirmatory execution.
5. Release certification (future, on the final HEAD).
