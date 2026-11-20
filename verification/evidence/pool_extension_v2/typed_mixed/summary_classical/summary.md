# Typed injection on mixed-schema and small tables

86 tables from 76 independent sources (tier A 49, tier B 37).

Median recall over sources, by detector and fault type:

| method | cross_column_swap | distribution_shift | duplicate | invalid_code | invalid_format | missing_value | multivariate_outlier | univariate_outlier |
|---|---|---|---|---|---|---|---|---|
| copod | 0.64 | 0.58 | 0.17 | 0.15 | 0.45 | 0.14 | 0.31 | 0.41 |
| drift | 0.0 | 0.11 | 0.04 | 0.01 | 0.0 | 0.02 | 0.08 | 0.0 |
| ecod | 0.65 | 0.57 | 0.17 | 0.17 | 0.52 | 0.12 | 0.36 | 0.47 |
| great_expectations | 0.0 | 0.01 | 0.0 | 0.0 | 0.7 | 0.74 | 0.0 | 0.44 |
| hbos | 0.5 | 0.44 | 0.16 | 0.17 | 0.39 | 0.13 | 0.22 | 0.26 |
| iqr | 0.82 | 0.37 | 0.08 | 0.1 | 0.96 | 0.1 | 0.37 | 1.0 |
| isolation_forest | 0.58 | 0.58 | 0.16 | 0.21 | 0.41 | 0.18 | 0.31 | 0.32 |
| knn | 0.9 | 0.6 | 0.11 | 0.33 | 0.72 | 0.24 | 0.29 | 0.6 |
| lof | 0.74 | 0.52 | 0.12 | 0.39 | 0.74 | 0.27 | 0.39 | 0.6 |
| ocsvm | 0.88 | 0.54 | 0.15 | 0.24 | 0.73 | 0.19 | 0.29 | 0.57 |
| pca | 0.62 | 0.59 | 0.18 | 0.95 | 0.58 | 0.48 | 0.38 | 0.45 |
| transform_dedup | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| zscore | 0.82 | 0.55 | 0.16 | 0.43 | 0.75 | 0.26 | 0.08 | 0.52 |

M1 mean rank correlation with the numeric protocol: 0.8373641924830911
M2: {"invalid_code": {"rules": 0.08492135511191773, "distance_density": 0.28692493946731235}, "cross_column_swap": {"rules": 0.2857142857142857, "distance_density": 0.7752525252525253}}

M3 (tier B against tier A), Holm-adjusted:

|  | median_A | median_B | p | p_holm |
|---|---|---|---|---|
| copod | 0.368 | 0.349 | 0.509 | 1.0 |
| drift | 0.038 | 0.059 | 0.227 | 1.0 |
| ecod | 0.385 | 0.361 | 0.463 | 1.0 |
| great_expectations | 0.194 | 0.291 | 0.146 | 1.0 |
| hbos | 0.303 | 0.303 | 0.722 | 1.0 |
| iqr | 0.471 | 0.462 | 0.941 | 1.0 |
| isolation_forest | 0.364 | 0.363 | 0.917 | 1.0 |
| knn | 0.463 | 0.473 | 0.698 | 1.0 |
| lof | 0.447 | 0.448 | 0.769 | 1.0 |
| ocsvm | 0.424 | 0.444 | 0.102 | 1.0 |
| pca | 0.489 | 0.51 | 0.176 | 1.0 |
| transform_dedup | 0.125 | 0.143 | 0.377 | 1.0 |
| zscore | 0.411 | 0.408 | 0.95 | 1.0 |
