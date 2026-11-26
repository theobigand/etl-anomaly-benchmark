# Statistical validity of the labelled-pool rankings

Problems 100; independent source groups 80 (units of inference). Friedman over 75 sources and 10 detectors: p = 4.52e-19. Pairs significant after Holm: 17 of 136. Five-seed versus ten-seed ranking, Kendall tau 0.91.

V3: best knn against second isolation_forest: median AP difference +0.002 [-0.011, +0.013], p (Holm) 1.000.

| Detector | Mean rank (10 seeds) | 95 % interval | Mean rank (5 seeds) |
|---|---:|---|---:|
| knn | 4.50 | 3.99 to 5.02 | 7.15 |
| isolation_forest | 4.55 | 4.05 to 5.09 | 7.28 |
| hbos | 4.67 | 4.01 to 5.35 | 7.24 |
| copod | 4.79 | 4.20 to 5.40 | 7.55 |
| ecod | 4.87 | 4.28 to 5.49 | 7.43 |
| zscore | 5.35 | 4.81 to 5.88 | 8.66 |
| pca | 5.49 | 4.87 to 6.12 | 8.69 |
| lof | 5.62 | 4.96 to 6.28 | 8.97 |
| iqr | 6.87 | 6.21 to 7.49 | 10.51 |
| great_expectations | 8.28 | 7.74 to 8.77 | 13.51 |

| Families | Median difference | 95 % interval | p (Holm) |
|---|---:|---|---:|
| classical - neural | +0.071 | +0.025 to +0.117 | 1.000 |
| classical - rule | +0.035 | +0.019 to +0.063 | 0.000 |
| neural - rule | +0.001 | -0.037 to +0.038 | 1.000 |

## Label rules

| Rule | Problems | Sources | Kendall tau vs R0 | R0 leader | its rank | Leader under the rule |
|---|---:|---:|---:|---|---:|---|
| R1 | 58 | 54 | 0.78 | knn | 1 | knn |
| R2 | 64 | 60 | 0.81 | knn | 1 | knn |
| R3 | 64 | 60 | 0.67 | knn | 4 | hbos |
| R4 | 25 | 24 | 0.38 | lof | 6 | isolation_forest |
| R5 | 24 | 22 | 0.42 | lof | 4 | knn |
