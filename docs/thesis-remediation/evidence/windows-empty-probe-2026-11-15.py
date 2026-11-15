import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from etl_benchmark.quality import windows

paths = (
    "src/etl_benchmark/quality/windows.py",
    "mutants/src/etl_benchmark/quality/windows.py",
)
print("sources", {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths})
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {name: version(name) for name in ("numpy", "pandas", "mutmut")},
)
cases = {
    "permuted": (np.array([1.0, np.nan, 3.0]), np.array([2, 0, 1]), pd.Index(["a", "b", "c"])),
    "integer": (np.array([3, -1]), np.array([1, 0]), pd.Index([4, 4])),
    "empty": (np.array([]), np.array([], dtype=int), pd.Index([])),
    "mismatch": (np.array([1.0]), np.array([], dtype=int), pd.Index([0])),
}
for number in (7, 9):
    mutant = getattr(windows, f"x_scores_to_events__mutmut_{number}")
    for label, args in cases.items():
        results = []
        for f in (windows.scores_to_events, mutant):
            try:
                results.append(("value", f(*args)))
            except Exception as error:
                results.append((type(error).__name__, str(error)))
        assert results[0][0] == results[1][0]
        if results[0][0] == "value":
            pd.testing.assert_series_equal(results[0][1], results[1][1])
        else:
            assert results[0][1] == results[1][1]
        print(number, label, results[0][0], "equal")
