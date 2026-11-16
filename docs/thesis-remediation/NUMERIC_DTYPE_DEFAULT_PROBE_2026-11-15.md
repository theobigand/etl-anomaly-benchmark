# Numeric conversion default probes

Five historical survivors replace an explicit numeric conversion dtype with
`None`. These are conditional proposals, not owner approvals:

- `research.pool_chrono.x_to_features__mutmut_12`, source SHA-256
  `cd8b6eff471b942804223040ca94f119f2ab710479c341dfd3d2668342eff035`,
  changes a numeric feature conversion from `astype(float)` to `astype(None)`.
  On the tested pandas builds both produce float64 for the exercised numeric
  dtypes. Direct generated-function comparisons covered signed and unsigned
  integer, float32/64, nullable integer/float, constants, missing values,
  infinities, large integers and extreme floating-point values. Returned frames,
  dtypes and errors matched.
- `research.multi_schema.x__transactions__mutmut_2` and `_66`, source SHA-256
  `1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`,
  change NumPy integer-array casts to `astype(None)` for item count and account
  age. In the tested NumPy build both conversions yield float64. Direct
  generated-function comparisons with fresh, identically seeded generators
  covered zero, singleton and larger datasets and two seeds; frames and dtypes
  matched.
- `research.multi_schema.x__per_type__mutmut_18` and `_26`, the same source
  digest, convert boolean truth labels to the default floating dtype instead of
  integer before recall or precision scoring. Both represent binary values as
  0 and 1. Direct generated-function comparisons covered mixed, all-positive,
  all-negative, absent-type, no-clean, empty and nullable-string cases;
  returned metrics, errors and captured warnings matched.

The checks ran on macOS arm64, Python 3.11.17, NumPy 2.4.6, scikit-learn 1.9.1,
and pandas 3.0.6 and 3.1.1. Executable probes and raw results are in
`evidence/continuation-2026-11-15/`: `pool-numeric.py.txt`,
`pool-numeric-boundaries.py.txt`, `transactions-dtype.py.txt`,
`per-type-dtype.py.txt`, and their corresponding `*-output.txt` files. The
exact generated source for both modules is preserved in the earlier
`evidence/nine-focused-*.gz` files. For example:

```sh
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/per-type-dtype.py.txt
```

Evidence confidence is medium for the tested environments and inputs. Other
supported dependency builds, extension dtypes and Linux remain untested. The
separate precision mutant that omits `zero_division=0` is not included: its
warning behavior is different and remains under investigation. No current
complete unit score or owner decision is implied.

Additional lower-bound dependency results are in [the compatibility addendum](MINIMUM_DEPENDENCY_PROBES_2026-11-16.md).
