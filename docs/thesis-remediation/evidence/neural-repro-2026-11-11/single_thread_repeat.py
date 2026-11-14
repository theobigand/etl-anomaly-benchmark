import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

spec = importlib.util.spec_from_file_location("nr", sys.argv[1] + "/neural_repro.py")
nr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nr)

out = Path(sys.argv[2])
res = {}
for problem, method in (
    ("adbench:breastw", "ae1svm"),
    ("adbench:breastw", "lunar"),
    ("adbench:cardio", "deep_svdd"),
    ("adbench:cardio", "ae1svm"),
    ("adbench:cardio", "lunar"),
    ("adbench:breastw", "deep_svdd"),
):
    paths = []
    for i in range(4):
        p = out / f"{method}_{problem[-6:]}_{i}.npz"
        nr.run_worker(problem, method, 42, 1, False, p)
        paths.append(p)
    cmp = [nr.compare(paths[0], q) for q in paths[1:]]
    res[f"{problem}|{method}"] = {
        "bitwise_all": all(c["test_bitwise"] and c["fit_bitwise"] for c in cmp),
        "max_abs": max(c["test_max_abs"] for c in cmp),
        "flag_dis": sum(c["flag_disagreements"] for c in cmp),
    }
print(json.dumps(res, indent=1))
