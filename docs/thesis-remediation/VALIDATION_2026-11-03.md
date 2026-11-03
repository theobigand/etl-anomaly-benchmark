# Definition remediation validation — 2026-11-03

Scope: #91 (T090, T094–T096, T098, T099) and #89 (T037–T044).
Implementation commits: `538210a` (metrics), `ce90e59` (rule definitions).
Branch: `docs/thesis-metric-definitions`. These are partial issue deliverables;
neither issue nor any parent milestone is complete.

## Checks and outcomes

Commands use `export PATH=/Users/theo/miniconda3/envs/etl-benchmark/bin:$PATH`
in the existing environment, without dependency installation or upgrades.

- **Baseline, before edits:** `pytest tests/test_metric_contract.py tests/test_publication_tables.py tests/test_manuscript_claims.py tests/test_artifact_lineage.py -q` — 38 passed.
- **Rule baseline, before the rule edit:** `pytest tests/test_detector_contracts.py tests/test_gx.py -q` — 32 passed.
- **Combined regression, after both edits:** `pytest tests/test_detector_contracts.py tests/test_gx.py tests/test_metric_contract.py tests/test_publication_tables.py tests/test_manuscript_claims.py tests/test_artifact_lineage.py -q` — 70 passed.
- **Mathematical acceptance:** both Python examples in the linked metric/rule evidence pages executed successfully; 240 exact strict rankings, tied-score baseline, threshold separation and Gaussian-tail calculations passed.
- **Build:** from `paper/`, `latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=/tmp/etl-thesis-paper main.tex` — passed. An initial invocation from the repository root failed because `main.tex` is in `paper/`; corrected working directory, no source workaround. Rebuilt PDF copied to `paper/main.pdf`. Page count remains 22; no undefined references or overfull boxes; 24 underfull-box notices remain. Rule and AP definition pages inspected as rendered images. This is not a full submission-format audit.
- **Publication manifest:** `python verification/archive_evidence.py --manifest-only` — passed after rebuilding. Compared against `901cced`: only `paper/main.tex` and `paper/main.pdf` artifact hashes changed. Dataset metadata, commands, all other listed hashes and sealed experiment records remain unchanged. Manifest revision/dirty fields truthfully describe publication assembly, not a clean replay or certification.
- **Fingerprint check:** `provenance.scientific_fingerprint_of(lineage.files_at("901cced"))` equals the fingerprint of `lineage.worktree_files()`; the corresponding measurement fingerprints also match. Documentation changes do not invalidate detector results or require scientific archive replay for this unit. This does not resolve the pre-existing #82 large-archive replay requirement.
- **Inventory:** all T001–T415 occur once in the canonical volumes; precisely 14 tasks are checked. P2 and `status:if-time` work remain excluded.
- **Formatting/static inspection:** `ruff check .`, `ruff format --check .`, `git diff --check` — passed after formatting the acceptance example.

## Failures retained and resolved

The first complete `make verify-fast` run returned failure: 1 failed, 1291 passed,
27 deselected. `test_archived_tables_and_figures_match_manifest` correctly detected the
changed manuscript before its publication hash was refreshed. Its failure was reproduced
with `pytest -x -m 'not real and not fault' -q`. The targeted lineage checks passed after
the PDF rebuild and supported manifest refresh. No assertion was weakened.

A subsequent FAST attempt stopped at `ruff format --check .`, which required whitespace
formatting in the Markdown Python example. Formatting was applied and the recorded
acceptance example was executed again successfully. These are validation-first document
corrections, not a claimed test-first change to scientific behavior.

## Gate applicability and limits

FAST final outcome: PASS (`make verify-fast`, exit 0): 1292 passed, 27 deselected,
300 warnings; 1790/1790 executable statements and 350/350 branches covered.
The warnings concern Isolation Forest max_samples on small contract-test inputs.
The result is local workspace verification, not clean-revision release certification.
Full command output: [FAST log](evidence/fast-2026-11-03.txt).

DEEP, FAULTS, REAL, types, verifier coverage, locked-environment reproduction and release
certification were not rerun for this documentation-only unit. No scientific implementation,
protection, verifier, dependency, environment or test changed; the relevant existing policies
apply by impact. No new clean-revision certification, independent attestation or CI pass is
claimed. The branch push does not trigger CI: `ci.yml` runs on pushes to main or pull requests.
No pull request, merge, release, deployment or protected-setting change is part of this unit.

## Remaining work and resume order

#91: T091–T093 and T097 (global display terminology, figures and evaluation prevalence).
#89: T045–T070 (remaining detector/adaptation and preprocessing audit). Next prioritize
this methods/source-accounting audit with #90, then source-aware inference #93/#83,
coordinated #91/#92 publication displays and #82 replay before final #88/#99 claims.
See [roadmap reconciliation](AUDIT_2026-11-03.md) for other historical and governance
requirements. Existing scientific limitations are unchanged by these definition corrections.
