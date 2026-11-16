# Behavioral regressions awaiting native verdicts

Six mutants have meaningful counterexamples and integrated tests. Each test
passed on the original and failed on the corresponding generated mutant; all
still require a native run on the frozen current test tree before counting as
kills. Direct RED logs are retained in
`evidence/continuation-2026-11-15/`.

- `etl_benchmark.quality.ml.xǁPyODDetectorǁfit__mutmut_4` and
  `etl_benchmark.quality.ml.xǁPyODDetectorǁ_matrix__mutmut_8`, source
  `4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`,
  omit float conversion. The same float32 values represented as float64 should
  yield consistent ECOD scores and flags. Real detector probes observed five
  differing training flags and one differing scoring flag on the mutants in
  both local pandas builds; the original matched. Regressions are
  `tests/test_ml.py::test_ecod_training_is_consistent_for_the_same_float_values`
  and `tests/test_ml.py::test_ecod_scoring_is_consistent_for_the_same_float_values`.
  Probe outputs include PCA numerical differences, which are recorded as
  observations and do not replace the established PCA interpretation.
- `experiments.run_severity.x_render__mutmut_46` and `_53`, source
  `7bda7511594ba6313e9579805a0726fd04ce06382f10d2fcb6c06e4d90f0a3fd`,
  remove explicit line coloring. Under a valid single-color Matplotlib theme,
  they render distinct method curves in the same color. The real rendering
  regression is
  `tests/test_script_outputs_synthetic.py::test_severity_methods_remain_visually_distinct_under_a_single_color_theme`.
- The two MPS device-transfer mutants and their public wrapper regression are
  detailed in [TORCH_DEVICE_MUTANTS_2026-11-15.md](TORCH_DEVICE_MUTANTS_2026-11-15.md).

An earlier focused ECOD native attempt started before the severity and MPS
tests were added. Its test tree changed during execution, so its verdicts must
not be treated as final bound evidence. Run all six together after freezing the
test tree, retain the native metadata and logs, and update the individual
triage records only after checking the native outcomes.

Update: the two severity mutants and the two MPS mutants were subsequently
killed in isolated native engine runs; see their linked reports. The two ECOD
mutants still require a native run with the current test tree. Two separate
command-help differences are awaiting regression tests as described in
[COMMAND_HELP_PROBE_2026-11-16.md](COMMAND_HELP_PROBE_2026-11-16.md).

Later continuation: the command-help tests, a deep calibration test, and a
failed-fit window guard test now have direct RED/GREEN evidence. The ECOD and
three scientific-command/calibration native attempt failed before mutation
execution because the Metal compiler service was unavailable; the window test
was added afterward. All six still need native verdicts. See
[SCIENTIFIC_REGRESSIONS_2026-11-16.md](SCIENTIFIC_REGRESSIONS_2026-11-16.md).
