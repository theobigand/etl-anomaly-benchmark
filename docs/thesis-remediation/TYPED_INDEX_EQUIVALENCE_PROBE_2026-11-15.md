# Typed benchmark result-index proposals

The historical survivors `research.typed_benchmark.x_evaluate__mutmut_53`
(`index=None`) and `research.typed_benchmark.x_evaluate__mutmut_55` (index
omitted) are proposed equivalents, not approved or excluded. The contract is
that detector flags align with the held-out rows when calculating FPR,
per-type recall and precision. The real `split` function resets each
partition's index with `drop=True`; therefore the test index is a zero-based
RangeIndex. A pandas Series built from the same flag array with the default
index has that same index. This argument relies on that split invariant and the
recorded pandas behavior; substituting a different split implementation is
outside the argument.

The probe injects a 4,000-row carrier, assigns it a reversed non-default
input index and performs the real split and z-score evaluation with seeds 0
and 11. Both mutants matched original recall, precision and FPR tables and the
split's RangeIndex was checked. These two seeds are examples, not an exhaustive
search. Environment: macOS arm64, Python 3.11.17, NumPy 2.4.6, pandas 3.1.1,
scikit-learn 1.9.1, mutmut 3.8.0. No second pandas build was executed.

Source SHA-256 is `abdd10e4a1965e99bd5db8ad1a61b0b9e37caed20f35d09c32bcb1a9a3bae9d2`;
the generated source SHA-256 is
`da03f935214788a1877fee129fd94c405b10cd71c5e29244705fb980ed1a8976`,
preserved in `evidence/typed-generated-2026-11-15.py.gz`. The executable
probe and output are `evidence/typed-index-probe-2026-11-15.py` and `.txt`:

```sh
PYTHONPATH=mutants/research:src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/typed-index-probe-2026-11-15.py
```

The historical raw unit was 175/180 (97.22%), L4 threshold 98%. Hypothetically
excluding these two alone yields 175/178 (98.31%), crossing that historical
threshold. The previous packet's separate proposal is not included. This is
not a fresh score, official exclusion, or independent review.

Two analogous unapproved proposals are
`research.multi_schema.x_evaluate__mutmut_68` and
`research.multi_schema.x_evaluate__mutmut_70`. The recorded `_split` also
resets each partition to a RangeIndex before `evaluate` constructs flags.
The probe uses the real generators and split for the transactions and sensors
schemas with a non-default input index. To bound execution it narrows the
classical registry to the real z-score detector; drift and deduplication still
run. Original and mutant recall, precision and FPR matched. Deep mode and the
other classical detectors were not executed by this probe; the index invariant
is shared by the code paths but has not been independently reviewed.

The multi-schema source SHA-256 is
`1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`;
the retained generated module `evidence/multi-schema-generated-2026-11-15.py.gz`
has uncompressed SHA-256
`8b48b7c67a6e97e0bfa55683104c6f7c28ff77fcc949ba1e6281003424dbdf8e`.
The common probe and output above include these cases. The historical raw
multi-schema score was 1057/1093 (96.71%); hypothetically excluding only
these two gives 1057/1091 (96.88%), still below L4 98%. No current measurement,
owner decision or official adjusted result is implied.
