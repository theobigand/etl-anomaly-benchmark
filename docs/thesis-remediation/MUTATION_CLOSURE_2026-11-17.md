# Mutation closure report, 2026-11-17 (status as of 2026-11-18)

Canonical closing record of the risk-tiered mutation work of PR #117 / issue #116. It replaces the
interim continuation and pending-regression notes. Earlier packets, probes and measurements stay in
place as the evidence that individual records cite. The section "Current status" is the one
authoritative statement of where the work stands; sections A to C give the evidence behind it and keep
the earlier results as history, marked as such.

## Current status

| Item | State |
| --- | --- |
| Official release verdict | **CERTIFIED**, workflow `verify-release`, run [44253806652](https://github.com/theobigand/etl-anomaly-benchmark/actions/runs/44253806652), `workflow_dispatch` on this branch, 2026-11-18 |
| Certified source revision | `5e57228e3fa547df76a83ed32d00e3c1f6889d9a`. The verdict is about that revision |
| Profiles | all seven required profiles PASS (fast, deep, faults, real, tools, types, reproduction), all `github-hosted`; `reasons: []` |
| Attestation | `ci-run:44253806652 (not independently attested)`. It says where the evidence was produced, not that anyone attested it. Policy-deferred items stay deferred: independent attestation, and the recorded environment lock covering osx-arm64 only (issue 45) |
| Certified environment | Linux-x86_64-glibc-2.43, Python 3.11.18, pandas 3.0.6, numpy 2.4.6, scikit-learn 1.9.1, pyod 3.6.7, scipy 1.17.1, great-expectations 1.24.0, torch 2.15.0+cpu, mutmut 3.8.0. Installed from the hash-locked Linux files `verification/environment/linux-x86_64-py311*.lock.txt`. The local macOS conda environment (torch 2.14.1 here) is not this environment |
| Mutation result | 35,253 eligible mutants: 34,786 killed, 463 survived, 4 timeouts (never counted as kills). All 97 units with mutants meet their own threshold. L2 100.00%, L3 98.71%, L4 98.67% raw and 99.01% adjusted |
| Exclusions | 101 accepted equivalences in 21 units: 4 LSTM records decided by the owner on 2026-11-11 and 97 delegated records of 2026-11-17 (88 analysis-backed, 7 on the owner's word, 2 CPU-only). Nine units have no slack: revoking any one of their records fails the unit |
| Branch | `feat/risk-tiered-mutation-policy`, 0 commits behind `main`, mergeable without conflict, draft. Commits after the certified revision change documentation and archived evidence only (section C) |
| Owner decisions outstanding | records of the 2026-11-17 delegation to ratify or revoke (the nine records of section B, in particular the two that touch a silent failure), squash merge, tag publication |
| Not claimed | independent scientific certification; certification of any revision other than `5e57228`; certification of the squash commit |

## A. Compliance

### Official campaign (certified run)

| Item | Value |
| --- | --- |
| Workflow | the DEEP profile of `verify-release` run 44253806652: the `mutation-shards` campaign, 45 shards, `fresh_mutants: true` (fixed in the workflow), `execution_bound: true` (controller proof), native exit code 0, no missing, unchecked or errored mutant |
| Tested commit | `5e57228e3fa547df76a83ed32d00e3c1f6889d9a`; `worktree_dirty: false` |
| Context digests | `inputs_sha256` `6399f1c7...cd05`, `tests_sha256` `85e00f16...cef9`, `configuration_sha256` `c85bfa2c...3181` |
| Coverage of the inventory | 100 classified units: 97 with mutants, 3 without function bodies (`src/etl_benchmark/__init__.py`, `config.py`, `quality/__init__.py`) |
| Archive | `evidence/release-44253806652/mutation-campaign.tar.gz` (SHA-256 `76ba28b1d17eb4ce7fe31ea3d48aa0418a0b25f4c4144abda919c601b1d263fb`): `deep-evidence.json` `121af895...892b`, `mutation-campaign.json` `23c820ac...34a0`, `shard-plan.json` `235015ca...3761`, 45 shard manifests; `evidence/release-44253806652/evidence-deep.tgz` (SHA-256 `cef4ab93a170b84fda25bc1c55327ac5ce97ad0147aaaa0d14d3fc9453945491`) is the bundle the gate consumed; `evidence/release-44253806652/release.json` (SHA-256 `77dd9be0e79543914ca1ed4a538163ed9186ea4d77a6813e1b02393a2a9df152`) is the immutable gate report |

GitHub artifacts expire after 90 days; the archives above are the durable copy. The two tarballs were added
after the run, from its artifacts, and `release.json` was not changed.

### Results by risk level

| Level | Units | Threshold | Killed / eligible | Raw | Adjusted |
| --- | ---: | ---: | ---: | ---: | ---: |
| L2 | 3 | 90% | 10 / 10 | 100.00% | 100.00% |
| L3 | 18 | 95% | 5,489 / 5,561 | 98.71% | 98.71% |
| L4 | 79 | 98% | 29,287 / 29,682 | 98.67% | 99.01% |

Every unit meets its own threshold; no aggregate compensates for a unit. Thresholds, levels and the 12 owner
reclassifications of L4 to L3 are unchanged.

### Units that pass only through accepted equivalences

101 mutants are excluded in 21 units. 20 units are below their threshold raw and pass only after exclusions. The 21st,
`experiments/generate_synthetic.py` (90/91, 98.90% raw), carries one analysis-backed exclusion it does not need.
Nothing else is excluded: 362 survivors in passing units remain counted. The last column is how many records of the
unit could be revoked, one at a time, before it fell below its threshold (0 means every excluded mutant is needed).

| Unit | Raw | Excluded | Adjusted | Revocable |
| --- | --- | ---: | --- | ---: |
| `experiments/generate_synthetic.py` | 90/91 (98.90%) | 1 | 90/90 (100.00%) | 1 |
| `experiments/run_severity.py` | 322/329 (97.87%) | 3 | 322/326 (98.77%) | 2 |
| `research/injection.py` | 327/336 (97.32%) | 4 | 327/332 (98.49%) | 1 |
| `research/lstm_detector.py` | 368/377 (97.61%) | 4 | 368/373 (98.66%) | 2 |
| `research/multi_schema.py` | 1071/1093 (97.99%) | 16 | 1071/1077 (99.44%) | 15 |
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
  Nothing in the review of 2026-11-18 changed a record, a verdict or a threshold.
- **Minimal exclusion.** Analysis-backed records are accepted first. A record on the owner's word is accepted only
  while a unit is still below its threshold: 7 records (state read before fitting, use after a failed fit, an
  argument no caller passes), in `ml.py` (5 of them), `_torch_models.py` and `autoencoder.py`.
- **Environment-dependent.** Two `_torch_models.py` records (`.to(None)`) are equivalent only on the CPU-only
  PyTorch build of the campaign. They bind `torch 2.15.0+cpu`; the validator rejects the whole evidence for any
  other torch string, and likewise for any other pandas, scipy, great-expectations or pyod version named by a
  record (probe: `evidence/final-review-2026-11-18/validator-binding-probe-output.txt`).
- **Known inconsistency with the LSTM records.** The five 2026-11-11 records that keep `replace=None` and
  `astype(None)` inconclusive are counted as survivors, while the delegated records accept the same operators on
  exact versions. The conservative LSTM decisions stand; `EQUIVALENCE_RATIFICATION_2026-11-17.md` section 4 explains
  which differences are contracts and which are the standard of proof.
- **Review.** Two earlier separate-context model reviews of the batch (texts not archived) found four mutants that a
  test could kill, removed and covered by tests, and corrected wording. They are model reviews, not human approval.
  On 2026-11-18 no new model review was run: the seven weaker records, the two CPU-only records, the record
  bindings and the certified evidence were re-checked by direct probes and deterministic comparisons
  (`evidence/final-review-2026-11-18/`). That check is the assistant's, not independent.
- Five survivors of `verification/mutation_shards.py` are equivalent by analysis (`allow_nan=None`, an unused default,
  two length boundaries of an always-non-empty list, a falsy initial flag). They need no record: the unit passes raw.

### Behavioural gaps closed by tests (not by exclusion)

- Six demonstrated differences were confirmed killed natively on Linux (`ml.py` x2, `window_drift.py`,
  `temporal_decision.py`, `multi_schema.py` x2).
- 107 survivors of `verification/mutation_shards.py` (the diagnostic and command line of the sharding tool, under-tested
  after the unit grew from 1,105 to 1,556 mutants) are now pinned by contract tests.
- Four mutants first judged equivalent were not: two on the float64 score dtype of `PyODDetector.score`, the tie-break
  at exactly zero correlation, and a deprecated pandas frequency alias. Each is killed by a test that fails on the mutant.
- Three timeouts of `generate_synthetic.py` were pytest computing a diff of two large CSV strings; the test now
  compares a boolean. Production code was not changed to improve a score.
- Four timeouts remain in the certified run, all counted as non-kills: `injection.py` x3 and `mutation_cache.py` x1
  (an infinite loop in a mutated breadth-first search, a real detection by hang).

### Provenance and reproducibility

- Every shard is bound to one commit, the digest of every Git-tracked file (`inputs_sha256`), the test tree, the
  mutation configuration, the runtime and a controller execution proof. A different value in any shard rejects the
  aggregation. The binding names the platform family, architecture and C library, not the hosting runner.
- The runtime packages the validator compares with each record now include scipy and great-expectations besides torch
  (commit `d3abc54`); the 2026-11-17 caveat that the validator could not enforce them no longer applies. One
  dependency stays unbound: matplotlib backs the pixel-identity argument of three `run_severity.py` records
  (`render__mutmut_24`, `_27`, `_28`); it is pinned in the Linux lock (3.11.2) but is not a captured package.
- Limits that remain: untracked, ignored and external data are not bound; the digest is taken when the manifest is
  built; tests run from the ignored `mutants/` copy tree, so campaign evidence needs `fresh_mutants=true`.
- Measurements of one source of `ml.py` differ with the environment (259/259 in the 2026-11-07 campaign, 238 and 239/259
  in the 2026-11-13 mixed-environment ledger, 241/259 at the first native Linux measurement, 243/259 in the
  campaigns of 2026-11-17 and 2026-11-18). Earlier ledgers are superseded and are not summed.
- Scientific integrity: the documented Cardio CSV parsing discrepancy (numerical replay only under pandas 3.0.6) and the
  synthetic PCA numerical instability are preserved as described; no archived numerical result was rewritten.

### Earlier campaign (history, superseded as the current result)

Run `mutation-shards` [44045848118](https://github.com/theobigand/etl-anomaly-benchmark/actions/runs/44045848118),
45 shards, commit `51ad0794fbbe6ccaa752104abc08f4d63d4ce732`, Linux, pandas 3.1.1, pyod 3.6.8, torch 2.15.0+cpu,
`PASS`: 35,237 eligible, 34,768 killed, 463 survived, 6 timeouts; L3 98.68%, L4 98.67% raw and 99.00% adjusted.
Its `deep-evidence.json` was marked `worktree_dirty: true`, which the release gate rejects. The 97 delegated records of
that run bound pandas 3.1.1; they were rebound to the locked versions in `5e57228` with arguments and verdicts
unchanged. The archive `evidence/final-campaign-44045848118.tar.gz` (SHA-256
`e74425daf0024fcba9e7340720988da209e698501ed3c0c25b9f487bc069052d`) is kept. A separate measurement of the mutants under
the lock (run 44179716383, commit `d3abc54`, `evidence/lock-measurement-44179716383/`) found 35,253 mutant identities
with the same totals as the certified run (34,786 killed, 463 survived, 4 timeouts); that run's own aggregation
failed by design because the records still bound pandas 3.1.1 at that commit.

## B. Owner decisions outstanding

Technical findings and per-record reasoning are in `EQUIVALENCE_RATIFICATION_2026-11-17.md` (sections 1, 2 and 6).
Nothing is ratified or revoked on the owner's behalf. In short:

1. **Seven records on the owner's word.** Five are defensible under the documented contract (private or internal
   classes, state that no public detector exposes): `PaddedAE1SVM.fit__mutmut_11`,
   `ReconstructionModel.__init____mutmut_4`, `PyODDetector.__init____mutmut_4`,
   `TailProbabilityModel.__init____mutmut_3` and `_5`. Two are not demonstrably outside supported use and need the
   owner's judgment: `PCAReconstruction.__init____mutmut_9` and `TailProbabilityModel.__init____mutmut_10`. After a fit
   that fails on a contamination outside 1e-4 to 0.5 (the range `registry.py` enforces), `ECODDetector`,
   `COPODDetector` and `PCADetector` return all-False flags instead of "not fitted", because `PyODDetector.fit` assigns
   `_model` before the fit completes; the mutants would raise `TypeError` instead. The original is the one with the
   defect. Revoking either one fails `ml.py` (243/248 = 97.98%, under 98%) and therefore the DEEP profile.
2. **Two CPU-only records.** Keep strictly as exclusions bound to `torch 2.15.0+cpu`, or revoke. They are not
   equivalences: the public `estimator_kwargs` accept other devices and the mutants are killed on Apple MPS. Revoking
   one fails `_torch_models.py` (58/60 = 96.67%). A CPU-only killer exists (a `meta` device, checked locally on torch
   2.14.1) and would remove the dependence on the build; adding it changes the test tree and so needs a new campaign.
3. **The other 88 delegated records.** Technical recommendation: ratify. Integrity checks pass (section C); the one
   known limit is the unbound matplotlib version of three records.
4. **LSTM consistency.** Recommendation: leave the 2026-11-11 decisions as they are.
5. **Merge and tag.** Authorise or refuse the squash merge; authorise creating and pushing the history tag (section C).
   Nothing is merged or tagged automatically.

## C. Integration readiness

### Release verification history

| Run | Revision | Result |
| --- | --- | --- |
| 44084515801, 44088269511, 44095792721, 44113451030 (`verify-release`) | branch | failed or incomplete; together they exposed six defects of the release machinery that no unit test could see (REAL preflights compared the checked-out commit with the pull-request merge commit; the aggregate copied mutated shard sources into the checkout; the 8.1 MB sharded envelope exceeded the 5 MB member limit; the bundle carried the tracked equivalence document its own allowlist refuses; the REAL profile collected PyTorch tests the locked environment cannot import; the gate did not install the shards' dependency set), each fixed at its cause and covered by a test |
| 44143370017 (`verify-release`) | `8e50b699` | every profile PASS, gate **REJECTED** for dependency versions only: FAST, FAULTS, DEEP, tools and reproduction ran the latest resolvable packages (pandas 3.1.1, pyod 3.6.8) while REAL ran the hash-locked environment (pandas 3.0.6, pyod 3.6.7). Kept as history |
| 44179716383 (`mutation-shards`) | `d3abc54` | measurement under the lock, aggregation failed by design (records bound pandas 3.1.1); see "Earlier campaign" |
| 44253688343 (`verify-release`) | `5e57228` | cancelled |
| 44253806652 (`verify-release`) | `5e57228` | **CERTIFIED**, all seven profiles PASS, no rejection reason |

The decision of 2026-11-17 to align every profile on the lock (pandas 3.0.6 is the only version under which the archived
Cardio results replay numerically) was implemented by `d3abc54` and `5e57228`; the 97 records were rebound to the
locked versions, with scipy and great-expectations now bound where their behaviour matters.

### Post-certification commits

`5e57228..ad16a79` is one commit, `ad16a79 docs: archive the certified release report`, which adds
`evidence/release-44253806652/release.json`. The commits of the review of 2026-11-18 add documentation and archived
evidence only. The repository's own freshness rule (`verification/release.py`, `fresh()`: the certified revision is an
ancestor of HEAD and `claims.is_code` is false for every changed file) holds for all of them, so the certification
evidence stays current for HEAD under the official contract. That is not a new certification: the verdict names
`5e57228`, `release.json` stays immutable, and any release statement about a later or integrated revision needs its own
run.

### Branch audit against `main` (`6b9f7c5`)

| Check | Result |
| --- | --- |
| Up to date, conflicts | 0 commits behind; `git merge-tree` against `origin/main` is clean |
| Size | 350 commits ahead; 4,258 files, +170,438 / -1,673: 3,414 under `verification/evidence`, 617 under `docs`, 85 tests, 76 under `research`, 31 slides, 21 verification code, policy and records, 4 workflows, 3 paper files, plus README, `Makefile`, `pyproject.toml`, `.gitignore`, `agent.md` |
| Temporary or unintended files | none found: no `.DS_Store`, caches, `mutants/`, pid or environment files; no added file over 5 MB. The tracked symlink `.venv` of `main` (it pointed into another checkout) is removed and ignored; `agent.md` is an intended addition |
| Working-tree files not in the branch | untracked, left as they are: `CONTINUATION_EB1D679.md`, `evidence/ci-43830818155/`, `evidence/tracking-backup-2026-11-17/`, two `eb1d679` JSON files, `cardio-replay.json`, and extracted copies (160 MB) of tracked diagnostic archives. `experiments/results/cardio-env-audit/` is excluded on purpose because it holds derived dataset values (stated in `CARDIO_PANDAS_REPRODUCIBILITY_2026-11-14.md`). No tracked file cites a missing artifact |
| Scientific artifacts | the archived alert-budget runs, pool partitions, probes, diagnostics, mutation evidence and the certified release evidence above are present; no archived scientific result is modified |
| Branch protection | `main` requires `test` and `faults`, strict (branch up to date), 0 approving reviews, administrators not enforced, no force push; no rulesets |
| Checks | ordinary CI of PR #117 must be green on the final head, which a documentation commit cannot record for itself: read it from the PR checks. Before this review: `ci` on `ad16a79` (see the PR), `faults` and `slides` green; the release evidence is independent of ordinary CI |

The PR is draft, so GitHub reports the merge state as blocked until it is marked ready.

### History tag (prepared, not created)

The repository has no tags and no tag convention. Proposed annotated tag: `archive/pr-117-pre-squash`. Pushing a tag
triggers no workflow: `ci.yml` runs on pushes to and pull requests on `main`, `thesis-roadmap-sync.yml` on pushes to `main`,
`mutation-shards.yml` on pull requests and calls, `verify-release.yml` on manual dispatch, and no workflow publishes or
releases. The local configuration has `tag.gpgsign true`, so creating the tag needs a usable signing key. The tag must
point at the final branch head, so it is created after the last commit is pushed and its checks are green:

```sh
git fetch origin
git switch feat/risk-tiered-mutation-policy && git pull --ff-only
test -z "$(git tag -l archive/pr-117-pre-squash)"          # never move an existing tag
HEAD_SHA=$(git rev-parse HEAD)
git tag -a archive/pr-117-pre-squash "$HEAD_SHA" \
  -m "PR 117 branch history before squash; certified source 5e57228e3fa547df76a83ed32d00e3c1f6889d9a (verify-release run 44253806652)"
git rev-parse 'archive/pr-117-pre-squash^{commit}'          # must equal HEAD_SHA
git push origin archive/pr-117-pre-squash                  # publication; owner authorisation required
```

### Squash merge and post-merge certification (not executed)

Squash merge is recommended: it keeps `main` readable and the tag keeps the 350 commits, including every commit that the
evidence cites (`eb1d679`, `d4d21895`, `215da02`, `51ad0794`, `8e50b699`, `d3abc54`, `5e57228`). The squash commit has a new
SHA and inherits no certification. After the owner authorises the merge:

1. Check that `main` is the expected squash commit and that its tree equals the branch head tree
   (`git rev-parse <squash>^{tree}` against the tagged head).
2. Let ordinary CI finish green on that commit (`test`, `faults`); `thesis-roadmap-sync` also runs because the squash touches
   `docs/thesis-remediation/**`.
3. Run `verify-release` by `workflow_dispatch` on `main` with `fresh_mutants` (fixed true in the workflow). It installs the
   hash-locked environment and regenerates the 45-shard mutation evidence, because every shard binds its commit.
4. Require all seven profiles PASS and no rejection reason, in the locked environment of this report.
5. Archive the new `release.json` and the campaign and bundle tarballs under a new `evidence/release-<run>/` directory;
   do not edit the files of `release-44253806652/`.
6. Record both provenances: pre-merge (run 44253806652, `5e57228`, tag) and post-merge (new run, squash SHA).

Do not reuse evidence of another commit and do not relax a revision check. If the owner revokes a record or a test is
added first, the equivalence file or test tree changes and step 3 also validates that change.

### Other places that still describe the earlier status

Not modified, because the manuscript and the slides were declared finished and their figures are pinned by tests: the
manuscript (`paper/main.tex` lines 1635, 1701 and 1761) and the slide deck (`slides/deck_c.py`, 35,237 / 34,768 / 6
timeouts and "The release gate stays closed") state the 2026-11-17 campaign and a closed gate. They are out of date
relative to this report. Correcting them is a text and figure update that the owner may schedule after the post-merge
certification, when the final figures exist.

### Verdict

Ready for owner review. The certified revision, its evidence and the equivalence records are consistent, and the branch
merges cleanly. Not claimed: independent scientific certification, or certification of the squash commit. PR #117 stays a
draft until the owner decides section B.
