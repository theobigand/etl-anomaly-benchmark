# Temporal decision label dtype investigation

`research.temporal_decision.x_decision_metrics__mutmut_2` changes label
conversion from `astype(int)` to `astype(None)` in source SHA-256
`f402ba92cdbd8a143608f9ce9d1ab98f68cad5b6c881318f504ab8c0380742d8`.
The direct generated-function probe found matching results for binary integer,
boolean, floating and integer-string labels. Nonbinary fractional labels,
float-formatted strings and labels containing NaN produced different metrics
or errors in NumPy 2.4.6 on both tested pandas environments.

The study's anomaly-label contract is binary, and the available evidence does
not establish that fractional or missing labels are valid inputs to this
metric function. The identity remains **inconclusive**, not an equivalence
proposal or a verified kill. The similar `run_frame` mutant is a separate
identity and has not been resolved by this experiment.

The executable probe and raw output are `temporal-label-dtype.py.txt` and
`temporal-label-dtype-output.txt` in
`evidence/continuation-2026-11-15/`; generated source is preserved with the
nine-focused evidence. No scientific assertion or archived result changed.

A separate real z-score study probe of
`research.temporal_decision.x_run_frame__mutmut_7` compared the two generated
functions with a bounded bootstrap. Binary integer, boolean, floating and
integer-string labels matched; fractional labels and NaN led to different
success/error outcomes, while float-formatted strings reversed which version
accepted the input. The script and output are `temporal-run-label-dtype.py.txt`
and `temporal-run-label-dtype-output.txt` in the same evidence directory. Since
the protocol's label domain is binary, the status of those nonbinary or
missing input cases is unresolved, and this second identity also remains
inconclusive.
