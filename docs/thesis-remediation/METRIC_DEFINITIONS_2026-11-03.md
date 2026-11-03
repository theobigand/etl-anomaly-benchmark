# AP definition and baseline evidence — 2026-11-03

Tracking: #91, T090, T094–T096, T098, T099. Baseline: `901cced`.

## Ready and scope

The implementation already computes non-interpolated Average Precision (AP), under the
historical `pr_auc` field in `src/etl_benchmark/metrics.py`. The labelled and pool runners
reuse that function; `research/pool_full.py` also computes AP directly for stored curves.
`tests/test_metric_contract.py::test_golden_metrics_use_continuous_scores` independently
expects AP = 5/6. No metric computation or experiment protocol is changed.

Acceptance: the manuscript defines the implemented metric, distinguishes trapezoidal PR
area, states score orientation and tie handling, qualifies the no-skill reference, and
separates ranking from threshold metrics. Existing numeric tables and lineage must remain
valid; the PDF must compile and the manuscript manifest must identify the revised files.
Documentation-only validation is permitted by `verification/README.md`; RED/GREEN is not
applicable because executable behavior is unchanged.

Environment: Python 3.11.17, scikit-learn 1.9.1 in the existing `etl-benchmark` Conda
environment. Both `verification/environment/conda-darwin-arm64.explicit.txt` and the
Linux lock name scikit-learn 1.9.1. The
[official versioned metric documentation](https://scikit-learn.org/1.9/modules/generated/sklearn.metrics.average_precision_score.html)
defines recall-weighted precision without interpolation. This supports the AP equation;
the finite-sample random-ranking calculation below is derived separately.

## Finite-sample calculation

For n rows and m positives, uniformly random strict rankings have

    E[AP] = m/n + (n-m)/(n(n-1)) (H_n - 1),  H_n = sum_{k=1}^n 1/k.

To derive this, condition on a positive at rank k. Its probability is m/n, and the
expected positive count through that rank is 1 + (k-1)(m-1)/(n-1). Sum precision
contributions over ranks and divide by m. This assumes 0 < m < n and no ties.
For fixed prevalence the correction vanishes as n grows. A constant-score predictor
has one tied group and AP = m/n exactly. Prevalence is therefore a reference precision,
not an exact finite-sample mean AP for random strict rankings.

The following acceptance check was run in the existing environment (no dataset access,
random seed or Monte Carlo estimate is involved):

```python
from fractions import Fraction
from itertools import combinations
from math import isclose
import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, auc
from etl_benchmark.metrics import compute_metrics

count = 0
for n in range(2, 8):
    for m in range(1, n):
        harmonic = sum(Fraction(1, k) for k in range(1, n + 1))
        expected = Fraction(m, n) + Fraction(n - m, n * (n - 1)) * (harmonic - 1)
        values = []
        for positives in combinations(range(n), m):
            y = np.zeros(n, dtype=int)
            y[list(positives)] = 1
            measured = average_precision_score(y, -np.arange(n))
            manual = sum(Fraction(int(y[: k + 1].sum()), k + 1) for k in positives) / m
            assert isclose(measured, float(manual), abs_tol=1e-14)
            assert isclose(average_precision_score(y, np.zeros(n)), m / n, abs_tol=1e-14)
            values.append(measured)
            count += 1
        assert isclose(float(np.mean(values)), float(expected), abs_tol=1e-14)
y, scores = [0, 1, 0, 1], [0.1, 0.9, 0.8, 0.2]
a = compute_metrics(y, [False, True, True, False], scores)
b = compute_metrics(y, [False, False, False, False], scores)
p, r, _ = precision_recall_curve(y, scores)
assert isclose(a["pr_auc"], 5 / 6)
assert isclose(auc(r, p), 19 / 24)
assert a["pr_auc"] == b["pr_auc"] and a["roc_auc"] == b["roc_auc"]
assert a["f1"] != b["f1"]
assert count == 240
```

Result: PASS, all 240 strict rankings for n=2 through 7 and every non-degenerate class
count. Constant-score AP, exact expected AP, AP versus trapezoidal area and ranking
invariance to changed flags all passed. Example: n=4, m=2 gives E[AP] = 49/72,
versus prevalence 1/2. These are mathematical checks, not a new empirical study.

## Remaining requirements

T091–T093 remain open: PR-AUC display text still occurs in Results, tables, plot sources
and figures. The Methods section explicitly identifies these as historical AP labels.
Do not rename stored fields or restamp sealed runs to perform a display correction.
T097 remains open: evaluation prevalence needs consistent presentation alongside AP,
including per-split accounting. #92 owns coordinated figure/table lineage; #93/#83 own
source-aware inference. No issue-level acceptance criterion is declared satisfied yet.

Validation outcomes and gate applicability: [shared validation record](VALIDATION_2026-11-03.md).
