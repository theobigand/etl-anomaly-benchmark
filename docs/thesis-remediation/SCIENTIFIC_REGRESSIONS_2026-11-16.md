# Scientific command, calibration, and window regressions

Four generated-mutant counterexamples now have regression tests. Each direct RED run loaded the preserved generated function and failed for the expected behavior; each test passed on the original implementation. The native verdict is pending, so none is counted as a native kill.

- `research.multi_schema.x_evaluate__mutmut_21`: the neural evaluation passes training anomaly prevalence to each detector. The mutant passes `None`. RED: `multi-prevalence-red.log.gz`.
- `research.multi_schema.x_main__mutmut_2`: help describes the study and links its protocol. RED: `multi-help-red.log.gz`.
- `research.temporal_decision.x_main__mutmut_2`: help describes the study and links its protocol. RED: `temporal-help-red.log.gz`.
- `etl_benchmark.quality.window_drift.xǁWindowDriftMonitorǁevaluate__mutmut_1`: after a failed numerical fit, evaluation reports that the monitor is not fitted. RED: `window-guard-red.log.gz`; the finite-input counterexample and environment are detailed in `WINDOW_GUARD_PROBE_2026-11-16.md`.

The RED harnesses and logs are in `evidence/continuation-2026-11-15/`. On the original, `~/.cache/etl-mutation-venv/bin/python -m pytest -q tests/test_window_drift_contracts.py research/tests/test_multi_schema_contracts.py research/tests/test_multi_schema_command.py research/tests/test_temporal_decision.py` passed 61 tests (see `scientific-regressions-green.log.gz`); the multi-schema test was subsequently formatted without changing behavior.

The generated multi-schema and temporal modules used for RED also match the
copies in `evidence/diagnostic-43744898804.tar.gz`: their SHA-256 digests are
`8b48b7c67a6e97e0bfa55683104c6f7c28ff77fcc949ba1e6281003424dbdf8e`
and `0264ae49d442c9cb7d3331d63ae14e36d1041078e8468b686a9175c8fbc18c38`,
respectively. The harness takes the function name, exact generated mutant
name, and pytest node as arguments; its log records each failed node. The
source identities are in the separate command-help and calibration records.
The first three RED checks used the Conda environment recorded in
`scientific-direct-context.json`. The window RED and the grouped GREEN used
the separate environment in `scientific-mutation-env.json`.

A native single-worker run of the first three mutants plus two ECOD mutants failed its clean baseline before executing those mutants. The failure was an unavailable Apple Metal compiler service in the DIF MPS detector test, not a mutant verdict. See `scientific-native-debug-run.log.gz` and `scientific-native-context.json`. The test tree later changed to add the window regression, so that context is not a digest of the final test tree. The earlier ECOD clean baseline failed with the same Metal-service message in the VAE MPS detector (`ecod-native-debug-run.log.gz`). Neither failure justifies skipping the MPS contract or claiming a native kill. A Linux native run with the official CPU environment is a suitable next attempt; MPS-specific native evidence must retain its own macOS environment and limitations.

On this machine, `docker info --format '{{.ServerVersion}} {{.OSType}} {{.Architecture}}'`
exited 1 because the Docker daemon was unavailable, so a local Linux container
was not established. Hosted diagnostics need a committed exact head and must
retain the full shard result and its limitations.

From the repository root, after restoring the archived generated modules in
`mutants/research` without overwriting an existing cache, the three direct RED
checks used these commands (each is expected to exit 1 on its mutant):

```sh
~/miniconda3/envs/etl-benchmark/bin/python docs/thesis-remediation/evidence/continuation-2026-11-15/scientific-regression-red.py.txt multi_schema evaluate x_evaluate__mutmut_21 research/tests/test_multi_schema_contracts.py::test_the_neural_mode_builds_only_the_neural_detectors
~/miniconda3/envs/etl-benchmark/bin/python docs/thesis-remediation/evidence/continuation-2026-11-15/scientific-regression-red.py.txt multi_schema main x_main__mutmut_2 research/tests/test_multi_schema_command.py::test_the_method_choice_default_and_help_are_documented
~/miniconda3/envs/etl-benchmark/bin/python docs/thesis-remediation/evidence/continuation-2026-11-15/scientific-regression-red.py.txt temporal_decision main x_main__mutmut_2 research/tests/test_temporal_decision.py::test_help_describes_the_study_and_protocol
~/.cache/etl-mutation-venv/bin/python docs/thesis-remediation/evidence/continuation-2026-11-15/window-guard-red.py.txt
```

The generated modules must match the hashes above. The fourth command requires
the extracted window source described in `WINDOW_GUARD_PROBE_2026-11-16.md`.
These commands execute individual generated functions; they are not substitutes
for native mutation-engine verdicts.
