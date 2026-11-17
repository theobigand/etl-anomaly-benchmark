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

1. **One dependency environment for every profile (blocks the release gate).** The gate's last verdict is
   REJECTED for one reason only: the profiles ran different versions of result-affecting packages. FAST, FAULTS,
   DEEP, tools and reproduction install the latest resolvable packages (pandas 3.1.1, pyod 3.6.8) while REAL runs
   in the hash-locked environment (pandas 3.0.6, pyod 3.6.7), which is also the recorded lock. A gate that finds
   consistent versions that differ from the lock reports INCOMPLETE, not REJECTED. The choices:
   - **Align every profile on the lock (recommended).** pandas 3.0.6 is the only version under which the archived
     Cardio results replay numerically (the documented parsing difference), so the lock is the scientifically
     canonical environment. Cost: the 97 delegated records bind pandas 3.1.1 (three also pyod 3.6.8), so DEEP has to
     be rerun under the lock and every record revalidated or rebound before the validator accepts it.
   - **Re-record the lock at the versions the profiles ran.** Keeps the campaign and the records valid, but REAL then
     runs under pandas 3.1.1, where the Cardio replay is statistical and the test that expects a numerical match
     fails; relaxing that test is a scientific-claims decision, not a plumbing one.
   - **Leave it.** The gate stays REJECTED and no certification is claimed.
2. **Ratify or revoke the 97 delegated records**, in particular the 7 on the owner's word and the 2 device-dependent
   ones; the decision packet is `EQUIVALENCE_RATIFICATION_2026-11-17.md`. Nine units have no slack, so revoking any
   one of their records fails the unit. The last column of the table above gives the slack of every unit.
3. **Merge.** Authorise or refuse the squash merge recommended in section C. Nothing is merged automatically.

## C. Integration readiness

### Release verification, run end to end on hosted Linux

The full `verify-release` workflow was run five times on this branch (runs 44084515801, 44088269511, 44095792721,
44113451030 and 44143370017). It found six defects that no unit test could see, each fixed at its cause and covered
by a test: the REAL preflights compared the checked-out commit with the pull request merge commit; the aggregate
copied whole shard artifacts, with their mutated sources, into the checkout where policy validation took them for
repository sources; the 8.1 MB sharded DEEP envelope exceeded the 5 MB member limit of the evidence bundles; the
bundle carried the tracked equivalence document that its own allowlist refuses to unpack; the REAL profile collected
test modules that import PyTorch, which the hash-locked environment does not have; and the gate did not install the
dependency set that the sharded evidence binds. A seventh, a test that read a file outside the mutation sandbox,
failed every shard baseline in one earlier attempt and is fixed too.

The last run (44143370017, commit `8e50b699`) passes every profile: FAST, FAULTS, static typing and tools,
reproduction, REAL on hosted Linux (the three datasets are downloaded from their public sources and every checksum
matches the manifest) and DEEP as the 45-shard campaign. The gate then reports `REJECTED` with the three reasons of
decision 1 (pandas, pyod, and the difference from the lock), nothing else. The 107 reasons about stale published
figures of the first run are gone because the published run, a local run of the original global criterion, is now
marked historical with a note, the mechanism the repository already uses.

| Item | Status |
| --- | --- |
| Mutation campaign | PASS at `51ad0794`; see section A |
| Hosted CI | green on the head of every run above; it must be green on the final head |
| Official DEEP | the sharded campaign passes inside the release workflow, bundled without tracked files |
| Official release verification | runs end to end; verdict REJECTED on dependency-version consistency only; no CERTIFIED verdict is claimed |
| REAL | passes on hosted Linux from public sources with verified checksums; no private runner is needed |
| Independent review | provenance change: two rounds, PASS. Equivalence batch: two rounds, fixes applied. Accuracy review of this report: one round, fixes applied. Reviews are model reviews and are not human approval |
| Scientific integrity | Cardio and PCA records preserved; no archived result touched |
| PR contents | At `8e50b699`: 4,250 changed files and 70.8 MB: 3,309 alert-budget runs and 100 pool partitions (scientific artifacts), 104 mutation-evidence files, 384 probe scripts and logs and 129 notes (cited by the equivalence records and the probe notes), 150 tests, 39 source and infrastructure files, 32 manuscript and slide assets. Nothing was removed beyond two superseded notes and a process-id file, because everything else is cited by a record or an evidence file |
| Evidence retention | durable archive above; superseded interim notes removed; all cited probe notes and diagnostic archives kept |

**Git strategy.** The repository allows squash merging (`allow_squash_merge: true`) and `main` requires the `test`
and `faults` checks. The branch has 346 commits and 4,250 changed files. A squash keeps `main` readable; the
original history must be tagged on the branch before it is deleted (`delete_branch_on_merge` is off, so the branch
survives, but a tag is the durable reference). Evidence cites commits (`eb1d679`, `d4d21895`, `215da02`,
`51ad0794`, `8e50b699`); those identities live on in the tagged history. After a squash, hosted CI must pass on the
resulting commit, and any release claim needs a new release verification, because every shard binds its commit.
No provenance claim in the repository depends on the branch head surviving.

**Verdict: READY FOR OWNER REVIEW, not certified.** The mutation requirement is met with the stated exclusions and
limits, and the release machinery runs end to end. The release gate stays closed on decision 1, and PR #117 stays a
draft.
