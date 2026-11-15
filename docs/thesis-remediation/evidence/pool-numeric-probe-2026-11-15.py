import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import pool_preprocessing as pool

for path in ("research/pool_preprocessing.py", "mutants/research/pool_preprocessing.py"):
    print(path, hashlib.sha256(Path(path).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {name: version(name) for name in ("numpy", "pandas", "scikit-learn", "mutmut")},
)
cases = {
    "numeric_and_nan": (pd.DataFrame({"x": [1.0, np.nan, 3.0]}), ["x"]),
    "numeric_text": (pd.DataFrame({"x": ["1", "2.5"]}), ["x"]),
    "invalid_text": (pd.DataFrame({"x": ["x", "1"]}), ["x"]),
    "infinity": (pd.DataFrame({"x": [1.0, np.inf]}), ["x"]),
    "empty_columns": (pd.DataFrame({"x": [1.0, 2.0]}), []),
    "missing_column": (pd.DataFrame({"x": [1.0]}), ["absent"]),
}
for label, args in cases.items():
    outcomes = []
    for function in (pool.x__numeric__mutmut_orig, pool.x__numeric__mutmut_9):
        try:
            outcomes.append(("value", function(*args)))
        except Exception as error:
            outcomes.append((type(error).__name__, str(error)))
    assert outcomes[0][0] == outcomes[1][0]
    if outcomes[0][0] == "value":
        np.testing.assert_array_equal(outcomes[0][1], outcomes[1][1], strict=True)
    else:
        assert outcomes[0][1] == outcomes[1][1]
    print(label, outcomes[0][0], "equal")
