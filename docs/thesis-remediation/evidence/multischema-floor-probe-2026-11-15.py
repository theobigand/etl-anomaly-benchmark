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
    {name: version(name) for name in ("numpy", "pandas", "mutmut")},
)
for label, function in (
    ("original", multi.x__transactions__mutmut_orig),
    ("79", multi.x__transactions__mutmut_79),
    ("101", multi.x__transactions__mutmut_101),
):
    balance = function(3000, np.random.default_rng(0), None)["balance_after"]
    print(
        label,
        "minimum",
        float(balance.min()),
        "negative",
        int((balance < 0).sum()),
        "zero",
        int((balance == 0).sum()),
    )
