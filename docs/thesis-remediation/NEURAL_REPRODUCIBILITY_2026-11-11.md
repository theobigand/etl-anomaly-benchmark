# Neural numerical reproducibility probe - 2026-11-11

Exploratory. Evidence: `docs/thesis-remediation/evidence/neural-repro-2026-11-11/` (`neural_repro.py`,
`out/results.json`, `single_thread_repeat.py/.json`, `archive_vs_new_medians_2pct.json`). The archived
experimental protocol and the neural alert-budget records are unchanged.

## Design

3 problems (`adbench:breastw`, `adbench:cardio`, `adbench:musk`), seeds 42 and 1, four detectors
(AE1SVM, LUNAR, Deep SVDD and the autoencoder as a control): 24 fits. Each fit ran in a fresh process
under 7 configurations: 4 threads three times (a, b, c), 1, 2 and 10 threads, and 4 threads with
`torch.use_deterministic_algorithms(True)`. The same fitted model scored the held-out rows twice. For each
run the fit scores, held-out scores, the 2% training-score threshold, the alert flags, recall, precision,
ROC-AUC and average precision were kept; arrays are summarized by hashes and differences.

Environment: Apple M4 (arm64, 10 cores), macOS 27.2, Python 3.11.17, torch 2.14.1 (default 4 threads),
numpy 2.4.6, pandas 3.0.6, scipy 1.17.1, scikit-learn 1.9.1. Seeds are the repetition seed; threading
variables `OMP/MKL/OPENBLAS/VECLIB_MAXIMUM_THREADS` equal the thread count; `PYTHONHASHSEED=0`.
The archived runs were made on another environment that is not recorded in the archive, so the
historical and the new environments cannot be compared reliably; only effects measured here are claimed.

## Findings

- Inference on a fitted model is repeatable: scoring twice gave identical arrays in all 168 runs.
- Same configuration, separate processes (4 threads, a/b/c): AE1SVM, LUNAR and the autoencoder are
  bitwise identical in all 6 cases. Deep SVDD is not (bitwise in 1 or 2 of 6): differences are at most
  9.3e-4 in score, Spearman at least 0.999, and no alert flag changes. A single-thread repeat (4 fits per
  case on 3 cases each) is bitwise for AE1SVM and LUNAR but not for Deep SVDD (up to 1.5e-4), so Deep SVDD's
  noise does not come from the thread count.
- Thread count: the autoencoder is bitwise invariant (1, 2, 4, 10). AE1SVM changes materially: maximum
  score difference 2.8 to 3.7 and Spearman as low as 0.82 against the 4-thread run; 4, 7 and 11 held-out
  flags change at 1, 2 and 10 threads. LUNAR changes at 1 thread (difference up to 1.8, Spearman 0.94,
  3 flag changes) and at 2 and 10 threads (up to 0.33), without a flag change there. Deep SVDD stays within
  its own noise.
- `use_deterministic_algorithms(True)` changed nothing at 4 threads (bitwise equal to the default for
  AE1SVM and LUNAR; Deep SVDD still within its noise): the thread-dependent behaviour is not removed by it
  and is not reported as an error by it.
- Scientific effect of a configuration change on one fit, largest spread across the 7 configurations:
  AE1SVM 2% alert rate 2.9 points, recall 11.1 points, ROC-AUC 14.6 points; LUNAR 1.5, 2.8 and 0.8;
  Deep SVDD 0.4, 6.7 (a few positives on a small test set) and 0.9; autoencoder 0.
- In aggregate the effect is small. Median over the 100 problems of the 2% alert rate, recall and
  precision, archive against the new run (`archive_vs_new_medians_2pct.json`): AE1SVM 0.0217 and 0.0217,
  0.0395 and 0.0400, 0.130 and 0.112; LUNAR 0.0230 and 0.0244, 0.0472 and 0.0513, 0.133 and 0.135; Deep SVDD,
  autoencoder, DIF and VAE agree to the printed digits.

## Reading

Distinguish three levels. Bitwise reproducibility: holds for the autoencoder, and for AE1SVM and LUNAR only
at a fixed thread count; it does not hold for Deep SVDD. Numerical tolerance: Deep SVDD is within about
1e-3 and rank-preserving. Scientific reproducibility: per-run AE1SVM results (and, less, LUNAR) depend on
the thread configuration and should be treated as one realization, while the pool medians used in the
alert-budget report are stable. Bitwise identity across libraries or machines is not required and is not
guaranteed by the supported numerical libraries.

## Configuration for future confirmatory neural work (a proposal, not applied retroactively)

Run with one PyTorch thread and the matching BLAS/OpenMP variables set to 1, one fit per process, and
record the torch, numpy, scikit-learn and pandas versions, the CPU, the thread count and the seed in the
run manifest. Reason: with one thread, the scheduling-dependent reductions that change AE1SVM and LUNAR
are removed, and repeated single-thread fits were bitwise identical for both. Deep SVDD remains
noisy at the 1e-4 level and is compared under a tolerance. The historical protocol and records are not
changed, and the 3,000 neural seed runs were not rerun.

## Limits

3 problems, 2 seeds, one machine; DIF and VAE were not probed here (they matched the archive exactly in
the budget run); the source of Deep SVDD's run-to-run noise was not isolated; no claim is made about
other CPUs or builds of PyTorch.
