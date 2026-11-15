# Drift score gross-outlier replacement

`etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ_row_score__mutmut_43`
replaces `row[gross] = 0.0` with `row[gross] = None` in source
`src/etl_benchmark/quality/drift.py`, SHA-256
`95380ca0f8f87a24c512ac7055357225472342065e0da676c0be46dd115fa09b`.
The behavioral contract excludes gross single-feature outliers from drift
scores while preserving scores for other rows. The method multiplies the row
scores by a finite recent/older factor and then fills missing values with zero;
onfloating outlier positions assigned `None` become missing and reach the same
zero after that fill.

The executable generated-method probe compares values, indexes and dtypes for
float64 and nullable Float64, several window sizes and seeds, a gross outlier,
and missing data. Original and mutant matched on macOS arm64, Python 3.11.17,
NumPy 2.4.6 with pandas 3.0.6 and 3.1.1. Inputs with fewer than 20 recent rows
also exercise the unchanged early return. The probe, output and generated
source archive are `drift-null-zero.py.txt`, `drift-null-zero-output.txt` and
`drift-generated.py.gz` in `evidence/pending-probes-2026-11-15/`.

This is a conditional owner proposal, not an approval. It does not prove every
supported pandas dtype/version or a Linux execution, and no current full unit
score has been measured. Run with the generated inventory present:

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/pending-probes-2026-11-15/drift-null-zero.py.txt
```

Evidence confidence: medium for the tested numeric dtypes and pandas builds;
other supported dtypes and platforms remain untested. The owner decision remains
separate.
