# Window event UTC spelling

`etl_benchmark.quality.window_drift.x_event_metrics__mutmut_29` changes
`cutoff.tz_convert("UTC")` to `cutoff.tz_convert("utc")` in
`src/etl_benchmark/quality/window_drift.py` (SHA-256
`7369796bac2ada0ee25c125b383752c8d40d7f683e287767dfb6b373108ea8d7`). The
contract reports false-alarm rate and detection delay relative to the same
absolute change time. In the tested pandas builds both spellings resolve to
UTC; naive timestamps follow an unchanged branch.

The direct generated-function probe compares values and error outcomes for
naive, UTC, Paris and New York change times, detected and undetected windows,
and empty input. All cases matched on macOS arm64 with Python 3.11.17 and
pandas 3.0.6 and 3.1.1. The script and raw output are
`event-utc-case.py.txt` and `event-utc-case-output.txt` in
`evidence/pending-probes-2026-11-15/`; the generated source is archived in the
nine-mutant focused evidence. Reproduce from the repository root:

```sh
PYTHONPATH=mutants/src:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/pending-probes-2026-11-15/event-utc-case.py.txt
```

This conditional equivalence proposal is not an approval. Confidence is medium
for the tested environments; other supported timezone databases, pandas builds
and Linux have not been tested, and no fresh complete unit score is available.
