import hashlib
import os
import platform
import tempfile
from importlib.metadata import version
from pathlib import Path

import great_expectations as gx
import pandas as pd

from etl_benchmark.quality.gx import GreatExpectationsDetector

for path in ("src/etl_benchmark/quality/gx.py", "mutants/src/etl_benchmark/quality/gx.py"):
    print(path, hashlib.sha256(Path(path).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "great-expectations", "mutmut")},
)
with tempfile.TemporaryDirectory() as temp:
    gx.get_context(mode="file", project_root_dir=temp)
    os.chdir(temp)
    root = Path(temp)

    def snapshot():
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }

    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    detector = GreatExpectationsDetector().fit(frame)
    for name in (
        "xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_orig",
        "xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_9",
    ):
        before = snapshot()
        result = getattr(detector, name)(frame)
        after = snapshot()
        changed = [k for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)]
        print(name, "row failures", result.tolist(), "changed files", changed)
