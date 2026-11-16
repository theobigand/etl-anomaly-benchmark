# Temporal drift initial-state and inactive-path probes

The following five historical survivors in `src/etl_benchmark/quality/drift.py`
(source SHA-256 `95380ca0f8f87a24c512ac7055357225472342065e0da676c0be46dd115fa09b`)
are conditional proposals, not approvals:

- `etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ__init____mutmut_11`
  sets `_fitted` to `None` instead of `False`; both are false under the guard.
- `etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ__init____mutmut_13`
  and `_14` set `_active` to `None` or `True`; `_fitted` still guards use
  before fit, and fit assigns `_active` before public scoring.
- `etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ__init____mutmut_15`
  initializes the private cutoff to an empty string; a fit with a usable time
  column assigns a cutoff before learned means are available.
- `etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁfit__mutmut_4` sets
  `_active` to `None` instead of `False` when no timestamp exists. Both are
  false under the public predict/score branch.

Direct generated-constructor probes compared pre-fit score/predict, successful
fit, absent time, empty, singleton, missing and nonnumeric data, and scoring
after a failed fit. Direct generated-fit probes covered absent timestamps on
empty and nonempty frames, both fresh and previously fitted. The public
outcomes and captured warnings matched for these five identities in the
observed cases on macOS arm64, Python 3.11.17, NumPy 2.4.6 and pandas
3.0.6/3.1.1. Scripts and outputs are `drift-init.py.txt`,
`drift-init-detailed.py.txt`, `drift-partial-fit.py.txt`, `drift-inactive.py.txt`
and corresponding `*-output.txt` files in
`evidence/continuation-2026-11-15/`. Generated source is preserved in
`evidence/pending-probes-2026-11-15/drift-generated.py.gz`.

The same search found a counterexample for the distinct `_means` initializer
mutant `_16`: after an empty-frame fit fails, a later score raises a different
exception type than the original. The `_stds` initializer `_17` also differs
in private partial state after some failed fits. Whether these differences have
a supported public contract is unresolved, so those two remain inconclusive.
Confidence for the five proposals is medium for the tested paths; other numeric
extension dtypes, versions and Linux remain untested. No full unit score or
owner decision is implied.

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/drift-init-detailed.py.txt
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/drift-inactive.py.txt
```
