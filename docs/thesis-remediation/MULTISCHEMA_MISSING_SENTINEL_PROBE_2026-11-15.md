# Multi-schema missing-value sentinel

`research.multi_schema.x_make__mutmut_126`, source SHA-256
`1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`,
changes injected `np.nan` to `None`. Direct generated-function comparisons
for the two built-in schemas, multiple row counts, seeds and severities matched
values, dtypes and captured warnings in pandas 3.0.6 and 3.1.1 on macOS arm64.

A counterexample uses a `Schema` whose clean generator returns object-typed
string and categorical columns: `make` then returns float NaNs in some missing
positions on the original, but Python `None` at those positions on the mutant.
Both are missing under pandas `isna`, but Python consumers can distinguish them
and strict JSON serialization treats them differently. The generator accepts a
`Schema` argument, so the difference must not be dismissed merely because the
built-in frames compare equal. The public contract specifies missingness; the
available evidence does not establish a requirement for one Python sentinel or
a downstream scientific effect. This case remains **inconclusive**, not an
exclusion proposal or a verified kill. Further investigate actual supported
consumers before defining any regression around sentinel identity.

Executable probes and outputs are `multi-missing.py.txt`,
`multi-missing-output.txt`, `multi-missing-object.py.txt` and
`multi-missing-object-output.txt`, and `json-sentinel-py311-output.txt` under `evidence/continuation-2026-11-15/`.
The generated source is preserved in the nine-focused evidence. Reproduce:

```sh
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/multi-missing-object.py.txt
```

No owner decision, policy change, unit remeasurement or scientific archive
change follows from these probes.
