# Lower-bound dependency probe addendum

The continuation ran existing direct generated-mutant probes in an isolated
`uv run --no-project` environment using Python 3.11.17, NumPy 1.24.4, pandas
2.0.3, SciPy 1.11.4, scikit-learn 1.3.2, mutmut 3.8.0 and Faker 40.44.0 on
macOS arm64. These versions satisfy the repository's declared dependency
lower bounds. No project manifest or lock changed.

The following probes exited 0 and printed no mismatches: pool numeric dtype and
boundary cases; pool row-position alignment; multi-schema transaction and
per-type metrics; typed per-type metrics; injection carrier preparation; drift
outlier replacement; window UTC spelling; and rule/window initial-state
lifecycles. The corresponding `<probe>-minimum.log.gz` files are in
`evidence/continuation-2026-11-15/`. Two initial invocations of the drift and
window probes used an incorrect directory and exited 2; those failures and
the successful `*-minimum-rerun.log.gz` files are retained. The scripts and
individual behavior analyses are linked from the individual triage records.
The separate [pool compatibility probe](POOL_MINIMUM_COMPAT_PROBE_2026-11-16.md)
also tested Python and PyArrow string storage.

These are supplemental direct experiments, not native full-unit scores or
owner approvals. They do not cover every dependency version, third-party dtype
or Linux. The declared lower bounds do not themselves constitute the locked
Cardio environment, and no scientific numerical assertion or archive changed.

The direct classical-model default/NaN probe also passed in this environment;
its log is `ml-defaults-mutants-minimum.log.gz` in the same evidence directory.
