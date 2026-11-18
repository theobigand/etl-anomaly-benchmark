import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

import injection
import multi_schema as multi
import numpy as np
import pandas as pd
import typed_benchmark as benchmark

for p in ("research/typed_benchmark.py", "mutants/research/typed_benchmark.py"):
    print(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "scikit-learn", "mutmut")},
)
rng = np.random.default_rng(1)
a = rng.normal(50, 10, 4000)
carrier = pd.DataFrame(
    {
        "a": a,
        "b": 0.8 * a + rng.normal(0, 4, 4000),
        "c": rng.gamma(4, 5, 4000),
        "d": rng.normal(size=4000),
    }
)
frame = injection.inject(carrier, seed=3)
frame.index = pd.Index(np.arange(len(frame))[::-1] * 3 + 7)
for seed in (0, 11):
    test = benchmark.split(frame, seed)[2]
    assert test.index.equals(pd.RangeIndex(len(test)))
    original = benchmark.x_evaluate__mutmut_orig(
        frame, list(carrier.columns), seed, names=["zscore"]
    )
    for number in (53, 55):
        mutant = getattr(benchmark, f"x_evaluate__mutmut_{number}")
        result = mutant(frame, list(carrier.columns), seed, names=["zscore"])
        for table in ("recall", "precision"):
            pd.testing.assert_frame_equal(original[table], result[table])
        pd.testing.assert_series_equal(original["fpr"], result["fpr"])
        print(seed, number, "split RangeIndex and all output tables equal")

for p in ("research/multi_schema.py", "mutants/research/multi_schema.py"):
    print(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
# Restrict the detector registry to a real inexpensive detector while preserving
# the actual split, scoring path and deduplication comparator.
multi.DETECTOR_NAMES = ["zscore"]
for schema in ("transactions", "sensors"):
    spec = multi.SCHEMAS[schema]
    data = multi.make(spec, n_rows=300, seed=3)
    data.index = pd.Index(np.arange(len(data))[::-1] * 3 + 7)
    test = multi._split(data, spec, 3)[2]
    assert test.index.equals(pd.RangeIndex(len(test)))
    original = multi.x_evaluate__mutmut_orig(data, spec, 3)
    for number in (68, 70):
        mutant = getattr(multi, f"x_evaluate__mutmut_{number}")
        result = mutant(data, spec, 3)
        for table in ("recall", "precision"):
            pd.testing.assert_frame_equal(original[table], result[table])
        pd.testing.assert_series_equal(original["fpr"], result["fpr"])
        print(schema, number, "split RangeIndex and all output tables equal")
