import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

import multi_schema as multi
import numpy as np

for path in ("research/multi_schema.py", "mutants/research/multi_schema.py"):
    print(path, hashlib.sha256(Path(path).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "mutmut")},
)
for n in (0, 1, 10, 100, -1):
    for number in (31, 34, 35):
        outcomes = []
        for function in (multi.x__dates__mutmut_orig, getattr(multi, f"x__dates__mutmut_{number}")):
            try:
                outcomes.append(("value", function(n, np.random.default_rng(42), "%Y-%m-%d %H:%M")))
            except Exception as error:
                outcomes.append((type(error).__name__, str(error)))
        assert outcomes[0] == outcomes[1]
        print(n, number, outcomes[0][0], "equal")
