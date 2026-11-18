# UCI CSV mixed-type chunk boundary

`research.uci_loader.x_read_table__mutmut_5` and `_6` omit
`low_memory=False` or change it to True. The loader must provide consistent
column values for downstream cleaning and encoding. A 140,000-row CSV with
20 columns and a late block of nonnumeric text demonstrates the effect of
chunked inference: the original returns a homogeneous string column, while
both mutants return a mixture of integer and string values and emit
`DtypeWarning`. The example used a sufficiently large text block to prevent
the loader's separate 99% numeric-conversion rule from intentionally coercing
it. This is a behavioral difference, not an equivalence claim.

The generated fixture's SHA-256 is
`eb188ebb1fe6bfdb3119bdf39dc26570b113c02ec5c645cd2b1edd0503e753bf`.
Both local environments reproduced the difference: macOS arm64, Python
3.11.17, NumPy 2.4.6, mutmut 3.8.0 and pandas 3.0.6 or 3.1.1. Source and
generated-source hashes and type counts are retained in the matching
`evidence/uci-csv-probe-2026-11-15-{conda,mutation}.txt` outputs; the
uncompressed generated source is preserved at
`evidence/uci-loader-generated-2026-11-15.py.gz`.

```sh
PYTHONPATH=mutants/research:src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/uci-csv-probe-2026-11-15.py
PYTHONPATH=mutants/research:src ~/miniconda3/envs/etl-benchmark/bin/python \
  docs/thesis-remediation/evidence/uci-csv-probe-2026-11-15.py
```

The fixture is generated in a disposable temporary directory. A public-loader regression now checks the entire returned column consists of
strings and preserves the first and last values. It failed on each mutant
(RED, exit 1) and passed on the original in both pandas environments; the
complete affected loader test file passed in the mutation environment
(GREEN/regression, exit 0; 12 tests). The fixture exercises a real parser
chunk boundary; its exact size may need revisiting if pandas changes its
chunking strategy. The focused native run exited 0 and recorded both mutants killed (exit code 1).
The command, context, log and metadata are in
`evidence/uci-csv-focused-2026-11-15.json` and associated files. The run used
the case-insensitive local filesystem with tests uncommitted on `11b7994`;
it is not a full unit measurement and does not change a campaign score.

RED uses the temporal preload pattern, importing `research.uci_loader` as
`uci_loader`, setting `MUTANT_UNDER_TEST` to the exact identity above and
running node `research/tests/test_uci_loader.py::test_large_mixed_csv_keeps_a_consistent_string_column`.
GREEN/regression: `~/.cache/etl-mutation-venv/bin/python -m pytest
research/tests/test_uci_loader.py --disable-warnings -q`; canonical boundary
check: `~/miniconda3/envs/etl-benchmark/bin/python -m pytest
research/tests/test_uci_loader.py::test_large_mixed_csv_keeps_a_consistent_string_column --disable-warnings -q`.
