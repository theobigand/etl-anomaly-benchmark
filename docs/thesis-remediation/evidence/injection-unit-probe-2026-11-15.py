import hashlib
import platform
import warnings
from importlib.metadata import version
from pathlib import Path

import injection
import numpy as np
import pandas as pd

for p in ("research/injection.py", "mutants/research/injection.py"):
    print(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "mutmut")},
)
rng = np.random.default_rng(8)
frame = pd.DataFrame(rng.normal(size=(400, 4)), columns=list("abcd"))
for number in (48, 191):
    results = []
    for function in (
        injection.x_inject__mutmut_orig,
        getattr(injection, f"x_inject__mutmut_{number}"),
    ):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = function(frame, seed=3)
        results.append((result, [(w.category.__name__, str(w.message)) for w in captured]))
    pd.testing.assert_frame_equal(results[0][0], results[1][0])
    print(
        number, "frames equal", "original warnings", results[0][1], "mutant warnings", results[1][1]
    )

for label, ref in {
    "finite": frame,
    "constant": pd.DataFrame({"a": [1.0] * 4, "b": [0.0, 1.0, 2.0, 3.0]}),
    "one_column": pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0]}),
    "empty_columns": pd.DataFrame(index=range(4)),
}.items():
    outcomes = []
    for function in (injection.x__pair__mutmut_orig, injection.x__pair__mutmut_9):
        try:
            outcomes.append(("value", function(ref)))
        except Exception as error:
            outcomes.append((type(error).__name__, str(error)))
    assert outcomes[0][0] == outcomes[1][0]
    if outcomes[0][0] == "value":
        assert outcomes[0][1][:2] == outcomes[1][1][:2]
        np.testing.assert_equal(outcomes[0][1][2], outcomes[1][1][2])
    else:
        assert outcomes[0][1] == outcomes[1][1]
    print("pair", label, outcomes[0][0], "equal")

for label, value in {
    "bool": pd.Series([True, False] * 10, dtype=bool),
    "nullable_bool": pd.Series([True, False, None, True] * 5, dtype="boolean"),
    "int_binary": pd.Series([1, 0] * 10, dtype=int),
    "distinct": pd.Series(np.arange(20), dtype=int),
    "text": pd.Series([str(i) for i in range(20)], dtype="string"),
}.items():
    data = pd.DataFrame({"candidate": value})
    original = injection.x_continuous_columns__mutmut_orig(data)
    mutant = injection.x_continuous_columns__mutmut_5(data)
    assert original == mutant
    print("continuous_columns", label, original, "equal")
