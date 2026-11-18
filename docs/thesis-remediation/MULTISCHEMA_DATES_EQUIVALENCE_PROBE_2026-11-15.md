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

Three additional unapproved proposals in the same source are
`research.multi_schema.x_main__mutmut_70`, `_73` and `_74`. They make the
same strict-to-nonstrict changes to the zip that pairs the fixed `SEEDS` tuple
with `runs`. Immediately before that zip, a list comprehension builds one run
for each member of the same tuple, so successful completion gives equal
lengths. The argument assumes the module's seed tuple is not dynamically
reassigned during generation; the shipped generator and evaluator do not
reassign it.

The executable `evidence/multischema-main-zip-probe-2026-11-15.py` compares
all seven artifacts emitted by the original and each mutant on the existing
five seeds, using the real command serialization and atomic writers. To bound
execution it narrows the registry to one schema and replaces generation and
model evaluation with deterministic frames; it therefore does not establish
scientific model behavior or exercise classical-mode hypotheses. The
recorded environment and generated/source digests match the date probe's
mutation environment above; only that environment was exercised for this
command probe. Its `.txt` output records the files compared. Invoke with
`PYTHONPATH=mutants/research:src` and the mutation interpreter.

The three main-zip and three date-zip proposals together hypothetically give
1057/1087 (97.24%) for the historical L4 unit; adding the two new index
proposals gives 1057/1085 (97.42%). Both remain below 98%, exclude other
packet candidates and are neither current scores nor authorized decisions.

Four more conditional proposals are `research.multi_schema.x_main__mutmut_23`,
`_27`, `_35` and `_36`. They replace or omit the default `classical` methods
argument. The only use of the parsed value in the recorded command is the
comparison with `deep`; all four altered defaults select the same classical
route. The actual argument parser accepted each default in the tested runtime.
The main probe now compares the no-option route and all emitted artifacts,
using the real parser and writers but deterministic stand-ins for generation,
detectors, published customer data and hypotheses. It does not validate those
scientific computations or other Python/argparse versions. None of these
proposals has owner approval or independent review.

Considering only the twelve newly proposed multi-schema mutants (three date,
three seed zip, two index and four default-route cases), historical arithmetic
would be 1057/1081 (97.78%), still below L4 98%. Previous packet proposals are
excluded from this calculation. It is not a current or official score.
