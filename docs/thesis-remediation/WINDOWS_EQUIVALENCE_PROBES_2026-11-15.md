# Window score mapping dtype proposals

The following historical survivors are proposed equivalents, not owner
approvals or official exclusions:

- `etl_benchmark.quality.windows.x_scores_to_events__mutmut_7` changes
  `np.empty(len(scores), dtype=float)` to `dtype=None`.
- `etl_benchmark.quality.windows.x_scores_to_events__mutmut_9` omits the
  dtype argument.

The contract maps each window score to its closing event using the supplied
ordering and event index. For the supported NumPy API, `empty` defaults to
float64 when dtype is omitted or None; the original `float` dtype maps to that
same type. See the [NumPy 1.24](https://numpy.org/doc/1.24/reference/generated/numpy.empty.html)
and [NumPy 2.4](https://numpy.org/doc/2.4/reference/generated/numpy.empty.html)
manuals. A dtype match is relevant because assignment casts each score into
this allocated array before constructing the result Series.

Both generated mutants matched the original for a permuted mapping with NaN,
integer scores with duplicate event labels, an empty mapping, and mismatched
score/order lengths. The first three use complete valid permutations; the
last checks an error. `np.empty` is uninitialized before assignment, so these
probes do not infer equivalence for malformed orders that fail to fill each
position. No second runtime was tested; the API documentation and the Python
`float` mapping provide the source-level argument. The recorded environment
is macOS arm64, Python 3.11.17, NumPy 2.4.6, pandas 3.1.1 and mutmut 3.8.0.

Source SHA-256 is `5a4fdd8739edcc33dd786b2b241cf5c3c92ec3e63f6e669ef571d1cb9699c864`;
generated source SHA-256 is
`548f6082bc9d51025473094549af962ec6af4638a29c1b839d0d139510c62031`.
The generated source is preserved in `evidence/windows-generated-2026-11-15.py.gz`;
probe and results are `evidence/windows-empty-probe-2026-11-15.py` and `.txt`.
Reproduce with the matching generated module and interpreter:

```sh
PYTHONPATH=mutants/src ~/.cache/etl-mutation-venv/bin/python \
  docs/thesis-remediation/evidence/windows-empty-probe-2026-11-15.py
```

The historical raw score was 54/57 (94.74%), L4 threshold 98%. Hypothetically
excluding these two alone gives 54/55 (98.18%), which would cross that
historical threshold. This arithmetic is not an owner decision or an official
current score; the earlier packet's separate proposal is not included. Fresh
measurement, owner decisions and independent review remain necessary.
