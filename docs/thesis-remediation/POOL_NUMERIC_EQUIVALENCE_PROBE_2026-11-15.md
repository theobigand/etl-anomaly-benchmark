# Pool numeric conversion default proposal

`research.pool_preprocessing.x__numeric__mutmut_9` omits `errors="raise"`
from the `pd.to_numeric` call that converts each selected numeric feature.
It is proposed as equivalent, not approved or excluded from any official score.
The contract rejects unparseable or infinite numeric data, permits missing
values, and returns numeric arrays in input column order. The documented
pandas default for `errors` is `raise` in both the
[2.0 API](https://pandas.pydata.org/pandas-docs/version/2.0/reference/api/pandas.to_numeric.html)
and [3.0 API](https://pandas.pydata.org/pandas-docs/version/3.0/reference/api/pandas.to_numeric.html).
The default applies to each series passed by `DataFrame.apply`; the surrounding
conversion and infinity check are unchanged.

Direct original/mutant probes matched numeric and missing values, numeric text,
invalid text, infinity, no selected columns and a nonexistent column, including
exception types and messages. These examples search boundaries but are not
exhaustive. They ran on macOS arm64, Python 3.11.17, NumPy 2.4.6 and
scikit-learn 1.9.1 in both the canonical pandas 3.0.6 and mutation pandas 3.1.1
environments. The probes do not establish behavior in every supported release
or under dynamic replacement of `pd.to_numeric`.

The source SHA-256 is
`edf8ac28b2824c76840c8e4cad47fe3fee1f1ac84a5b38ad341e968dee9e8dc0`;
the generated source is
`cbeabfdae48053ea69948b38802c4bf0f3dd9175a4289cd23e0b53806b641cc5` and
is preserved as `evidence/pool-preprocessing-generated-2026-11-15.py.gz`.
The executable probe and both outputs are in `evidence/pool-numeric-probe-2026-11-15.py`
and the matching `-conda.txt` and `-mutation.txt` files. With the matching
generated module present, run:

```sh
PYTHONPATH=mutants/research:src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/pool-numeric-probe-2026-11-15.py
PYTHONPATH=mutants/research:src ~/miniconda3/envs/etl-benchmark/bin/python \
  docs/thesis-remediation/evidence/pool-numeric-probe-2026-11-15.py
```

The historical raw unit was 241/248 (97.18%) at L4. Excluding this proposal
alone hypothetically gives 241/247 (97.57%), still below 98%. Even adding the
separate existing packet proposal yields 241/246 (97.967%), still below the
exact threshold. Neither figure is a current or officially authorized result.

Two further proposals in the same source are
`research.pool_preprocessing.x_prepare_frozen__mutmut_16` (`dtype=None`)
and `research.pool_preprocessing.x_prepare_frozen__mutmut_18` (dtype omitted),
both replacing `dtype=int` for a temporary membership array. The validation
before allocation requires nonempty, disjoint partitions that cover every
position exactly once. The subsequent loop therefore fills every element with
one of 0, 1 and 2, exactly representable in the default float64 dtype. The
array is used only to count distinct partition values per hashed feature row;
its dtype is not returned. Equality of those three values is unchanged, so the
cross-partition duplicate check and subsequent processing have the same input.

Both original/mutant comparisons matched a valid numeric/categorical frame,
a duplicate confined to one partition, a duplicate across partitions, and
invalid overlapping assignments. The complete returned tables and fit report
or the exception type and message were compared in both recorded pandas
environments. The same source and generated source digests above apply. The
probe cannot establish behavior for dynamic library replacement or every
future pandas version. These cases remain proposals, without owner approval
or independent review. Hypothetically excluding these two and the numeric
conversion proposal gives historical 241/245 (98.37%); that would cross the
historical L4 threshold, but is neither a current measurement nor an
authorized adjusted score. The prior packet's separate proposal is not
counted in this hypothetical.

`research.pool_preprocessing.x_prepare_frozen__mutmut_93` remains inconclusive.
It forces the `nanmedian` branch when there are no numeric columns, where the
original creates an empty median array. The same probe compared mixed and
categorical-only data, duplicate cases and invalid partitions; it found matching
outputs, errors and successful-call warnings in both local pandas environments.
Both used NumPy 2.4.6, however, so the empty-axis numerical and warning behavior
has not been established across the supported NumPy range. No equivalence is
proposed on that evidence alone. The record retains its source identity and
this limitation for a later supported-environment investigation.

The `_categorical` mutants `research.pool_preprocessing.x__categorical__mutmut_2`
and `research.pool_preprocessing.x__categorical__mutmut_4` remain inconclusive.
They replace `dtype=object` with None or omit it in the string array conversion.
The probe found matching object dtype and values for missing, Unicode, empty
and mixed inputs in both local pandas environments. Earlier supported pandas
releases and alternate string-storage backends were not exercised, and this
is a separate operation from the existing owner-decided LSTM records. No
new equivalence is proposed. An initial probe used NumPy's array equality on
object arrays and failed because paired NaNs compared unequal; the retained
probe checks dtypes and uses pandas' missing-aware frame equality instead.
