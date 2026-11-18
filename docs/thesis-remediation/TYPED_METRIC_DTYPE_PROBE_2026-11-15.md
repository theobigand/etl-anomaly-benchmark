# Typed per-type metric dtype probes

`research.typed_benchmark.x__per_type__mutmut_18` and `_26` replace integer
conversion with `astype(None)` for the binary truth labels supplied to recall
and precision, respectively. Source SHA-256:
`abdd10e4a1965e99bd5db8ad1a61b0b9e37caed20f35d09c32bcb1a9a3bae9d2`.
The contract is per-anomaly-type recall and precision relative to clean rows;
binary boolean labels become numerical zero and one under both conversions in
the tested environments.

Direct generated-function comparisons covered mixed, all-positive,
all-negative, absent-type, no-clean, empty and nullable-string cases. Metrics,
errors and captured warnings matched on macOS arm64 with Python 3.11.17,
NumPy 2.4.6, scikit-learn 1.9.1 and pandas 3.0.6/3.1.1. The script and raw
output are `typed-per-type-dtype.py.txt` and
`typed-per-type-dtype-output.txt` in
`evidence/continuation-2026-11-15/`. The generated source SHA-256 is
`da03f935214788a1877fee129fd94c405b10cd71c5e29244705fb980ed1a8976`,
preserved as `evidence/typed-generated-2026-11-15.py.gz`.

These are conditional owner proposals, not approvals. Confidence is medium for
tested binary labels and dependency builds; other supported versions, dtypes
and Linux remain untested. No complete current unit score is implied.

```sh
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/typed-per-type-dtype.py.txt
```

Additional lower-bound dependency results are in [the compatibility addendum](MINIMUM_DEPENDENCY_PROBES_2026-11-16.md).
