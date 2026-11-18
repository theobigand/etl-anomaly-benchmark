# Severity figure axis pairing proposals

`experiments.run_severity.x_render__mutmut_24`, `_27` and `_28` change the
strict zip between axes and anomaly types to `strict=None`, omitted or
`strict=False`. They are proposed equivalents, not approved exclusions. With
the shipped three magnitude types and normal Matplotlib behavior, `subplots`
constructs one axis for each type using that same length, so the two zip
inputs have equal lengths. The output contract is a panel per magnitude type
with consistently labeled method curves. This argument is conditional on the
shipped configuration and unmodified plotting library; replacing `subplots`
with an implementation returning a mismatched number of axes is not covered.

The probe renders the same two-method, three-severity input with the original
and each generated mutant, decodes the PNGs and compares all image pixels.
They match in the recorded macOS arm64, Python 3.11.17 environment. This one
visual input and one dependency environment are examples, not exhaustive
proof. The executable `evidence/severity-zip-probe-2026-11-15.py` and `.txt`
output record package versions and comparison. The source SHA-256 is
`7bda7511594ba6313e9579805a0726fd04ce06382f10d2fcb6c06e4d90f0a3fd`;
the retained generated source `evidence/severity-generated-2026-11-15.py.gz`
has uncompressed SHA-256
`316dac2dba25659c4861d0399b50e0c5ba7aff804650703c4d2492690689f5c9`.
Reproduce with the matching generated source:

```sh
PYTHONPATH=mutants/experiments:mutants/src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/severity-zip-probe-2026-11-15.py
```

The historical raw unit was 320/329 (97.26%) at L4. Excluding these three
alone hypothetically gives 320/326 (98.16%), which crosses the historical 98%
threshold. This is not a fresh score, an authorized exclusion, or independent
review; the earlier packet's two separate proposals are not included.
