# Injection carrier numeric dtype probe

`research.injection.x_prepare__mutmut_6` changes the selected carrier frame
conversion from `astype(float)` to `astype(None)`. Source SHA-256:
`cdfc81d98e3470ccdf5f7930d7e987b1bdad3545e060552f3a3bb1d170d8cb39`.
The contract selects continuous numeric columns, converts them to floating
values, drops incomplete and duplicate rows, and enforces the minimum row
count and cap. Both conversions use float64 for the tested pandas numeric
dtypes.

Direct generated-function comparisons covered integer, float32, float64,
nullable integer and nullable float columns; too-small, exactly minimum and
larger carriers; missing rows; and two caps. Result frames, dtypes, reports,
exceptions and captured warnings matched. The expanded probe is
`evidence/continuation-2026-11-15/injection-prepare-dtype-expanded.py.txt`,
with raw output in the corresponding `*-output.txt`. The first smaller probe
only reached the row-count rejection and is retained separately. The generated
source SHA-256 is `0a049b613cdff4161eabffebcb6f7c7a0dfc67379516fec3e6bac09781988cdd`
and is preserved in `evidence/injection-generated-2026-11-15.py.gz`.

The checks used macOS arm64, Python 3.11.17, NumPy 2.4.6, and pandas 3.0.6
and 3.1.1. Confidence is medium for these tested dtypes and environments;
other numeric extension dtypes, supported versions and Linux remain untested.
This is a conditional proposal, not an owner decision or full unit score.

```sh
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/injection-prepare-dtype-expanded.py.txt
```

Additional lower-bound dependency results are in [the compatibility addendum](MINIMUM_DEPENDENCY_PROBES_2026-11-16.md).
