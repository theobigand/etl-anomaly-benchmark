import hashlib
import platform
import warnings
from importlib.metadata import version
from pathlib import Path

import multi_schema
import pandas as pd
import typed_benchmark

for path in (
    "research/typed_benchmark.py",
    "mutants/research/typed_benchmark.py",
    "research/multi_schema.py",
    "mutants/research/multi_schema.py",
):
    print(path, hashlib.sha256(Path(path).read_bytes()).hexdigest())
print(
    "environment",
    platform.platform(),
    platform.python_version(),
    {n: version(n) for n in ("numpy", "pandas", "scikit-learn", "mutmut")},
)
cases = {
    "mixed": ([False, True, False, True], ["clean", "clean", "missing_value", "missing_value"]),
    "unflagged": ([False, False, False], ["clean", "clean", "missing_value"]),
    "absent": ([False, True], ["clean", "clean"]),
}
for module, numbers in ((typed_benchmark, (18, 26)), (multi_schema, (18, 25, 26))):
    for number in numbers:
        for label, (flags, types) in cases.items():
            outcomes = []
            for function in (
                module.x__per_type__mutmut_orig,
                getattr(module, f"x__per_type__mutmut_{number}"),
            ):
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter("always")
                    result = function(pd.Series(flags), pd.Series(types))
                outcomes.append((result, [(w.category.__name__, str(w.message)) for w in captured]))
            for i in (0, 1):
                pd.testing.assert_series_equal(
                    pd.Series(outcomes[0][0][i]), pd.Series(outcomes[1][0][i]), check_exact=True
                )
            print(
                module.__name__,
                number,
                label,
                "metrics equal",
                "original warnings",
                outcomes[0][1],
                "mutant warnings",
                outcomes[1][1],
            )
