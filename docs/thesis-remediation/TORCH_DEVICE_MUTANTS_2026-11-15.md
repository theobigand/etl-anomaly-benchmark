# Torch device-transfer counterexamples

`etl_benchmark.quality._torch_models.xǁMeanVAEǁevaluating_forward__mutmut_3`
and `etl_benchmark.quality._torch_models.xǁFitScalerDIFǁ_deep_representation__mutmut_14`
replace a transfer to `self.device` with `.to(None)` in
`src/etl_benchmark/quality/_torch_models.py`, SHA-256
`77a1b57ff69e580cad700bb4ee41f069e3ac0c8489bdd714651c753c4bbdd09d`.
CPU-only comparison can mask the difference. Public `TorchDetector` arguments
allow caller device choices because `estimator_kwargs` are merged after the
class defaults.

On macOS arm64 with Python 3.11.17 and torch 2.15.0, the local Apple MPS device
was available. Real `DIFDetector(device="mps", ...)` and
`VAEDetector(device="mps", ...)` fit and scored finite results on the original.
Each corresponding mutant failed with `RuntimeError` because a CPU input was
passed to an MPS model. A separate generated-method probe confirmed the DIF
transfer difference. Scripts and raw outputs are `dif-mps-wrapper.py.txt`,
`vae-mps-wrapper.py.txt`, `torch-mps-direct.py.txt` and their output files in
`evidence/continuation-2026-11-15/`.

The parametrized public regression
`tests/test_deep_detectors.py::test_deep_detector_scores_on_an_explicit_mps_device`
failed on each matching mutant (RED, exit 1, expected device mismatch) and
passed both cases on the original (GREEN). It skips when MPS is unavailable,
including the Linux CPU runner. The native mutmut engine, run with in-memory diagnostic logging enabled after
the earlier clean-baseline failures, completed successfully and recorded both
mutants killed. The command, before/after test digests, metadata, and logs are in
`evidence/continuation-2026-11-15/mps-native-debug.json`. The earlier baseline
failures and their unresolved cause remain recorded; CUDA remains untested. The generated source is
preserved in `evidence/pending-probes-2026-11-15/torch-models-generated.py.gz`.

The test's former `pytest.skip` for unavailable MPS violated the repository's
skip policy. The fast-selection suite reported that failure (4,023 passed,
one failed, 53 deselected); the direct policy RED is in
`evidence/continuation-2026-11-15/mps-skip-policy-red.log.gz`. The regression
now parametrizes CPU everywhere and MPS only when available, with separate
pytest case IDs. The policy test and all four device cases passed on the
current MPS-capable machine; see `mps-policy-green.log.gz`. Linux CPU runs do
not exercise the MPS case. The earlier native kills remain historical evidence
for their recorded test-tree digest; the changed test tree needs remeasurement.
