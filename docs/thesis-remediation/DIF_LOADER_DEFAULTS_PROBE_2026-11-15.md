# DIF data-loader default probes

The following historical survivors in `src/etl_benchmark/quality/_torch_models.py`
(SHA-256 `77a1b57ff69e580cad700bb4ee41f069e3ac0c8489bdd714651c753c4bbdd09d`)
change only the `DataLoader` arguments used for DIF representation batches:

- `etl_benchmark.quality._torch_models.xǁFitScalerDIFǁ_deep_representation__mutmut_5`
  changes `shuffle=False` to `shuffle=None`.
- `etl_benchmark.quality._torch_models.xǁFitScalerDIFǁ_deep_representation__mutmut_8`
  omits `drop_last=False`.
- `etl_benchmark.quality._torch_models.xǁFitScalerDIFǁ_deep_representation__mutmut_9`
  omits `shuffle=False`.

The contract is deterministic fit-row and scoring representations with no
rows lost, including a short last batch. In both tested PyTorch builds the
`DataLoader` signature defaults to `drop_last=False` and `shuffle=None`, with
`None` and `False` both selecting sequential sampling in the tested cases.
The direct generated-method probe tests empty, singleton, complete and partial
batches, different batch sizes, and a second scoring call using the previously
fit scaler. Values and error outcomes matched the original for every case.

The tests ran on macOS arm64, Python 3.11.17, torch 2.14.1 and 2.15.0. Probe
scripts, outputs and the generated mutant source are in
`evidence/pending-probes-2026-11-15/`: `dataloader-defaults.py.txt`,
`dataloader-defaults-output.txt`, `dif-defaults-mutants.py.txt`,
`dif-defaults-mutants-output.txt.gz`, and `torch-models-generated.py.gz`. The
uncompressed generated source SHA-256 is
`ace89b287a051542a58a9e06999e8ec0a9d871cb4a0487ea180e75de132cdda7`.

These are conditional owner proposals, not approvals. The probe uses the CPU
and does not establish behavior for every supported PyTorch build, device or
third-party monkeypatch. Linux and a full current unit campaign have not been
run. Reproduce the direct generated-method probe from the repository root:

```sh
PYTHONPATH=mutants/src:src ~/miniconda3/envs/etl-benchmark/bin/python -P docs/thesis-remediation/evidence/pending-probes-2026-11-15/dif-defaults-mutants.py.txt
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/pending-probes-2026-11-15/dif-defaults-mutants.py.txt
```

Evidence confidence: medium for the tested CPU environments; dependency and
platform coverage is incomplete. The owner decision remains separate.
