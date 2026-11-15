# Multi-schema date sequence proposals

The three historical survivors `research.multi_schema.x__dates__mutmut_31`,
`research.multi_schema.x__dates__mutmut_34` and
`research.multi_schema.x__dates__mutmut_35` change `zip(..., strict=True)`
to `strict=None`, omit `strict`, or use `strict=False`, respectively. They
are proposed equivalents, not approved or excluded.

The date generator draws `offsets` and `hours` from the supplied NumPy
Generator using the same length `n`. For its annotated integer `n` and
standard Generator, successful draws have the same length; strict and
non-strict zip therefore visit the same pairs. A negative size fails while
drawing the first sequence, before zip. Replacing the Generator with a
nonconforming object that returns unequal lengths lies outside this argument;
that possibility and future dependency changes remain limitations.

Original and each generated mutant were compared at sizes 0, 1, 10, 100 and
-1 with a fixed seed and time-inclusive format, including matching failures,
in both local pandas environments (3.0.6 and 3.1.1) with NumPy 2.4.6, Python
3.11.17 and mutmut 3.8.0 on macOS arm64. These probes do not cover every
Generator implementation or NumPy version.

The source SHA-256 is
`1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`;
the retained generated module
`evidence/multi-schema-generated-2026-11-15.py.gz` has uncompressed SHA-256
`8b48b7c67a6e97e0bfa55683104c6f7c28ff77fcc949ba1e6281003424dbdf8e`.
The executable `evidence/multischema-dates-probe-2026-11-15.py` and both
`-conda.txt` and `-mutation.txt` outputs record the comparisons. For example:

```sh
PYTHONPATH=mutants/research:src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/multischema-dates-probe-2026-11-15.py
```

The historical L4 unit was 1057/1093 (96.71%). Hypothetically excluding these
three alone gives 1057/1090 (96.97%), still below 98%; including the two new
index proposals gives 1057/1088 (97.15%), also below. Earlier packet proposals
are not counted. Neither figure is a fresh or authorized score.
