# Typed and multi-schema metric probes

Four historical mutants remain inconclusive after investigation:
`research.typed_benchmark.x__per_type__mutmut_18` and `_26`, and
`research.multi_schema.x__per_type__mutmut_18` and `_26`. Each replaces a
boolean target's `astype(int)` with `astype(None)` before recall or precision
is computed. The original and each mutant produced identical metric values
for mixed flags, no predicted positives and an absent anomaly type in the
probe. Both local environments were tested (pandas 3.0.6 and 3.1.1), but both
use scikit-learn 1.9.1 and NumPy 2.4.6. Compatibility with other supported
scikit-learn versions and dtypes was not established. These distinct mutants
are not re-proposals of the previously decided LSTM records, and no exclusion
is proposed from these observations.

A fifth mutant, `research.multi_schema.x__per_type__mutmut_25`, omits
`zero_division=0` for precision. Its values also matched in those cases, but
with no predicted positives it emitted `UndefinedMetricWarning`, unlike the
original. The significance of that warning for supported callers and other
scikit-learn versions remains unresolved. No warning-only regression was
added solely to change a mutation score.

The source SHA-256 values are
`abdd10e4a1965e99bd5db8ad1a61b0b9e37caed20f35d09c32bcb1a9a3bae9d2`
for `research/typed_benchmark.py` and
`1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`
for `research/multi_schema.py`. Matching generated modules are retained as
`evidence/typed-generated-2026-11-15.py.gz` and
`evidence/multi-schema-generated-2026-11-15.py.gz`; their uncompressed hashes
and environments are in both probe outputs. The executable is
`evidence/typed-metric-probe-2026-11-15.py`, run with
`PYTHONPATH=mutants/research:src` and each of the canonical conda and mutation
interpreters. This is evidence for further investigation, not a new unit score
or owner decision.
