Replace the global 95% mutation threshold with **L1: 80%, L2: 90%, L3: 95%, L4: 98%**, according to the effect of a defect on the benchmark and its results. Historical reports keep their original criterion.

### Current status

Work is on `feat/risk-tiered-mutation-policy`, through 08391b1. Risk calculations, native-result reading, cache control, DEEP evidence construction, the public mutation gate, the DEEP Makefile target, and DEEP bundles require a bound native campaign; changing the risk policy ages published verification claims and invalidates the CI mutation-cache key. The complete verifier gate measures 2,789/2,789 lines and 1,078/1,078 branches; this is bounded software evidence, not scientific validation. Release policy v2 now rejects legacy global mutation envelopes for current certification. Full release reconciliation and workflow artifact integration remain pending. The prospective v2 scope covers 92 classified production modules across source, experiment, research and verification roots, with three explicit no-mutant declarations.

The latest focused results are **295/318 (92.77%)** for the controller at 1177578 and **470/535 (87.85%)** for the arithmetic module at 0d4a0f9. Both are below L4; all survivors remain counted. Unit tests and typing pass; this does not establish scientific validity or complete the migration. A full campaign also requires a scientific environment without the conflicting package metadata found locally.

### Completion criteria

- [x] Support the four fixed thresholds, justify classifications and reject unclassified production code.
- [x] Cover source, experiments, research and verification modules; document technical exclusions without narrowing the required scope.
- [x] Use exact comparisons for each required module; stronger modules or lower-risk scopes cannot compensate for a failure.
- [x] Reconcile all mutant identities and outcomes; reject incomplete, duplicate, malformed, interrupted or untested evidence.
- [ ] Bind evidence to policy/classification versions and hashes, source, tests, configuration, tools and dependencies; record counts, exclusions and each scope's result.
- [ ] Make release checks recompute compliance and reject missing, stale or inconsistent evidence.
- [ ] Reuse valid cached results; invalidate changed execution inputs, while policy-only changes require reevaluation rather than unnecessary reexecution.
- [x] Pass boundary, forged-evidence, cache and release regressions; preserve the actual verification and mutation results.
- [ ] Complete independent review after deterministic checks and resolve its findings.
- [x] Update documentation, paper and slides; preserve historical figures, T001–T415 and linked tracking.

Next: connect the shared calculations to DEEP, evidence bundles and release checks, then complete mutation validation and independent review. Keep this issue open until all criteria are met.

[Implementation notes and verification results](https://github.com/theobigand/etl-anomaly-benchmark/blob/feat/risk-tiered-mutation-policy/docs/thesis-remediation/RISK_MUTATION_MIGRATION.md)

Related: #100, #103, #110, #111; historical #84. This changes verification requirements, not the research questions or experimental results.

