"""Probe of the synthetic PCA discrepancy; run from the repository root with the interpreter to test.

python docs/thesis-remediation/evidence/pca_probe.py
"""

import sys, numpy as np

sys.path[:0] = ["experiments", "src", "."]
import run_curves as rc
from etl_benchmark.pipeline import detect
from etl_benchmark.registry import all_detectors
from sklearn.metrics import average_precision_score

train_x, test_x, y, cont, names, base = rc._split_synth(42, None)
dets = [d for d in all_detectors(ml_contamination=cont, names=names) if d.name == "pca"]
det = dets[0]
res = detect(test_x, det, fit_df=train_x)
print("AP", round(average_precision_score(y, np.asarray(res.scores, float)), 4))
est = [v for k, v in vars(det).items() if hasattr(v, "pca_")] or [getattr(det, "estimator_", None)]
print(type(est[0]))
p = est[0].pca_
cum = np.cumsum(p.explained_variance_ratio_)
print("n_components", p.n_components_, "cum", np.round(cum, 6).tolist())
s = np.asarray(res.scores, float)
print("score min/median/max", s.min(), np.median(s), s.max())
