import ast
import hashlib
import platform
from pathlib import Path

import numpy as np
import pandas as pd

import research.pool_chrono as m

p = Path("research/pool_chrono.py")
generated = Path("mutants/research/pool_chrono.py")
tree = ast.parse(generated.read_text())
wanted = ["x_eligible__mutmut_7", "x_eligible__mutmut_9", "x_eligible__mutmut_10"]
ns = vars(m).copy()
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in wanted:
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(generated), "exec"), ns)
print(
    "python",
    platform.python_version(),
    "pandas",
    pd.__version__,
    "source_sha256",
    hashlib.sha256(p.read_bytes()).hexdigest(),
)
times = pd.Series(["2024-01-01T00:00:00+00:00", "2024-01-01T01:00:00+01:00"] * 20)
y = np.zeros(len(times), dtype=int)
for name, fn in [("original", m.eligible), *((name, ns[name]) for name in wanted)]:
    try:
        print(name, "result", fn(y, times))
    except Exception as e:
        print(name, "error", type(e).__name__, str(e).splitlines()[0])
