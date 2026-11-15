import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from etl_benchmark.quality.drift import TemporalDriftDetector

for p in ("src/etl_benchmark/quality/drift.py", "mutants/src/etl_benchmark/quality/drift.py"):
    print(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "mutmut")},
)
train = pd.DataFrame({"t": range(6), "x": [-1.0, 0.0, 1.0, 0.0, 0.0, 0.0]})
det = TemporalDriftDetector(time_column="t", columns=["x"], reference_frac=0.5).fit(train)
for label, values in {
    "positive": np.repeat(0.5, 32),
    "negative": np.repeat(-0.5, 32),
    "unmoved": np.repeat(0.0, 32),
    "outlier": np.r_[np.repeat(0.5, 31), 50.0],
    "small_window": np.repeat(0.5, 19),
    "with_missing": np.r_[np.repeat(0.5, 31), np.nan],
}.items():
    frame = pd.DataFrame({"t": np.repeat(3, len(values)), "x": values})
    original = det.xǁTemporalDriftDetectorǁ_row_score__mutmut_orig(frame)
    mutant = det.xǁTemporalDriftDetectorǁ_row_score__mutmut_33(frame)
    pd.testing.assert_series_equal(original, mutant, check_exact=True)
    print("signed division", label, "equal")
frame = pd.DataFrame({"t": np.repeat(3, 32), "x": np.repeat(0.03, 32)})
print(
    "boundary mean",
    repr(det._z(frame)["x"].mean()),
    "original max",
    det.xǁTemporalDriftDetectorǁ_row_score__mutmut_orig(frame).max(),
    "mutant max",
    det.xǁTemporalDriftDetectorǁ_row_score__mutmut_15(frame).max(),
)
