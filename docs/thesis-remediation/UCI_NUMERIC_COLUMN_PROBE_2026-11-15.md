# UCI loader numeric-column probe

`research.uci_loader.x_read_table__mutmut_23`, source SHA-256
`a1176cd61bd8454c9fa51da682194444feb24529dc401916e8bb94fd212ab691`,
changes the dtype predicate to examine all columns, including numeric columns.
The contract is to load the CSV and repair repeated headers and libsvm-style
tokens without changing already numeric values. For numeric columns produced
by the tested `read_csv`, string-token matching cannot match the libsvm pattern
and `pd.to_numeric` preserves the numeric values and dtype in the cases tried.

Direct generated-function comparisons covered signed and unsigned integers,
booleans, decimal and extreme floating values, infinities, missing columns,
repeated headers, categorical strings, and libsvm tokens. Returned frames,
dtypes, exceptions and captured warnings matched under Python 3.11.17, NumPy
2.4.6 and pandas 3.0.6/3.1.1 on macOS arm64. The executable probe and successful
output are `uci-numeric-columns.py.txt` and
`uci-numeric-columns-rerun-output.txt` in
`evidence/continuation-2026-11-15/`. An initial import attempt during native
mutant regeneration failed and is retained separately. The generated source
SHA-256 is `3cb508cd5acfca86f8cb2b3bfe68018838ad01000d0474b5281a854b560fee81`
and is preserved in `evidence/uci-loader-generated-2026-11-15.py.gz`.

The result is **inconclusive**, not an equivalence proposal. A separate 30,000-row,
24-column numeric CSV probe (14,134,786 bytes) produced identical frames but took
about 0.28 seconds on the original and 0.57 seconds on the mutant in two local
runs. The probe and exact fixture digest are `uci-numeric-cost.py.txt` and
`uci-numeric-cost-output.txt` in the same evidence directory. This limited
measurement suggests a meaningful performance cost; it does not establish a
portable performance requirement or justify a timing-based regression. Other
supported pandas builds, larger inputs and Linux remain untested. The native
mutant has not been remeasured as part of a complete current unit campaign.

```sh
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P docs/thesis-remediation/evidence/continuation-2026-11-15/uci-numeric-columns.py.txt
```
