# PCA precision-recall discrepancy, 2026-11-12

Question: why do regenerated PCA average-precision values differ from the legend of `paper/figures/pr_curves.png`
(Water Quality 0.54 against 0.57, synthetic 0.48 against 0.56)?

Findings
- The figure is the output recorded by `verification/evidence/run_curves.json` (SHA-256 4d1c2e74..., source revision
  8d245d2, clean tree, seed 42, pandas 3.0.6, scikit-learn 1.9.1, numpy 2.4.6, pyod 3.6.7, Python 3.11.17).
- No file under `src/` or `experiments/run_curves.py` changed since that revision.
- The local environment now has pandas 3.1.1. Re-running `scores_for` with the capture-time pandas 3.0.6 gives PCA AP
  0.5737 on Water Quality, which matches the archived 0.57. So the Water Quality difference is a dependency-version
  effect on the pipeline, not an error in the paper. The other ten curves of that panel match under both versions.
- The synthetic panel stays at 0.4818 under both pandas versions; the archived legend says 0.56. Unresolved. All ten
  other detectors match the archived legend on that panel. Tested and excluded: Faker 40.43.0 (the locked version) instead of 40.44.0 changes nothing. Candidates not yet tested: numerical sensitivity of the 95%-variance
  component count in `PCAReconstruction`, and BLAS threading.

Consequences
- The paper figure and its text are unchanged; historical values are preserved.
- Slide 22 draws curves regenerated under pandas 3.0.6; only the synthetic PCA curve differs from the paper figure, and
  the slide says so.
- The run manifest should record every package that touches the data (pandas is recorded; Faker is not, though `verification/environment/pip-freeze.txt` pins it). Not changed here
  because the manifest format is part of archived evidence.
- Next step if the synthetic value matters to a conclusion: re-run `make curves` in an environment built from
  `verification/environment/conda-darwin-arm64.explicit.txt`, which pins the capture-time versions.

## Addendum, 2026-11-13: mechanism of the synthetic difference

The two remaining candidates were tested. BLAS threading changes nothing (`OPENBLAS_NUM_THREADS`,
`VECLIB_MAXIMUM_THREADS` and `OMP_NUM_THREADS` set to 1 give the same 0.4818). The component count explains the
effect:

- On the synthetic panel the six features have cumulative explained variance 0.189, 0.357, 0.522, 0.683, 0.842, 1.000.
  The 95% rule therefore keeps all six components (`n_components_ = 6`), so the reconstruction is exact and every
  score is floating-point rounding noise (median 1.1e-32, maximum 1.5e-28). The ranking, and so the average precision,
  is decided by the rounding behaviour of the linear-algebra library.
- The same code, data, seed, numpy 2.4.6, scipy 1.17.1 and scikit-learn 1.9.1 give 0.4818 in the venv whose numpy
  wheel links Accelerate (`~/.cache/etl-mutation-venv`) and 0.5645 in the canonical conda environment `etl-benchmark`
  (reference BLAS/LAPACK 3.9.0). The archived legend, 0.56, is the second value.
- Correction of 2026-11-14: Water Quality is also full rank (9 of 9 components kept), so the 0.54 against 0.57 difference listed above is not only a pandas effect; it is the same rounding-noise sensitivity (see below).

Status. The archived value is not wrong for the environment that produced it, and nothing archived was changed. But the
synthetic PCA curve measures rounding noise, not reconstruction error, so it is not reproducible across numerical
back ends. This remains a scientific-integrity item for the owner: either state in the paper that PCA keeps every
component on the six-feature synthetic table and that its curve is back-end dependent, or choose a component rule that
does not retain all features (a protocol change, therefore not made here). The method comparison on this panel should not rest on this one curve.

Probe: `docs/thesis-remediation/evidence/pca_probe.py` prints one JSON record per interpreter; the two records of 2026-11-14 are in
`docs/thesis-remediation/evidence/l4-campaign-2026-11-13/pca-probe-results.json`. The comparison changes two things at once (the numpy wheel's BLAS
and the packaging), so it shows that the value follows the numerical back end, not which routine of it is responsible.

## Second addendum, 2026-11-14: scope of the sensitivity and the manuscript wording

Audit (`evidence/pca_degeneracy_audit.py`, records for two interpreters in `evidence/l4-campaign-2026-11-13/pca-degeneracy-audit.json`). The 95 % rule keeps every component, so the scores are rounding noise (median 1e-33 to 1e-30), for: the synthetic customer table (6 of 6), the transactions and sensors schemas (6 of 6), the real Water Quality table (9 of 9) and 2 of the 44 typed-injection carriers audited here (UCI 2 and 222). It does not for Credit Card (27 of 30), Cardio (14 of 21) or the other 42 carriers. Both interpreters agree on which tables are full rank. ADBench carriers and the labelled pool were not audited.

Effect (`evidence/pca_backend_recall.py`, `evidence/l4-campaign-2026-11-13/pca-backend-recall.json`): PCA recall on the synthetic customer table, mean over the five benchmark seeds, missing/duplicate/univariate/multivariate/drift/invalid. Conda reference BLAS: 0.10 / 0.12 / 1.00 / 0.48 / 0.23 / 0.58, the row archived in the paper. Numpy wheel linked to Accelerate: 0.07 / 0.11 / 0.99 / 0.35 / 0.23 / 0.69. The archived row therefore matches the reference-BLAS build, and the Accelerate build differs by 0.13 on multivariate outliers and 0.11 on invalid formats.

Interpretation adopted: the archived PCA rows of the full-rank tables are environment-dependent and must not be read as numerically robust or cross-platform reproducible results. Archived values are untouched. The manuscript (`paper/main.tex`, methodology, PCA description, and the threats-to-validity paragraph) and `README.md` now say so; the PDF was rebuilt and the manifest hashes of `paper/main.tex` and `paper/main.pdf` refreshed. The figure legend of `paper/figures/pr_curves.png` (PCA 0.56 on the synthetic panel) is unchanged and falls under the same sentence. Nothing claims stability that the evidence does not show, and no value was replaced.
