# Neural budget-sufficiency probe (T055)

Date: 2026-11-19. Code: `research/neural_budget_probe.py`. Output:
`verification/evidence/neural_budget_probe/neural_budget_probe.json`.

## Why this probe

PyOD 3.6.7 exposes no loss history for the VAE, Deep SVDD, AE1SVM and LUNAR, so convergence
cannot be read from training curves (see `NEURAL_CONVERGENCE_AUDIT_2026-11-07.md`). The probe
instead asks whether the registry epoch budget is sufficient: scores at the registry budget are
compared with scores at three times that budget, same seed and same train-only partition.

## Protocol (declared before the run)

- 8 labelled problems with 300-5000 rows, sorted by id and evenly spaced (`select`).
- Seeds 42, 1, 2; grouped 70/15/15 split of `research.pool_train_only_replay`, frozen
  preprocessing of `research.pool_preprocessing.prepare_frozen`.
- Budgets (1x / 3x): VAE 30/90, Deep SVDD 100/300, AE1SVM 50/150, LUNAR 200/600 epochs.
- DIF has no epoch budget: Spearman correlation of scores across model seeds on one fixed
  partition. Autoencoder: the existing `settings()` record (`n_iter`, `max_iter`, `converged`).

A first version of the DIF check compared scores across different seeds' test partitions, which
is not meaningful. It was corrected to a fixed partition and recomputed; the invalid values are
kept in the JSON under `dif_seed_spearman_old_invalid` and must not be used.

## Results (24 runs per detector, no non-finite scores, no warnings)

| Detector | Spearman 1x vs 3x, median (min) | Change in AP at 3x, median / mean | Largest absolute change |
| --- | --- | --- | --- |
| VAE | 0.905 (0.812) | +0.002 / +0.008 | 0.086 |
| Deep SVDD | 0.740 (0.325) | -0.022 / -0.034 | 0.192 |
| AE1SVM | 0.961 (0.862) | -0.002 / 0.000 | 0.043 |
| LUNAR | 1.000 (0.819) | 0.000 / -0.013 | 0.318 |

- DIF seed-to-seed Spearman on a fixed partition: 0.73 to 0.99 (per-problem means from 0.74 to 0.98).
- Autoencoder: 8 of 24 runs report `converged: true`; 16 of 24 reach `max_iter` (300).
  The 8 converged runs are on the three largest problems; all small UCI problems hit the cap.

## Interpretation and limits

- Tripling the budget does not systematically raise AP for any of the four detectors; for Deep
  SVDD it lowers it on average. The registry budgets are therefore not shown to be too small.
- Rankings are not identical across budgets (Deep SVDD median 0.74), so individual-problem AP is
  budget-sensitive. Neural results stay qualified as "out-of-the-box CPU configuration".
- The autoencoder frequently stops at its iteration cap; its small-problem results are
  not converged fits.
- 8 problems and 3 seeds: a bounded diagnostic, not proof of convergence and not a
  re-tuning study. The registry settings were not changed.
