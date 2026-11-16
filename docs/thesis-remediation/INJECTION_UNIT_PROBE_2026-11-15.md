# Injection time-unit investigation

`research.injection.x_inject__mutmut_48` and
`research.injection.x_inject__mutmut_191` change an hour unit from `h` to `H`
at different timestamp-generation sites. They remain inconclusive; neither is
proposed equivalent or counted as killed.

With the same 400-row seeded numeric carrier, the generated original and each
mutant produced equal complete output frames in both local environments:
macOS arm64, Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6 or 3.1.1. In both,
the original emitted no warning and each mutant emitted a `Pandas4Warning`
about the deprecated uppercase hour unit. Thus outputs matching in those
examples do not establish behavioral equivalence. Whether that warning is a
meaningful contract violation for this workflow, and behavior in other
supported pandas versions, still need investigation. No artificial warning
assertion was added solely to kill these mutants.

The source SHA-256 is
`cdfc81d98e3470ccdf5f7930d7e987b1bdad3545e060552f3a3bb1d170d8cb39`;
the generated source SHA-256 is
`0a049b613cdff4161eabffebcb6f7c7a0dfc67379516fec3e6bac09781988cdd`,
retained as `evidence/injection-generated-2026-11-15.py.gz`. The probe and
results are `evidence/injection-unit-probe-2026-11-15.py` and the matching
`-conda.txt` and `-mutation.txt` files. With that generated module available,
run the probe with `PYTHONPATH=mutants/research:src` and each interpreter
specified in the output files' environment records.

```sh
PYTHONPATH=mutants/research:src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/injection-unit-probe-2026-11-15.py
PYTHONPATH=mutants/research:src ~/miniconda3/envs/etl-benchmark/bin/python \
  docs/thesis-remediation/evidence/injection-unit-probe-2026-11-15.py
```

`research.injection.x__pair__mutmut_9` is a separate proposed equivalent, not
an owner decision. It replaces the common diagonal sentinel -1 with -2 after
taking absolute correlations. Finite off-diagonal values are nonnegative, so
neither negative sentinel outranks them; missing correlations and degenerate
shapes were also considered. The same probe compared the returned column pair
and correlation, or error, for a four-column finite carrier, a constant
column, a single column and no columns in both local pandas builds. The
single-column and empty cases probe the helper directly; normal injection uses
at least three columns. The finite/NaN and argmax reasoning is conditional on
the recorded NumPy/pandas operations and assumes no dynamic function
replacement. It is not a proof for every future dependency build.

The same source and generated-source digests and probe paths above apply. The
historical injection unit score was 325/336 (96.73%), L4 threshold 98%.
Hypothetically excluding this mutant alone yields 325/335 (97.01%), still
below threshold. The existing packet's separate proposals are not counted;
this is not a fresh measurement or an authorized adjusted score.

`research.injection.x_continuous_columns__mutmut_5` is another unapproved
proposal. It passes None rather than the column to the boolean dtype check.
For built-in NumPy bool and pandas nullable Boolean columns, there are at
most two distinct nonmissing values, while the unchanged subsequent rule
requires at least ten. Thus those columns are excluded even if the boolean
check is bypassed. Numeric columns with ten distinct values still pass, and
nonnumeric columns are rejected by the preceding numeric dtype check.
The probe compares the original and mutant on ordinary and nullable boolean,
binary integer, twenty-distinct integer and string columns in both local
pandas environments. Custom extension dtypes that claim boolean identity but
expose additional values were not tested; this proposal is conditional on
the built-in dtype behavior and unchanged threshold. It is not an owner
verdict or independent review. Excluding this and the `pair` proposal alone
would hypothetically yield historical 325/334 (97.31%), still below L4 98%;
it is not an authorized or current score.

A later isolated lower-bound probe with pandas 2.0.3 and NumPy 1.24.4 found
matching frames and no warnings for either case, unlike the `Pandas4Warning`
observed with pandas 3.0.6/3.1.1. See
`evidence/continuation-2026-11-15/injection-units-minimum.log.gz`. This
version-dependent warning strengthens the reason to retain both identities as
inconclusive; it does not establish a warning contract or an owner exclusion.
