import hashlib
import logging
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from etl_benchmark.quality.gx import GreatExpectationsDetector

logging.getLogger("great_expectations").setLevel(logging.ERROR)
for p in ("src/etl_benchmark/quality/gx.py", "mutants/src/etl_benchmark/quality/gx.py"):
    print(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "great-expectations", "mutmut")},
)
training = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0], "label": [1.0, 1.0, 1.0, 1.0]})
frames = {
    "normal": pd.DataFrame({"x": [1.0, 2.0], "label": [1.0, 1.0]}, index=["b", "a"]),
    "missing_outlier": pd.DataFrame({"x": [np.nan, 100.0], "label": [1.0, 1.0]}, index=["x", "x"]),
}
for number in (17, 18, 19, 20, 21, 22):
    for label, frame in frames.items():
        detector = GreatExpectationsDetector().fit(training)
        original = detector.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_orig(frame)
        mutant = getattr(
            detector, f"xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_{number}"
        )(frame)
        pd.testing.assert_series_equal(original, mutant, check_exact=True)
        print(number, label, "equal")
