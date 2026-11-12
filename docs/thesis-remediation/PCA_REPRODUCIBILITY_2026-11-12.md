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
