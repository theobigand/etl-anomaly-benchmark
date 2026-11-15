# Multi-schema drift specification boundary

`research.multi_schema.x_make__mutmut_218`, `_221` and `_225` change a strict
zip over a schema's drift columns and three configured multipliers to a
non-strict form. A transaction schema with only two drift columns is malformed:
the original rejects it, whereas each generated mutant silently creates a
315-row dataset using only two multipliers. Rejecting this incomplete
experimental configuration prevents a partial drift specification from being
accepted as the three-column protocol.

The regression constructs the malformed schema from the real transaction
schema and checks that `make` refuses it. Against each generated mutant the
same test failed with `DID NOT RAISE ValueError` (RED, exit 1); the original
and the two affected multi-schema test files passed (GREEN/regression,
exit 0). RED was run separately for each suffix:

```sh
MUTANT_UNDER_TEST="research.multi_schema.x_make__mutmut_218" \
PYTHONPATH=mutants:mutants/research:src ~/.cache/etl-mutation-venv/bin/python -P \
  -c 'import sys, research.multi_schema as m, pytest; sys.modules["multi_schema"]=m; raise SystemExit(pytest.main(["-c", "/dev/null", "--import-mode=importlib", "-p", "no:cacheprovider", "-q", "research/tests/test_multi_schema_contracts.py::test_a_schema_with_an_incomplete_drift_specification_is_refused"]))'
```

Substitute suffix `221` and `225` for the other RED runs. GREEN/regression:
`~/.cache/etl-mutation-venv/bin/python -m pytest
research/tests/test_multi_schema_contracts.py research/tests/test_multi_schema.py
--disable-warnings -q` exited 0. The source SHA-256 is
`1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`;
the generated module prior to the native run is retained at
`evidence/multi-schema-generated-2026-11-15.py.gz` and its uncompressed
SHA-256 is `8b48b7c67a6e97e0bfa55683104c6f7c28ff77fcc949ba1e6281003424dbdf8e`.
The direct checks used macOS arm64, Python 3.11.17, NumPy 2.4.6, pandas 3.1.1
and mutmut 3.8.0. The native three-mutant run exited 0 and recorded each as killed (mutant
exit code 1). Its command, context, metadata and log are retained in
`evidence/multischema-drift-focused-2026-11-15.json` and associated files.
The run used the case-insensitive local filesystem and started with the test
uncommitted on `bc67ad5`; it is not a full unit or campaign measurement.

## Zero-correlation multivariate boundary

`research.multi_schema.x_make__mutmut_167` and `_168` change the branch for
zero feature-pair correlation. A transaction-schema carrier with positive
values 1 and 3 was constructed with exactly zero correlation in the clean
training portion. The original makes each multivariate outlier take opposite
tails `(1, 3)` or `(3, 1)`; the mutants instead create same-tail pairs
`(1, 1)` or `(3, 3)`. This changes the injected anomaly mechanism, rather
than only an internal representation.

The regression checks that the constructed correlation is exactly zero and
that every multivariate-outlier pair lies on opposite sides of 2. Both
mutants failed this assertion (RED, exit 1); the original and both affected
multi-schema test files passed (GREEN/regression, exit 0; 40 tests). RED uses
the same preload command above with the test node
`research/tests/test_multi_schema_contracts.py::test_uncorrelated_features_receive_opposite_multivariate_tails`
and suffix 167 or 168. Source digest, generated source and environment are
as recorded above. The focused native run exited 0 and recorded both mutants as killed
(exit code 1). The command, context, log and metadata are in
`evidence/multischema-zero-focused-2026-11-15.json` and associated files.
It used the case-insensitive local filesystem with uncommitted tests on
`bc67ad5`; this is not a full unit or campaign measurement.

## Transaction balance floor: preliminary finding

`research.multi_schema.x__transactions__mutmut_79` removes the zero lower
bound on `balance_after`; `_101` changes it to one. On a 3,000-row carrier
with seed 0, the original had four zero balances and no negative balances;
`_79` had four negative balances, and `_101` had no zeros and minimum one.
The observed negative balances conflict with the existing nonnegative schema
contract. The zero-versus-one result changes the configured floor. The regression
checks the scientific properties that balances are nonnegative and that the
zero floor is reached in the seeded 3,000-row sample; it does not pin exact
values or counts. Both mutants failed their respective property assertions
(RED, exit 1), while the original and the affected test files passed
(GREEN/regression, exit 0; 41 tests). The test depends on this seed producing
a floor event, a dependency limitation if the random generator changes. The focused native run subsequently killed both; see
`evidence/multischema-floor-focused-2026-11-15.json` and its log and metadata. The source and generated module digests are above. The command
`PYTHONPATH=mutants/research:src ~/.cache/etl-mutation-venv/bin/python
 docs/thesis-remediation/evidence/multischema-floor-probe-2026-11-15.py`
and its `.txt` output preserve the probe. These observations are not fresh
unit scores.

RED uses the preload command above with suffix `79` or `101`, mutation name
`research.multi_schema.x__transactions__mutmut_<suffix>`, and test node
`research/tests/test_multi_schema_contracts.py::test_transaction_balance_floor_is_zero_when_noise_would_make_it_negative`.
The native two-mutant run exited 0, and the metadata records both as killed
(exit code 1). It ran on the case-insensitive local filesystem with the
regression uncommitted on `bc67ad5`; it is not a complete unit measurement.
