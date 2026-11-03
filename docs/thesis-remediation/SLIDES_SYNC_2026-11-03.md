# Presentation synchronization — 2026-11-03

Related issues: #89, #91, #92, #103. Completes the presentation companion to the
verified definition corrections, without closing their remaining scientific tasks.

## Changes

- Added editable slides explaining non-interpolated AP, tied scores, prevalence and
  finite-sample random-ranking qualifications, and ranking versus threshold metrics.
- Added a fitted-rule slide covering sample standard deviations, IQR fences, constant
  columns, Gaussian per-column tail references and the actual generic GX suite.
- Updated authored result labels from PR-AUC to AP; archived image labels remain as
  recorded and their historical AP meaning is explained. All pre-existing result-table
  numbers are identical before/after this edit.
- Updated the roadmap status slide to distinguish historical completion from the
  current 415-task remediation plan, 14 verified tasks and outstanding P0 work.
- Fixed a synthetic heatmap display overflow found during visual inspection; the
  figure file and its scientific values are unchanged.
- Rebuilt `slides/thesis_progress.pdf`: 38 pages, including two added definition slides.

`paper/main.tex` and its PDF already contain the corresponding corrected definitions
from `538210a` and `ce90e59`. Their bytes and publication manifest remain unchanged
in this presentation follow-up. No experimental implementation or result changed.

## Validation

Documentation-only validation-first work; no executable scientific behavior changed.

- `make slides CHROME=<Chromium executable>`: PASS with Google Chrome 155.0.8059.80.
  The executable path contains spaces, so a temporary shell launcher was used because
  the existing Makefile expands CHROME unquoted. An initial direct-path invocation
  failed before rendering; no dependency or Makefile change was needed.
- Rendered all 38 PDF pages and inspected contact sheets; inspected definition slides
  and the corrected heatmap separately at full presentation size.
- Browser geometry at a 1280×720 content viewport: all 38 slides pass text/table/image
  bounds and footer-overlap checks; keyboard next/previous navigation passes. A first
  check used an outer window of 1280×720, yielding only 633 content pixels; the window
  was adjusted to measure the documented 720-pixel content viewport. These checks do
  not establish mobile/short-viewport support.
- Machine-readable results: [geometry and navigation](evidence/slides-geometry-2026-11-03.json).
- Output voice check: PASS. `make lint` and `git diff --check`: PASS.
- `pytest tests/test_metric_contract.py tests/test_publication_tables.py tests/test_manuscript_claims.py tests/test_artifact_lineage.py -q`: 38 passed after synchronization.
- Table-number comparison: every pre-existing HTML table retains its numeric cells.
  Manuscript-byte comparison against the preceding commit: identical.

The prior [FAST record](VALIDATION_2026-11-03.md) is preserved as a dated local run,
not relabelled as evidence from this later revision. Integration checks must pass on
this branch's final revision before merging. No new release certification is claimed.

T091–T093 and T097 remain open because global paper/generator/figure terminology and
prevalence presentation are not completed by updating the slides alone. T045–T070,
#82 replay and #83 statistical sensitivity remain outstanding. The 14 checked tasks
are the same in GitHub and the canonical volumes; no additional task is claimed done.
