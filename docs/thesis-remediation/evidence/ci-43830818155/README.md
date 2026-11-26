# CI evidence at `eb1d679`

Exact-head CI run: https://github.com/theobigand/etl-anomaly-benchmark/actions/runs/43830818155 . The `test`, `faults`, and `slides` jobs succeeded. GitHub's artifact digests matched the downloaded zip bytes:

- `verification-fast.zip`: SHA-256 `2dee33fd953f2b5617d13aa616b19647d47733e73e33ca25a386a4da667a4c5c`.
- `verification-faults.zip`: SHA-256 `81e1b1e0d49dfdc37b2ae0794b7cac070ce2039177266d331ed003798b0933e7`.

The FAST coverage report has 1,800/1,800 measured statements and 354/354 measured branches. The separate verifier report has 3,222/3,222 measured statements and 1,262/1,262 measured branches. The FAST JUnit report records 4,024 tests, zero failures, zero errors and zero skips. These counts are for their configured scopes, not a fresh complete mutation campaign or proof that every applicable production surface was covered.

The slides artifact has GitHub SHA-256 `5c7eb03981d7d6b20c6dd63b410f0b3141739d6c3bbc2858d24f48522e777fa3` and was not downloaded into this checkpoint. The test job's pinned mypy and verifier-coverage steps succeeded. Pull-request release and mutation workflows were skipped.
