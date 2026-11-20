# Typed injection on mixed-schema and small tables

86 tables from 76 independent sources (tier A 49, tier B 37).

Median recall over sources, by detector and fault type:

| method | cross_column_swap | distribution_shift | duplicate | invalid_code | invalid_format | missing_value | multivariate_outlier | univariate_outlier |
|---|---|---|---|---|---|---|---|---|
| ae1svm | 0.8 | 0.48 | 0.14 | 0.26 | 0.71 | 0.18 | 0.25 | 0.51 |
| autoencoder | 0.87 | 0.76 | 0.17 | 0.93 | 0.78 | 0.53 | 0.5 | 0.62 |
| deep_svdd | 0.83 | 0.69 | 0.2 | 0.78 | 0.77 | 0.47 | 0.31 | 0.57 |
| dif | 0.83 | 0.74 | 0.2 | 0.89 | 0.72 | 0.43 | 0.54 | 0.62 |
| lunar | 0.72 | 0.63 | 0.18 | 0.6 | 0.75 | 0.37 | 0.46 | 0.67 |
| transform_dedup | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| vae | 0.8 | 0.48 | 0.13 | 0.19 | 0.69 | 0.16 | 0.24 | 0.47 |

M1 mean rank correlation with the numeric protocol: None
M2: {"invalid_code": {"rules": NaN, "distance_density": NaN}, "cross_column_swap": {"rules": NaN, "distance_density": NaN}}

M3 (tier B against tier A), Holm-adjusted:

|  | median_A | median_B | p | p_holm |
|---|---|---|---|---|
| ae1svm | 0.424 | 0.415 | 0.39 | 1.0 |
| autoencoder | 0.589 | 0.638 | 0.729 | 1.0 |
| deep_svdd | 0.544 | 0.58 | 0.564 | 1.0 |
| dif | 0.535 | 0.645 | 0.0 | 0.001 |
| lunar | 0.544 | 0.498 | 0.015 | 0.088 |
| transform_dedup | 0.125 | 0.143 | 0.377 | 1.0 |
| vae | 0.403 | 0.406 | 0.483 | 1.0 |
