import hashlib
import platform
import warnings
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

folds = {"train": list(range(8)), "validation": [8, 9], "test": [10, 11]}
frame = pd.DataFrame({"x": np.arange(12, dtype=float), "cat": ["a", "b"] * 6})
within = frame.copy()
within.iloc[1] = within.iloc[0]
across = frame.copy()
across.iloc[10] = across.iloc[0]
bad_folds = {"train": list(range(8)), "validation": [8, 9], "test": [10, 10]}
categorical_only = pd.DataFrame({"x": [f"category-{n}" for n in range(12)]})
for number in (16, 18, 93):
    mutant = getattr(pool, f"x_prepare_frozen__mutmut_{number}")
    for label, input_frame, parts in (
        ("valid", frame, folds),
        ("duplicate_within", within, folds),
        ("duplicate_across", across, folds),
        ("invalid_partitions", frame, bad_folds),
        ("categorical_only", categorical_only, folds),
    ):
        outcomes = []
        for function in (pool.x_prepare_frozen__mutmut_orig, mutant):
            try:
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter("always")
                    value = function(input_frame, parts)
                outcomes.append(
                    ("value", value, [(w.category.__name__, str(w.message)) for w in captured])
                )
            except Exception as error:
                outcomes.append((type(error).__name__, str(error)))
        assert outcomes[0][0] == outcomes[1][0]
        if outcomes[0][0] == "value":
            assert outcomes[0][1]["fit"] == outcomes[1][1]["fit"]
            assert outcomes[0][2] == outcomes[1][2]
            for part in folds:
                pd.testing.assert_frame_equal(outcomes[0][1][part], outcomes[1][1][part])
        else:
            assert outcomes[0][1] == outcomes[1][1]
        print(number, label, outcomes[0][0], "equal")
