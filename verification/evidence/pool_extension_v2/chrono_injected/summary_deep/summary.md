# Chronological study with controlled injection

7 real time-series tables. Differences are chronological minus random.

| detector | FPR difference (median, 95% CI) | recall difference | higher FPR |
|---|---|---|---|
| ae1svm | -0.003 [-0.038, +0.097] | +0.016 [-0.007, +0.049] | 3/7 |
| autoencoder | +0.147 [-0.000, +0.557] | +0.060 [+0.014, +0.187] | 5/7 |
| deep_svdd | +0.095 [+0.020, +0.649] | +0.069 [+0.030, +0.168] | 6/7 |
| dif | +0.021 [-0.027, +0.166] | +0.002 [-0.030, +0.054] | 4/7 |
| lunar | +0.162 [+0.100, +0.823] | +0.090 [+0.020, +0.211] | 7/7 |
| vae | +0.023 [-0.008, +0.253] | +0.014 [+0.004, +0.048] | 5/7 |

C1 median detector FPR difference: +0.0589
C2 median detector recall difference: +0.0378 (smaller in magnitude than the FPR difference: True)
C3 mean rank correlation of detector recall between the arms: 0.88
