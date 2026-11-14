# Case-sensitive measurement environment

Local mutation runs on macOS miss kills that Linux makes: pytest's temporary folders sit on the default volume, which compares file names without case, so a mutant that only changes the case of a path (`"TYPED_INJECTION"`, `"PYPROJECT.TOML"`, `"GIT"`) survives. The verdicts adopted by `evidence/merge_case_sensitive.py` come from runs with the repository and `TMPDIR` on a case-sensitive APFS volume.

## Recreate it

```
docs/thesis-remediation/evidence/case_sensitive_volume.sh setup     # sparse image in ~/.cache, mounted at /Volumes/etlcs, repository copied
docs/thesis-remediation/evidence/case_sensitive_volume.sh run research/typed_figures.py verification/scaling.py
python docs/thesis-remediation/evidence/merge_case_sensitive.py
python docs/thesis-remediation/evidence/consolidate_l4_campaign.py
python docs/thesis-remediation/evidence/build_owner_packet.py
python docs/thesis-remediation/evidence/build_l4_campaign_report.py
python docs/thesis-remediation/evidence/archive_verdicts.py
```

`setup` and `sync` copy the checkout (without `mutants/`) and its `.git`; `run` collects the test map once, runs each unit with `run_l4_campaign.py --rerun`, writes the survivor differences into `evidence/l4-campaign-2026-11-13/survivors/` straight after the unit (the generated copy is a mutated source only then) and copies the verdict file next to the main checkout's as `mutants/<unit>.meta.cs`.

## What is and is not recorded

- Environment: the mutation venv (`~/.cache/etl-mutation-venv`: mutmut 3.8.0, pandas 3.1.1, numpy 2.4.6, torch 2.15.0 without the `+cpu` build tag), macOS arm64, Python 3.11.17.
- `case-sensitive-units.json` keeps, per adopted unit, the counts of this run and of the case-insensitive file it replaced, plus the head and test-tree digest of the copy at the last adoption. A unit's run is not tied to one commit: runs were made at successive commits, and killed verdicts persist across runs.
- `verdicts.tgz` (with `verdicts.sha256`) archives every verdict file so `final-measurement.json` can be rebuilt.
- Not recorded: a Linux run. The CI mutation jobs are skipped on this branch, so "dies on Linux" is an expectation, not a measurement. The official `lstm_detector` equivalence records need `torch 2.15.0+cpu`, which only a Linux runner provides.

## Compatibility with the controller

The adopted files are `mutmut` verdict files of the same mutant keys as the case-insensitive ones (the merge refuses a file whose keys differ). They are inputs to the local consolidator, which applies the exact integer score rule and records any timeout, incomplete or not-run verdict as INCOMPLETE. They are not controller evidence: the controller rebuilds its own proof with `verification/mutation_run.py` and `mutation_campaign.py` on a clean runner.
