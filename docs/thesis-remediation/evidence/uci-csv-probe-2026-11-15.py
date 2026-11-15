import hashlib
import platform
import tempfile
import warnings
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import uci_loader as loader

for p in ("research/uci_loader.py", "mutants/research/uci_loader.py"):
    print(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "mutmut")},
)
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "mixed.csv"
    with path.open("w") as stream:
        stream.write(",".join(["x"] + [f"v{i}" for i in range(19)]) + "\n")
        stream.writelines(
            (str(i) if i < 120000 else "bad") + "," + ",".join(["1"] * 19) + "\n"
            for i in range(140000)
        )
    print("fixture sha256", hashlib.sha256(path.read_bytes()).hexdigest())
    for number in (0, 5, 6):
        function = (
            loader.x_read_table__mutmut_orig
            if number == 0
            else getattr(loader, f"x_read_table__mutmut_{number}")
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            values = function(path)["x"]
        types = Counter(type(value).__name__ for value in values)
        print(
            number,
            "dtype",
            str(values.dtype),
            "types",
            dict(types),
            "warnings",
            sorted({w.category.__name__ for w in captured}),
        )
