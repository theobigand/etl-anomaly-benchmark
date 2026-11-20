# Schema-rule baseline against the archived detectors

Tables: 86. Median false-positive rate on clean rows 0.053; 48% of tables at or below 0.05.

| Fault type | Tables | Sources | Baseline | Best archived | Rule detectors | Other detectors | Baseline >= best (tables) | Baseline - best, source median [95 %] |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| invalid_code | 64 | 58 | 1.00 | 1.00 | 0.08 | 0.31 | 98% | +0.00 [+0.00, +0.00] |
| cross_column_swap | 77 | 67 | 0.72 | 1.00 | 0.27 | 0.79 | 35% | -0.24 [-0.38, -0.07] |
| missing_value | 86 | 76 | 1.00 | 0.96 | 0.25 | 0.20 | 100% | +0.04 [+0.00, +0.07] |
| univariate_outlier | 73 | 64 | 1.00 | 1.00 | 0.55 | 0.54 | 85% | +0.00 [+0.00, +0.00] |
| multivariate_outlier | 66 | 57 | 0.07 | 0.80 | 0.04 | 0.30 | 9% | -0.66 [-0.72, -0.44] |
| invalid_format | 73 | 64 | 0.93 | 1.00 | 0.80 | 0.71 | 49% | -0.04 [-0.05, +0.00] |
| distribution_shift | 86 | 76 | 0.16 | 0.93 | 0.14 | 0.55 | 8% | -0.67 [-0.74, -0.60] |
| duplicate | 86 | 76 | 0.04 | 0.40 | 0.02 | 0.16 | 5% | -0.31 [-0.40, -0.24] |
