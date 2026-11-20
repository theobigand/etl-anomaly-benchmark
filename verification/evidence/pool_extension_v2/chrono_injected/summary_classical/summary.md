# Chronological study with controlled injection

7 real time-series tables. Differences are chronological minus random.

| detector | FPR difference (median, 95% CI) | recall difference | higher FPR |
|---|---|---|---|
| copod | -0.001 [-0.020, +0.175] | +0.018 [-0.012, +0.234] | 3/7 |
| ecod | +0.015 [-0.010, +0.127] | +0.014 [+0.005, +0.147] | 5/7 |
| great_expectations | +0.052 [+0.010, +0.145] | +0.017 [+0.009, +0.055] | 7/7 |
| hbos | +0.012 [-0.025, +0.055] | -0.002 [-0.010, +0.039] | 4/7 |
| iqr | +0.049 [-0.007, +0.222] | +0.003 [-0.031, +0.050] | 5/7 |
| isolation_forest | +0.001 [-0.020, +0.101] | +0.013 [+0.006, +0.135] | 4/7 |
| knn | +0.163 [+0.052, +0.839] | +0.079 [+0.018, +0.235] | 7/7 |
| lof | +0.197 [+0.072, +0.870] | +0.080 [+0.029, +0.249] | 7/7 |
| ocsvm | +0.013 [-0.022, +0.095] | +0.006 [-0.019, +0.028] | 5/7 |
| pca | +0.062 [+0.002, +0.359] | +0.042 [+0.013, +0.170] | 6/7 |
| zscore | -0.016 [-0.018, +0.106] | -0.016 [-0.023, +0.014] | 3/7 |

C1 median detector FPR difference: +0.0153
C2 median detector recall difference: +0.0140 (smaller in magnitude than the FPR difference: True)
C3 mean rank correlation of detector recall between the arms: 0.97
