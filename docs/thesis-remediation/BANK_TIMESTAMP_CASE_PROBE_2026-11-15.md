# Bank timestamp assembly key case

`research.temporal_decision.x_bank_marketing__mutmut_48`, `_50` and `_54`
respectively change the pandas timestamp assembly keys `year`, `month`, and
`day` to uppercase. Source SHA-256:
`f402ba92cdbd8a143608f9ce9d1ab98f68cad5b6c881318f504ab8c0380742d8`.
The contract is to construct UTC timestamps in file order, retaining month
rollovers and within-month order, while preserving labels and features. The
installed pandas implementations normalize these keys to lower case before
mapping timestamp components.

The executable direct generated-mutant probe compares features, labels,
timestamps, dtypes, and exceptions for year rollover, repeated months, empty
input, and an invalid month. All three matched the original in pandas 3.0.6 and
3.1.1 on macOS arm64 with Python 3.11.17. The probe and its raw outputs are in
`evidence/pending-probes-2026-11-15/bank-case.py.txt` and
`bank-case-output-rerun.txt`; the first attempted command omitted the repository
root from `PYTHONPATH` and its failure is retained in `bank-case-output.txt`.
The generated source digest is recorded in the successful output and archived
with the nine-mutant focused evidence.

These are conditional equivalence proposals only, not approvals. The declared
pandas range is wider than the tested versions, and Linux and other supported
builds were not tested. No fresh complete campaign has been performed.
Reproduce with the generated mutant inventory present:

```sh
PYTHONPATH=.:research:src ~/miniconda3/envs/etl-benchmark/bin/python docs/thesis-remediation/evidence/pending-probes-2026-11-15/bank-case.py.txt
PYTHONPATH=.:research:src ~/.cache/etl-mutation-venv/bin/python docs/thesis-remediation/evidence/pending-probes-2026-11-15/bank-case.py.txt
```

Evidence confidence: medium for the tested environments; supported-version
and platform coverage remains incomplete. The owner decision remains separate.
