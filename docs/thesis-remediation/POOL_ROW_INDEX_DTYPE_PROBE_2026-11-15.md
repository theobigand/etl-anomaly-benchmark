# Chronological pool row-index dtype probes

The following historical survivors alter the temporary row-position column in
`research/pool_chrono.py`, source SHA-256
`cd8b6eff471b942804223040ca94f119f2ab710479c341dfd3d2668342eff035`:

- `research.pool_chrono.x_load_pool_dataset__mutmut_19` changes the position
  generator's `dtype=float` to `dtype=None`.
- `research.pool_chrono.x_load_pool_dataset__mutmut_21` omits that dtype.
- `research.pool_chrono.x_load_pool_dataset__mutmut_28` changes the later cast
  from `astype(int)` to `astype(None)` before positional selection.

The observable contract aligns the surviving feature rows, labels and UTC
timestamps after removing unreadable times and downsampling the anomaly class.
The first two mutants produce integer positions instead of floating positions;
the last retains floating positions instead of integer positions. In the tested
pandas versions `iloc` accepted those integral floating positions and selected
the same rows. The direct generated-function probe exercised different input
sizes, both passing and rejected label counts, downsampling and stray-header
removal. All returned frames, labels, times, dropped counts and error outcomes
matched the original on macOS arm64 with Python 3.11.17, NumPy 2.4.6,
scikit-learn 1.9.1, and pandas 3.0.6 and 3.1.1.

Reproduce from the repository root with the generated source available:

```sh
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/pool-row-index.py.txt
```

The raw output is `evidence/continuation-2026-11-15/pool-row-index-output.txt`;
the generated source is preserved with the nine-focused evidence. These are
conditional proposals only. Confidence is medium for tested practical dataset
sizes and dependency builds: very large positions beyond exact floating-point
integer range, alternative metadata, other supported versions, and Linux have
not been exhaustively tested. No owner approval or full unit score is implied.

Additional lower-bound dependency results are in [the compatibility addendum](MINIMUM_DEPENDENCY_PROBES_2026-11-16.md).
