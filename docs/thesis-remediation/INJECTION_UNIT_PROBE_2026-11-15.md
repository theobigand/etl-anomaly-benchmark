# Injection time-unit investigation

`research.injection.x_inject__mutmut_48` and
`research.injection.x_inject__mutmut_191` change an hour unit from `h` to `H`
at different timestamp-generation sites. They remain inconclusive; neither is
proposed equivalent or counted as killed.

With the same 400-row seeded numeric carrier, the generated original and each
mutant produced equal complete output frames in both local environments:
macOS arm64, Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6 or 3.1.1. In both,
the original emitted no warning and each mutant emitted a `Pandas4Warning`
about the deprecated uppercase hour unit. Thus outputs matching in those
examples do not establish behavioral equivalence. Whether that warning is a
meaningful contract violation for this workflow, and behavior in other
supported pandas versions, still need investigation. No artificial warning
assertion was added solely to kill these mutants.

The source SHA-256 is
`cdfc81d98e3470ccdf5f7930d7e987b1bdad3545e060552f3a3bb1d170d8cb39`;
the generated source SHA-256 is
`0a049b613cdff4161eabffebcb6f7c7a0dfc67379516fec3e6bac09781988cdd`,
retained as `evidence/injection-generated-2026-11-15.py.gz`. The probe and
results are `evidence/injection-unit-probe-2026-11-15.py` and the matching
`-conda.txt` and `-mutation.txt` files. With that generated module available,
run the probe with `PYTHONPATH=mutants/research:src` and each interpreter
specified in the output files' environment records.

```sh
PYTHONPATH=mutants/research:src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/injection-unit-probe-2026-11-15.py
PYTHONPATH=mutants/research:src ~/miniconda3/envs/etl-benchmark/bin/python \
  docs/thesis-remediation/evidence/injection-unit-probe-2026-11-15.py
```
