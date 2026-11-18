# Severity command pivot display

`experiments.run_severity.x_main__mutmut_134` and `_137` replace or omit
`values="recall"` in the printed pivot. Source SHA-256:
`7bda7511594ba6313e9579805a0726fd04ce06382f10d2fcb6c06e4d90f0a3fd`.
A direct generated-command probe supplied the documented four-column `run`
result and executed the real render and output path in temporary directories.
Both mutants printed the same numeric recall values but included an extra
`recall` column level in the console table. The original did not. The observed
CSV shape and figure creation matched in the tested cases.

This is a user-visible formatting difference, but the available evidence does
not establish that the extra header harms interpretation or violates a
specified console-format contract. Both cases remain **inconclusive** rather
than being counted as equivalent or given a formatting assertion solely to
kill them. The script and raw outputs are `severity-pivot.py.txt` and
`severity-pivot-output.txt` in `evidence/continuation-2026-11-15/`; tests used
Python 3.11.17 and pandas 3.0.6/3.1.1 on macOS arm64. The expensive study
computation was replaced with a representative documented result frame; the
pivot, figure render and record path ran normally. Generated source is archived
with the severity-focused evidence.
