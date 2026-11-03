# Inductive detector audit — 2026-11-03

Scope: #89, T045–T047 and T051–T054; shared classification evidence for #97, T255. Baseline: `f7a388a`.
This is a dated clarification of the implementation already evaluated, not a revision
of preregistered hypotheses or a new detector-performance experiment. Historical
`verification/full_registry.md`, sealed runs and negative outcomes remain intact.

## Ready and acceptance

The paper conflated copula motivation with the implemented marginal calculation and
claimed general singleton equivalence to PyOD. Inspect the pinned source, characterize
actual adapters, run existing contract tests before editing, and correct paper/slides
together. Acceptance requires exact scoring semantics, bounded invariance evidence,
explicit algorithm-change limitations, unchanged scientific fingerprints and result
values, rebuilt publication artifacts and applicable verification gates.

Documentation-only validation-first applies. No production code, tests, dependency,
threshold, partition or training procedure changes; no artificial RED/GREEN is claimed.

## Pinned sources and task reconciliation

Versions and full installed-module SHA-256 hashes are recorded in
[inductive-sources-2026-11-03.json](evidence/inductive-sources-2026-11-03.json).
The environment uses Python 3.11.17, PyOD 3.6.7, NumPy 2.4.6, SciPy 1.17.1,
scikit-learn 1.9.1 and PyTorch 2.14.1. No packages were installed or upgraded.

