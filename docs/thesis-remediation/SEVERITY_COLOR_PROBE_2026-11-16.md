# Severity plot method-color regression

`experiments.run_severity.x_render__mutmut_46` and `_53` set the line color
to `None` or omit it. Source SHA-256:
`7bda7511594ba6313e9579805a0726fd04ce06382f10d2fcb6c06e4d90f0a3fd`.
A severity figure must distinguish different detector methods. Under a valid
single-color Matplotlib theme, the original retains distinct method colors,
whereas each mutant renders both methods in black. The regression
`tests/test_script_outputs_synthetic.py::test_severity_methods_remain_visually_distinct_under_a_single_color_theme`
executes real rendering and checks distinguishability across all panels.

Each generated mutant failed the regression (RED, exit 1), the original passed
(GREEN), and an isolated native mutmut run exited 0 and recorded both killed
(exit code 1). The command, source and test-tree digests, generated source,
metadata and compressed native log are in
`evidence/continuation-2026-11-15/severity-native-isolated.json` and associated
files. The run used a case-insensitive macOS filesystem and uncommitted tests;
it is not a full unit measurement or an addition to the historical campaign.
