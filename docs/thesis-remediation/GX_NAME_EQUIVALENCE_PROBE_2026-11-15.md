# Ephemeral GX identifier proposals

Six historical survivors change only the fixed name supplied when creating a
component inside a fresh ephemeral Great Expectations context:

- `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_17`
  and `_18`: datasource name;
- `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_19`
  and `_20`: dataframe asset name;
- `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_21`
  and `_22`: batch definition name.

These are proposed equivalents only. Each object is obtained directly from
its creator and used within the same new ephemeral context; those names are
not returned in the detector's row-failure result. The separate mutation that
changes the context mode has a demonstrated side effect and was killed; this
proposal assumes the unchanged ephemeral mode. Different identifiers could
still affect library logs, telemetry or behavior in untested GX releases, and
those effects were not exhaustively checked. Neither owner approval nor
independent review exists for these six proposals.

The executable probe compared original and each generated mutant's exact
index-aligned row failures for normal data and missing/outlier data with a
duplicate input index. It used macOS arm64, Python 3.11.17, NumPy 2.4.6 and
mutmut 3.8.0 in both GX 1.24.0/pandas 3.0.6 and GX 1.24.1/pandas 3.1.1.
These are two examples from the supported 1.x dependency range, not every
version or every possible input.

The source SHA-256 is
`11be59dbe975d05547395263b763d37716cd9f916b284ce4147cfd87c61e3416`;
the generated-source SHA-256 is
`03c4ec9748e7d655d0c142f303a962c2a157be91455e528b1988ef9e9be166a6`,
retained in `evidence/gx-generated-2026-11-15.py.gz`. The probe and outputs
are `evidence/gx-name-probe-2026-11-15.py` and the corresponding `-conda.txt`
and `-mutation.txt` files. To reproduce with the matching generated module:

```sh
PYTHONPATH=mutants/src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/gx-name-probe-2026-11-15.py
PYTHONPATH=mutants/src ~/miniconda3/envs/etl-benchmark/bin/python \
  docs/thesis-remediation/evidence/gx-name-probe-2026-11-15.py
```

The historical raw L4 result was 87/98 (88.78%); hypothetically excluding all
six gives 87/92 (94.57%), still below 98%. Later focused kills are deliberately
not combined with that historical measurement. The hypothetical is neither a
current unit result nor an authorized adjusted score.
