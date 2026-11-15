import hashlib
import platform
import warnings
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import numpy as np

from etl_benchmark.quality.autoencoder import ReconstructionModel

for path in (
    "src/etl_benchmark/quality/autoencoder.py",
    "mutants/src/etl_benchmark/quality/autoencoder.py",
):
    print(path, hashlib.sha256(Path(path).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "scikit-learn", "mutmut")},
)
for scale in (1e100, 1e200):
    for number in (0, 14):
        model = ReconstructionModel(0.1, 0, 2)
        method = (
            model.xǁReconstructionModelǁfit__mutmut_orig
            if number == 0
            else model.xǁReconstructionModelǁfit__mutmut_14
        )
        values = np.array([[1.0, -1.0], [2.0, 3.0], [-2.0, 1.0]]) * scale
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            try:
                method(values)
                outcome = "returned"
            except Exception as error:
                outcome = type(error).__name__
        counts = Counter((w.category.__name__, str(w.message)) for w in captured)
        print(scale, number, outcome, "warnings", dict(counts))
