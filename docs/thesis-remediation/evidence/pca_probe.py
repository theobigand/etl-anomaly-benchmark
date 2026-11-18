# ruff: noqa: E402, E501
"""Probe of the synthetic PCA discrepancy (run from the repository root with the interpreter to test).

    python docs/thesis-remediation/evidence/pca_probe.py

Prints one JSON record: library versions and BLAS back end, the average precision of the PCA detector on the
synthetic split of `experiments/run_curves.py` (seed 42), the number of components kept, the cumulative explained
variance and the range of the scores.
"""

import json
import platform
import sys

import numpy as np

sys.path[:0] = ["experiments", "src", "."]
import run_curves as rc
import scipy
import sklearn
from sklearn.metrics import average_precision_score

from etl_benchmark.pipeline import detect
from etl_benchmark.registry import all_detectors

train_x, test_x, y, cont, names, base = rc._split_synth(42, None)
detector = next(d for d in all_detectors(ml_contamination=cont, names=names) if d.name == "pca")
result = detect(test_x, detector, fit_df=train_x)
scores = np.asarray(result.scores, float)
pca = next(v for v in vars(detector).values() if hasattr(v, "pca_")).pca_
blas = np.show_config(mode="dicts")["Build Dependencies"]["blas"]
print(
    json.dumps(
        {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit-learn": sklearn.__version__,
            "blas": {"name": blas.get("name"), "version": blas.get("version")},
            "average_precision": round(average_precision_score(y, scores), 4),
            "n_components": int(pca.n_components_),
            "cumulative_variance": [
                round(float(v), 6) for v in np.cumsum(pca.explained_variance_ratio_)
            ],
            "score_min": float(scores.min()),
            "score_median": float(np.median(scores)),
            "score_max": float(scores.max()),
        },
        indent=2,
    )
)
