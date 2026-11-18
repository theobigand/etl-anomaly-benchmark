# Bank marketing dummy-column selection

Three historical survivors in `research/temporal_decision.py` (source SHA-256
`f402ba92cdbd8a143608f9ce9d1ab98f68cad5b6c881318f504ab8c0380742d8`)
change how categorical columns are passed to `pd.get_dummies`:

- `research.temporal_decision.x_bank_marketing__mutmut_77` makes the explicit
  column list `None`.
- `research.temporal_decision.x_bank_marketing__mutmut_82` passes `columns=None`.
- `research.temporal_decision.x_bank_marketing__mutmut_86` omits `columns`.

The public loader reads a CSV, preserves aligned labels and times, and encodes
categorical feature columns. The direct generated-function probe used actual
CSV files containing numeric, boolean, unsigned large-integer, string, date-like,
missing and all-numeric features, plus an empty input. It compared returned
frames, dtypes, labels, timestamps, errors and captured warnings. All three
mutants matched the original on macOS arm64 with Python 3.11.17 and pandas
3.0.6/3.1.1, and in the isolated NumPy 1.24.4/pandas 2.0.3/SciPy 1.11.4/
scikit-learn 1.3.2 environment. The executable probe and outputs are
`bank-dummies.py.txt`, `bank-dummies-output.txt` and
`bank-dummies-minimum.log.gz` in `evidence/continuation-2026-11-15/`.
Generated source is preserved in the nine-focused evidence.

These are conditional owner proposals, not approvals. Confidence is medium for
the tested CSV-inferred dtypes; custom injected DataFrames with datetime or
third-party extension columns, other dependency builds, larger data and Linux
were not exhaustively tested. No complete current unit score is implied.