- T045: distinguish the [original COPOD copula motivation](https://arxiv.org/html/2009.09463v1)
  from the implemented additive marginal score. General copulas model dependence;
  this evaluated calculation does not fit an arbitrary joint copula. Moderate marginal
  contributions can still accumulate into a large score, so categorical claims that
  column-wise methods can never flag a multivariate anomaly are unjustified.
- T046/T047: inspected installed `COPOD.decision_function` and
  `ECOD.decision_function`, corroborated by official PyOD 3.6.7
  [COPOD source](https://pyod.readthedocs.io/en/latest/_modules/pyod/models/copod.html)
  and [ECOD source](https://pyod.readthedocs.io/en/latest/_modules/pyod/models/ecod.html).
  With left/right negative-log tails uL/uR, the skew term uS is uL (negative skew),
  uR (positive skew), or uL+uR (zero skew). ECOD sums max(uL,uR,uS); COPOD sums
  max(uS,(uL+uR)/2). The latter averages log surprisals, not probabilities.
- T051: `TailProbabilityModel` freezes sorted training columns and skew signs. Query
  tails use (inclusive training rank + 1)/(n+1), including ties on both sides. Training
  thresholds use the quantile of those adapted training scores, which can also differ
  from upstream. `FitScalerDIF` fits a separate representation scaler for each network
  during training and reuses it before tanh; upstream fits a scaler to each represented
  batch. `MeanVAE` decodes the latent mean and measures Euclidean reconstruction
  distance; upstream samples its latent code. This is not the expected error across
  latent draws. Official [DIF](https://pyod.readthedocs.io/en/latest/_modules/pyod/models/dif.html)
  and [VAE](https://pyod.readthedocs.io/en/latest/_modules/pyod/models/vae.html) sources
  corroborate the inspected installed functions.
- T052/T053: the row-level ETL contract excludes other evaluation rows from a score.
  `tests/test_registry_contract.py` applies the singleton/batch check to exactly 17
  row-level detectors. The eighteenth registry name, `drift`, is explicitly exempt
  because it evaluates a recent time window. Neural score comparisons use rtol=1e-4,
  atol=1e-5 for float32; other models use atol=1e-9 with NumPy's default rtol.
  Passing these finite fixtures is bounded evidence, not a universal proof.
- T054/T255: frozen skew/tails, latent-mean inference, representation scaling and the
  reconstruction-based PCA score are algorithm-changing protocol choices, not proof
  that the evaluated models equal upstream defaults. AE1SVM singleton padding avoids
  execution failures but repeating its final training row also changes its weight.
  The manuscript now states that limitation. Separate paired adaptation ablations in
  #97 remain outstanding; existing experiment results are not replaced or relabelled.

The old singleton-comparison test in `tests/test_ml.py` checks three probe rows on one
fixture. It passes, but it does not establish general equivalence. The following two
counterexamples characterize the frozen-skew distinction without changing any code:

```python
import numpy as np
from pyod.models.ecod import ECOD
from pyod.models.copod import COPOD
from etl_benchmark.quality.ml import TailProbabilityModel

cases = [
    (
        "ecod",
        ECOD,
        np.array([-1.0, 0.0, 1.0])[:, None],
        np.array([[0.5]]),
        np.log(8 / 3),
        np.log(2),
    ),
    (
        "copod",
        COPOD,
        -(np.arange(100.0) ** 2)[:, None],
        np.array([[1e6]]),
        np.log(101) / 2,
        np.log(101),
    ),
]
for method, cls, train, query, expected, expected_upstream in cases:
    adapted = TailProbabilityModel(0.05, method).fit(train)
    upstream = cls(contamination=0.05).fit(train)
    score = adapted.decision_function(query)[0]
    reference = upstream.decision_function(query)[0]
    assert np.isclose(score, expected)
    assert np.isclose(reference, expected_upstream)
    assert not np.isclose(score, reference)
    batch = np.vstack([query, [[1e9], [-1e9]]])
    assert np.isclose(score, adapted.decision_function(batch)[0])
```

PASS before publication edits: ECOD 0.9808292530117262 versus upstream 0.6931471805599453;
COPOD 2.30756025842063 versus upstream 4.61512051684126. The adapted score remains
unchanged when unrelated extreme query rows are added. This is an exact implementation
characterization on constructed inputs, not a claim about dataset-level AP or rankings.

## Validation and remaining work

Baseline before edits:
`pytest tests/test_ml.py tests/test_registry_contract.py tests/test_deep_detectors.py tests/test_ae1svm_batches.py -q`
passed all 200 cases, including the 17 batch-independence checks. Existing tests are
reused; none is weakened or replaced.

Publication/regression and build outcomes are recorded below when checked. Scientific
and measurement fingerprints match `f7a388a`; only current TeX/PDF hashes change in the
publication manifest using the existing `--manifest-only` procedure. No scientific replay
is required by this documentation-only correction; the historical #82 replay gap remains.

T048–T050/T055 and T056–T070 stay open. Full detector inventories, convergence checks,
preprocessing/leakage audits and #97 ablations are not completed by this clarification.
No issue-level closure or release certification is claimed.

### Publication checkpoint

- Combined regression: 223 cases passed with the four baseline files plus
  `tests/test_publication_tables.py`, `tests/test_manuscript_claims.py` and
  `tests/test_artifact_lineage.py`.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=/tmp/etl-inductive-paper main.tex`
  from `paper/`: PASS, 23 pages, no undefined references or overfull boxes. An initial
  invocation from the repository root failed to locate main.tex; the working directory
  was corrected without changing the build configuration. The revised Methods pages
  were inspected as rendered images. Final submission page-budget review remains #101.
- `make slides CHROME=<Chromium launcher>`: PASS with Google Chrome 155.0.8059.80;
  39 pages. All slide contact sheets and the new adaptation slide were inspected.
- 1280×720 content-viewport text/table/image bounds, footer placement and keyboard
  navigation: PASS for all 39 slides, with final HTML/PDF hashes in
  [geometry evidence](evidence/inductive-slides-geometry-2026-11-03.json).
- Every pre-existing slide table retains its numeric cells; presentation voice check
  passed. Scientific source, historical protocols and run records remain unchanged.

### Final local verification

`make verify-fast`: PASS, exit 0; 1292 passed, 27 deselected, 300 expected small-fixture
Isolation Forest warnings; 1790/1790 executable statements and 350/350 branches covered.
Full output is preserved in [FAST evidence](evidence/inductive-fast-2026-11-03.txt).
`make lint` and `git diff --check` pass. No verification assertion or acceptance criterion
was changed. Both recorded characterization examples execute successfully.

The canonical inventory retains exactly T001–T415 once each. This unit adds seven
verified #89 tasks and shared T255 in #97, bringing the checked total to 22.
T255 reuses the source audit; the performance/ranking/cost ablations remain outstanding.

DEEP, FAULTS, REAL, typing, verifier coverage and locked-environment reproduction were
not rerun locally for documentation-only changes. No scientific code, test, protection,
verifier or dependency changed. Integration CI runs its configured checks independently.
No clean-revision release certification or independent attestation is claimed.

