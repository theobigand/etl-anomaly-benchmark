import hashlib
import platform
import tempfile
from importlib.metadata import version
from pathlib import Path

import multi_schema as multi
import pandas as pd

for path in ("research/multi_schema.py", "mutants/research/multi_schema.py"):
    print(path, hashlib.sha256(Path(path).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "mutmut")},
)
# The expensive data generator and detectors are replaced with stable results;
# the command's seed iteration and the real artifact writers remain in use.
multi.SCHEMAS = {"transactions": multi.SCHEMAS["transactions"]}
multi.make = lambda spec, rows, seed: seed
multi.evaluate = lambda value, spec, seed, deep: {
    "recall": pd.DataFrame([[float(seed)]], index=["zscore"], columns=["missing_value"]),
    "precision": pd.DataFrame([[float(seed)]], index=["zscore"], columns=["missing_value"]),
    "fpr": pd.Series({"zscore": float(seed)}),
}
outputs = []
with tempfile.TemporaryDirectory() as d:
    for number in (0, 70, 73, 74):
        output = Path(d) / str(number)
        function = (
            multi.x_main__mutmut_orig if number == 0 else getattr(multi, f"x_main__mutmut_{number}")
        )
        assert function(["--output", str(output), "--rows", "300", "--methods", "deep"]) == 0
        saved = {p.name: p.read_text() for p in output.iterdir()}
        outputs.append(saved)
        print(number, "file count", len(saved), "files", sorted(saved))
assert all(item == outputs[0] for item in outputs[1:])
print("all generated files match")

# Compare the no-option classical route while keeping the actual argument parser,
# result aggregation and artifact writers. Research computations are stand-ins.
multi.published_customer = lambda: pd.DataFrame(
    [[0.5]], index=["zscore"], columns=["missing_value"]
)
multi.hypotheses = lambda matrices: {"probe": len(matrices)}
outputs = []
with tempfile.TemporaryDirectory() as directory:
    for number in (0, 23, 27, 35, 36):
        output = Path(directory) / str(number)
        function = (
            multi.x_main__mutmut_orig if number == 0 else getattr(multi, f"x_main__mutmut_{number}")
        )
        assert function(["--output", str(output), "--rows", "300"]) == 0
        saved = {p.name: p.read_text() for p in output.iterdir()}
        outputs.append(saved)
        print("default", number, "file count", len(saved))
assert all(item == outputs[0] for item in outputs[1:])
print("all default-route files match")
