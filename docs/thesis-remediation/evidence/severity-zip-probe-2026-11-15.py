import hashlib
import platform
import tempfile
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import run_severity as severity
from PIL import Image

for p in ("experiments/run_severity.py", "mutants/experiments/run_severity.py"):
    print(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "matplotlib", "pillow", "mutmut")},
)
curves = pd.DataFrame(
    [
        {"method": method, "anomaly_type": kind, "severity": s, "recall": r}
        for kind in severity.MAGNITUDE_TYPES
        for method, r in [("zscore", 0.25), ("iqr", 0.75)]
        for s in (0.5, 1.0, 2.0)
    ]
)
images = []
with tempfile.TemporaryDirectory() as temp:
    for number in (0, 24, 27, 28):
        function = (
            severity.x_render__mutmut_orig
            if number == 0
            else getattr(severity, f"x_render__mutmut_{number}")
        )
        path = Path(temp) / f"{number}.png"
        assert function(curves, path) == path
        with Image.open(path) as image:
            images.append(np.asarray(image).copy())
        print(number, "image shape", images[-1].shape)
for image in images[1:]:
    np.testing.assert_array_equal(images[0], image, strict=True)
print("all decoded images match")
