import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from etl_benchmark.quality.ml import ECODDetector, TailProbabilityModel
from etl_benchmark.quality.rules import IQRDetector, ZScoreDetector

cases = {
    "ordinary": pd.DataFrame({"x": [0.0, 1.0, 100.0]}),
    "all_nan": pd.DataFrame({"x": [float("nan")]}),
    "infinity": pd.DataFrame({"x": [float("inf")]}),
    "missing_column": pd.DataFrame({"y": [1.0]}),
    "nonnumeric": pd.DataFrame({"x": ["a"]}),
    "empty": pd.DataFrame({"x": pd.Series([], dtype=float)}),
}
paths = (
    "src/etl_benchmark/quality/rules.py",
    "src/etl_benchmark/quality/base.py",
    "mutants/src/etl_benchmark/quality/rules.py",
    "src/etl_benchmark/quality/ml.py",
    "mutants/src/etl_benchmark/quality/ml.py",
)
print("sources", {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths})
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {p: version(p) for p in ("numpy", "pandas", "mutmut", "scikit-learn", "pyod")},
)
for cls, original, mutant in (
    (ZScoreDetector, "_zscores", "xǁZScoreDetectorǁ_zscores__mutmut_8"),
    (IQRDetector, "_exceedance", "xǁIQRDetectorǁ_exceedance__mutmut_9"),
):
    for label, frame in cases.items():
        detector = cls().fit(pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]}))
        outcomes = []
        for method in (original, mutant):
            try:
                outcomes.append(("value", getattr(detector, method)(frame)))
            except Exception as error:
                outcomes.append((type(error).__name__, str(error)))
        assert outcomes[0][0] == outcomes[1][0]
        if outcomes[0][0] == "value":
            pd.testing.assert_frame_equal(outcomes[0][1], outcomes[1][1])
        else:
            assert outcomes[0][1] == outcomes[1][1]
        print(cls.__name__, label, outcomes[0][0], "equal")

detector = ECODDetector().fit(pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]}))
for label, frame in cases.items():
    outcomes = []
    for method in ("_matrix", "xǁPyODDetectorǁ_matrix__mutmut_11"):
        try:
            outcomes.append(("value", getattr(detector, method)(frame)))
        except Exception as error:
            outcomes.append((type(error).__name__, str(error)))
    assert outcomes[0][0] == outcomes[1][0]
    if outcomes[0][0] == "value":
        np.testing.assert_array_equal(outcomes[0][1], outcomes[1][1])
    else:
        assert outcomes[0][1] == outcomes[1][1]
    print("PyODDetector", label, outcomes[0][0], "equal")

model = TailProbabilityModel(contamination=0.2, method="ecod").fit(
    np.array([[0.0, 1.0], [1.0, 1.0], [1.0, 3.0], [2.0, 5.0]])
)
for label, values in {
    "ties_and_outside": np.array([[1.0, 1.0], [-1.0, 6.0]]),
    "empty": np.empty((0, 2)),
    "nonfinite": np.array([[np.nan, np.inf]]),
}.items():
    expected = model.decision_function(values)
    actual = model.xǁTailProbabilityModelǁdecision_function__mutmut_26(values)
    np.testing.assert_array_equal(expected, actual)
    print("TailProbabilityModel", label, "equal")
