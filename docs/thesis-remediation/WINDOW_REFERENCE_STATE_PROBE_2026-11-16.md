# Window monitor initial reference state

`etl_benchmark.quality.window_drift.xǁWindowDriftMonitorǁ__init____mutmut_21`
sets the public `reference_end` field to an empty string instead of `None` in
source SHA-256
`7369796bac2ada0ee25c125b383752c8d40d7f683e287767dfb6b373108ea8d7`.
The generated-constructor probe confirms this observable type/value difference
in both local pandas environments; a hypothetical caller using `is None` to
decide whether to fit would make a different decision. Existing repository
consumers assert the reference end after fitting, but no repository consumer
was found relying on its pre-fit value. The supported significance of the
initial field is therefore unresolved: the case remains **inconclusive**,
not an equivalence proposal or a test added solely for field initialization.

The script and raw output are `window-reference-state.py.txt` and
`window-reference-state-output.txt` in
`evidence/continuation-2026-11-15/`; generated source is archived with the
nine-focused evidence. Checks used Python 3.11.17 and pandas 3.0.6/3.1.1 on
macOS arm64.
