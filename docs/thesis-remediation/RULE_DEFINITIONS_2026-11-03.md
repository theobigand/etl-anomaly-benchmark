# Rule-definition audit and correction — 2026-11-03

Tracking: #89, T037–T044. Baseline: `901cced`; follows the independent #91 definition unit.

## Ready and scientific scope

The existing Methods text already uses `$3\sigma$` and `$2.7\sigma$`: T037 and T038
were already implemented and require verification, not a repeated fix. It does not define
the fitted Z-score explicitly and describes the Great Expectations suite too broadly.
Acceptance: describe the actual rules and their fitted statistics, qualify alert-rate
interpretation and restrict conclusions to the generic suite evaluated here.

Affected files are the manuscript, rebuilt PDF, current publication manifest and this
roadmap evidence. No source behavior, registered protocol, label access, partition,
random seed or numerical result changes. Documentation-only validation is allowed by
`verification/README.md`; no artificial RED/GREEN is claimed.

## Task reconciliation

- T037/T038: correct sigma notation was present before the edit and remains in the PDF.
- T039: `quality/rules.py::ZScoreDetector` uses training means and sample standard
  deviations (`values.std()`), maximum absolute standardized deviation and a strict
  threshold greater than 3. A zero standard deviation gives no flag and zero score
  contribution. The Methods equation and edge-case description now state these choices.
- T040: `IQRDetector` uses training quartiles, a 1.5 multiplier, strict fence violations
  and a nonnegative maximum exceedance normalized by IQR. Zero-IQR columns contribute
  zero. The manuscript distinguishes population-normal per-column tail references
  from fitted multivariate row-level alert rates. The independence formula is explicitly
  illustrative; no independence assumption is added to the experimental protocol.
- T041/T042: `quality/gx.py::GreatExpectationsDetector` fits not-null checks on every
  column and numeric bounds at quantiles 0.001/0.999. Undefined or coincident bounds
  are omitted. Range boundaries are inclusive; score is the violated fraction of active
  expectations and any violation flags a row. The revised paragraph states these facts.
- T043/T044: the text identifies fitted percentile bounds as univariate statistical
  detection expressed declaratively. It makes no claim to evaluate domain-informed,
  cross-field, category or format rules. This qualification is necessary for #95's future
  fairness study; it does not substitute for that experiment.

The sample-standard-deviation and fence-score examples are already asserted by
`tests/test_detector_contracts.py`. `tests/test_gx.py` verifies null/range violations,
index preservation and the omission of constant-feature bounds. Source inspection plus
these checks establish what this implementation does, not a general property of rules.

## Gaussian reference calculation

Run in the existing Conda environment:

```python
from math import isclose
from scipy.stats import norm

q = norm.ppf(0.75)
fence = 4 * q
z_tail = 2 * norm.sf(3)
iqr_tail = 2 * norm.sf(fence)
assert isclose(fence, 2.697959000784327, abs_tol=1e-12)
assert 0.00269 < z_tail < 0.00271
assert 0.00697 < iqr_tail < 0.00698
```

PASS: population IQR fences at 2.697959000784 sigma; two-sided tail 0.69766032%,
compared with 0.26997961% beyond 3 sigma. These arithmetic references are not estimated
false-alarm rates for the benchmark datasets.

## Remaining scope

T045–T070 remain open: pinned-source algorithm descriptions, full implementation and
feature-access inventory, adaptation audits, neural convergence and preprocessing/leakage
reconciliation. Existing detector tests are reusable evidence, not automatic completion
of those tasks. No #89 issue-level closure or release certification is claimed.
