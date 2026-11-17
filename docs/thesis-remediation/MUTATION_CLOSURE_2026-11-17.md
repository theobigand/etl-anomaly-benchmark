# Mutation closure report, 2026-11-17

Canonical closing record of the risk-tiered mutation work of PR #117 / issue #116. It replaces the
interim continuation and pending-regression notes. Earlier packets, probes and measurements stay in
place as the evidence that individual records cite. Nothing here certifies a release: the release
gate is closed (section C) and the pull request stays a draft.

## A. Compliance

### Official campaign

| Item | Value |
| --- | --- |
| Workflow | `mutation-shards`, run [44045848118](https://github.com/theobigand/etl-anomaly-benchmark/actions/runs/44045848118), 45 shards, `fresh_mutants=true` |
| Tested commit | `51ad0794fbbe6ccaa752104abc08f4d63d4ce732` (`source.revision` of `deep-evidence.json`). That file is marked `worktree_dirty: true`: the workflow writes the aggregation output into the checkout before it builds the evidence, and `verification/release.py` rejects any profile marked dirty. The 45 shard digests still bind every tracked file |
| Environment | Linux-x86_64-glibc-2.43, Python 3.11.18, pandas 3.1.1, numpy 2.4.6, scikit-learn 1.9.1, pyod 3.6.8, torch 2.15.0+cpu, mutmut 3.8.0, pytest 9.1.1 |
| Result | `PASS`, `execution_bound: true` (controller proof), native exit code 0, no missing, unchecked or errored mutant |
| Coverage of the inventory | 100 classified units: 97 with mutants, 3 without function bodies (`src/etl_benchmark/__init__.py`, `config.py`, `quality/__init__.py`) |
| Mutants | 35,237 eligible: 34,768 killed, 463 survived, 6 timeouts (a timeout is never counted as a kill) |
| Archive | `evidence/final-campaign-44045848118.tar.gz`, SHA-256 `e74425daf0024fcba9e7340720988da209e698501ed3c0c25b9f487bc069052d`; inside, `mutation-campaign.json` `566c5bcd...7551`, `deep-evidence.json` `578cf19b...02bc`, `shard-plan.json` `235015ca...3761` and the 45 shard manifests |

GitHub artifacts expire after 90 days; the archive is the durable copy.

### Results by risk level

| Level | Units | Threshold | Killed / eligible | Raw | Adjusted |
| --- | ---: | ---: | ---: | ---: | ---: |
| L2 | 3 | 90% | 10 / 10 | 100.00% | 100.00% |
| L3 | 18 | 95% | 5,472 / 5,545 | 98.68% | 98.68% |
| L4 | 79 | 98% | 29,286 / 29,682 | 98.67% | 99.00% |

Every unit meets its own threshold; no aggregate compensates for a unit. Thresholds, levels and the 12 owner
reclassifications of L4 to L3 are unchanged.

### Units that pass only through accepted equivalences

101 mutants are excluded in 21 units: 4 owner records of 2026-11-11 (LSTM) and 97 records of 2026-11-17. Of the 97,
90 rest on a recorded technical argument and 7 on the owner's word (below); with the four LSTM records, 94 exclusions
carry an argument. 20 units are below their threshold raw and pass only after exclusions. The 21st,
`experiments/generate_synthetic.py` (90/91, 98.90% raw), carries one analysis-backed exclusion it does not need.
Nothing else is excluded: 362 survivors in passing units remain counted. The last column is how many records of the
unit could be revoked, one at a time, before it fell below its threshold (0 means every excluded mutant is needed).

| Unit | Raw | Excluded | Adjusted | Revocable |
| --- | --- | ---: | --- | ---: |
| `experiments/generate_synthetic.py` | 90/91 (98.90%) | 1 | 90/90 (100.00%) | 1 |
| `experiments/run_severity.py` | 322/329 (97.87%) | 3 | 322/326 (98.77%) | 2 |
| `research/injection.py` | 327/336 (97.32%) | 4 | 327/332 (98.49%) | 1 |
| `research/lstm_detector.py` | 368/377 (97.61%) | 4 | 368/373 (98.66%) | 2 |
| `research/multi_schema.py` | 1069/1093 (97.80%) | 16 | 1069/1077 (99.26%) | 13 |
| `research/normalise.py` | 191/197 (96.95%) | 4 | 191/193 (98.96%) | 1 |
| `research/pool_chrono.py` | 306/316 (96.84%) | 7 | 306/309 (99.03%) | 3 |
| `research/pool_preprocessing.py` | 241/248 (97.18%) | 6 | 241/242 (99.59%) | 3 |
| `research/typed_benchmark.py` | 175/180 (97.22%) | 4 | 175/176 (99.43%) | 2 |
| `src/etl_benchmark/load.py` | 13/14 (92.86%) | 1 | 13/13 (100.00%) | 0 |
| `src/etl_benchmark/quality/_torch_models.py` | 58/65 (89.23%) | 6 | 58/59 (98.31%) | 0 |
| `src/etl_benchmark/quality/autoencoder.py` | 112/117 (95.73%) | 3 | 112/114 (98.25%) | 0 |
| `src/etl_benchmark/quality/base.py` | 30/31 (96.77%) | 1 | 30/30 (100.00%) | 0 |
| `src/etl_benchmark/quality/deep.py` | 60/62 (96.77%) | 1 | 60/61 (98.36%) | 0 |
| `src/etl_benchmark/quality/drift.py` | 120/129 (93.02%) | 7 | 120/122 (98.36%) | 0 |
| `src/etl_benchmark/quality/gx.py` | 90/98 (91.84%) | 8 | 90/90 (100.00%) | 1 |
| `src/etl_benchmark/quality/ml.py` | 243/259 (93.82%) | 12 | 243/247 (98.38%) | 0 |
| `src/etl_benchmark/quality/rules.py` | 112/119 (94.12%) | 7 | 112/112 (100.00%) | 2 |
| `src/etl_benchmark/quality/window_drift.py` | 228/233 (97.85%) | 2 | 228/231 (98.70%) | 1 |
| `src/etl_benchmark/quality/windows.py` | 54/57 (94.74%) | 2 | 54/55 (98.18%) | 0 |
| `verification/mutation_scope.py` | 240/246 (97.56%) | 2 | 240/244 (98.36%) | 0 |

### Equivalence decisions and their limits

- **Authority.** The owner delegated equivalence verdicts to the assistant on 2026-11-16 and asked that a mutant
  that cannot be shown to differ be treated as equivalent. Records are in `verification/mutation_equivalence.json`
  under `sole_author_owner_review`; this is not independent peer review. The owner can revoke any record.
- **Minimal exclusion.** Analysis-backed records are accepted first. A record on the owner's word is accepted only
  while a unit is still below its threshold: 7 records (state read before fitting, use after a failed fit, an
  argument no caller passes), in `ml.py` (5 of them, the largest dependence on this basis), `_torch_models.py` and
  `autoencoder.py`. They are labelled INCONCLUSIVE in the first assessment of each record.
- **Environment-dependent.** Two `_torch_models.py` records (`.to(None)`) are equivalent only on the CPU-only
  PyTorch build of the campaign. The same mutants are killed on an Apple MPS device. The record binds
  `torch 2.15.0+cpu` and does not carry over to an accelerator campaign.
- **Review.** Two separate-context model reviews of the batch (their texts are not archived; findings and dispositions are those listed here). Round 1 found four accepted mutants that a test could
  kill; they were removed and covered by tests. Round 2 found one false citation and wording defects, all fixed.
  No third round was run: the remaining fixes were textual and the official validator accepted the result.
- **Known inconsistency.** The 2026-11-11 LSTM records keep `replace=None` and `astype(None)` as inconclusive while
  later records accept the same operators on a verified argument. The LSTM choice is the more conservative one.
- Five survivors of `verification/mutation_shards.py` are equivalent by analysis (`allow_nan=None`, an unused default,
  two length boundaries of an always-non-empty list, a falsy initial flag). They need no record: the unit passes raw
  at 1551/1556 (99.68%).

### Behavioural gaps closed by tests (not by exclusion)

- Six demonstrated differences were confirmed killed natively on Linux (`ml.py` x2, `window_drift.py`,
  `temporal_decision.py`, `multi_schema.py` x2).
- 107 survivors of `verification/mutation_shards.py`: the diagnostic and command line of the sharding tool were
  under-tested after the unit grew from 1,105 to 1,556 mutants: 112 of its 1,556 mutants survived the first native measurement (1,444 killed, 92.8%), and 107 of those 112 are now killed. They are
  now pinned by contract tests.
- Four mutants first judged equivalent were not: two on the float64 score dtype of `PyODDetector.score` (the deep
  detectors return float32 without it), the tie-break at exactly zero correlation, and a deprecated pandas frequency
  alias. Each is now killed by a test that fails on the mutant.
- Three timeouts of `generate_synthetic.py` were pytest computing a diff of two large CSV strings; the test now
  compares a boolean. Production code was not changed to improve a score.
- Six timeouts remain, all counted as non-kills: `injection.py` x3, `multi_schema.py` x2,
  `mutation_cache.py` x1 (an infinite loop in a mutated breadth-first search, a real detection by hang).

### Provenance and reproducibility

- Every shard is bound to one commit, the digest of every Git-tracked file (new `inputs_sha256`), the test tree,
  the mutation configuration, the runtime and a controller execution proof. A different value in any shard rejects
  the aggregation.
- The binding now names the platform family, architecture and C library, not the hosting runner. Two earlier full
  campaigns failed to aggregate because about a tenth of the shards ran on AWS runners whose kernel string differed
  from the Azure runners. Limits that remain: untracked, ignored and external data are not bound; the digest is
  taken when the manifest is built; tests run from the ignored `mutants/` copy tree, so campaign evidence must be
  produced with `fresh_mutants=true` (no manifest records freshness: check the run's inputs); the workflow installs
  unpinned dependency versions, and the validator rejects every accepted record if a pinned package moves.
- Earlier ledgers are superseded and not summed with this campaign. Measurements of one source of `ml.py` differ with the
  environment: 259/259 in the 2026-11-07 campaign (82 of the 91 L4 modules), 238/259 then 239/259 in the 2026-11-13
  mixed-environment ledger, 241/259 at the first native Linux measurement (run 44013883170, not archived), 243/259 in
  the final campaign.
- Scientific integrity: the documented Cardio CSV parsing discrepancy and the synthetic PCA numerical instability
  are preserved as described; no archived numerical result or evidence was rewritten.

## B. Owner decisions outstanding

Equivalence verdicts are no longer pending. What only the owner can decide, by consequence:

1. **Ratify or revoke the 97 delegated records**, in particular the 7 on the owner's word and the 2 device-dependent
   ones. Nine units have no slack, so revoking any one of their records fails the unit: `load.py`, `base.py`, `deep.py`,
   `drift.py`, `mutation_scope.py`, `windows.py` (98.18%), `autoencoder.py` (98.25%), `_torch_models.py` (98.31%) and
   `ml.py` (98.38%). The last column of the table gives the slack of every unit.
2. **How DEEP is certified.** The release workflow's `release-deep` job runs `make verify-deep`, one job of 35,237
   mutants with a 180-minute limit. The sharded campaign took about 1 h 40 on 45 parallel runners. Either accept the
   sharded `deep-evidence.json` (kind `deep`, controller-proof) as the DEEP input of the release gate, which needs a
   workflow change (the evidence is built after the aggregation wrote into the checkout and is marked dirty, which the
   release script rejects), or run a different campaign shape. No workflow was changed to make a gate pass.
3. **REAL evidence.** The release gate also needs a runner holding the research datasets; none is available.
4. **Merge.** Authorise or refuse the squash merge recommended in section C. Nothing is merged automatically.

## C. Integration readiness

| Item | Status |
| --- | --- |
| Mutation campaign | PASS at the commit above; see section A |
| Hosted CI | green on `51ad0794` (run 44042429763: `test`, `faults`, `slides`); it must be green again on the final head |
| Official DEEP | sharded evidence PASS but marked `worktree_dirty`; the release workflow's single-job DEEP not run (cannot fit its limit) |
| Official release verification | not run, so the gate stays closed: no CERTIFIED verdict is claimed |
| Independent review | provenance change: two rounds, PASS. Equivalence batch: two rounds, fixes applied, no third round. Reviews are model reviews and are not human approval |
| Scientific integrity | Cardio and PCA records preserved; no archived result touched |
| Evidence retention | durable archive above; superseded interim notes removed; 3,310 alert-budget JSON files, the cited probe notes and all diagnostic archives kept |

**Git strategy.** The repository allows squash merging (`allow_squash_merge: true`). The branch has 321+ commits
and 4,000+ changed files, 3,310 of which are scientific alert-budget artifacts. A squash keeps `main` readable;
the original history stays reachable on the branch and must be kept as a tag before the branch is deleted.
Evidence cites commits (`eb1d679`, `d4d21895`, `215da02`, `51ad0794`); those identities live on in the tagged
history. After a squash the following must be rerun on the resulting commit: hosted CI, and a campaign for any
future release claim, because every shard binds its commit. No provenance claim in the repository depends on the
branch head surviving.

**Verdict: READY FOR OWNER REVIEW, not certified.** The mutation requirement is met with the stated exclusions and
limits. The release gate is closed for the reasons in B2 and B3, and PR #117 stays a draft.
