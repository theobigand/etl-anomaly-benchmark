import ast
import hashlib
import pathlib
import platform

import pandas as pd

import research.pool_chrono as module

p = pathlib.Path("research/pool_chrono.py")
generated = pathlib.Path("mutants/research/pool_chrono.py")
tree = ast.parse(generated.read_text())
wanted = ["x_read_times__mutmut_18", "x_read_times__mutmut_21", "x_read_times__mutmut_25"]
ns = vars(module).copy()
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in wanted:
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(generated), "exec"), ns)
print(
    "platform",
    platform.platform(),
    "python",
    platform.python_version(),
    "pandas",
    pd.__version__,
    "source_sha256",
    hashlib.sha256(p.read_bytes()).hexdigest(),
)
frames = [
    pd.DataFrame({"Month": ["Jan", "Feb", "Dec", "Jan"]}),
    pd.DataFrame({"Month": ["JANUARY", "february", None, "header", "May"]}),
    pd.DataFrame({"Month": []}),
    pd.DataFrame({"Month": ["Mar", "Mar"]}, index=[20, 10]),
]
for i, frame in enumerate(frames):
    try:
        expected = module.read_times(frame, 468)
        x = ("ok", str(expected.dtype), expected.astype(str).tolist())
    except Exception as e:
        x = ("error", type(e).__name__, str(e))
    for name in wanted:
        try:
            out = ns[name](frame, 468)
            y = ("ok", str(out.dtype), out.astype(str).tolist())
        except Exception as e:
            y = ("error", type(e).__name__, str(e))
        print(i, name, "MATCH" if x == y else "DIFF", repr(y))
