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
