# Zero-correlation injection boundary

`research.injection.x_inject__mutmut_146` changes `corr > 0` to `corr >= 0`
when choosing opposite quantile tails for a multivariate injection. Source
SHA-256: `cdfc81d98e3470ccdf5f7930d7e987b1bdad3545e060552f3a3bb1d170d8cb39`.
The changed branch is reachable only when the strongest selected pair has
exactly zero computed correlation.

A 4,096-row carrier built from mutually orthogonal integer Walsh patterns had
16 distinct values per feature, no duplicate rows and passed the project's
carrier preparation. In the tested pandas builds its strongest computed
correlation was about `1.21e-16`, not exactly zero, so both generated functions
returned equal frames for two seeds. A further deterministic search among 128
four-term Walsh features found nine exact-zero pair edges but no four-feature
zero-correlation clique with unique rows in the searched set. These are
counterexample searches, not a proof that the boundary cannot occur. Scripts
and output are `injection-zero-correlation.py.txt`,
`injection-zero-correlation-output.txt`, `injection-zero-search.py.txt` and
`injection-zero-search-output.txt` in
`evidence/continuation-2026-11-15/`.

Even if an exact-zero input is found, whether either opposite-tail orientation
is a meaningful multivariate anomaly when the clean features are uncorrelated
requires a scientific contract. This identity remains **inconclusive**, not an
owner proposal or a fabricated regression. Tests used Python 3.11.17, NumPy
2.4.6 and pandas 3.0.6/3.1.1 on macOS arm64; the larger search used pandas
3.1.1 only. No scientific archive changed.

A subsequent deterministic search found an exact-zero three-column example:
96 rows drawn from the full binary factorial, in an ordering for which pandas
3.0.6 and 3.1.1 both computed exactly zero for every cross-correlation. The
generated original and mutant produced different assignments to the positive
and negative tails for seeds 1 and 11. The executable search and direct probes
and their outputs are `injection-zero-three-search.py.txt`,
`injection-zero-three-probe.py.txt`, and the corresponding output files in
`evidence/continuation-2026-11-15/`. An initial search attempt failed because
the pandas array was read-only; its output is retained separately as
`injection-zero-three-search-error.txt` and the corrected search explicitly
copies the array.
The generated `injection.py` used by the direct probe has SHA-256
`0a049b613cdff4161eabffebcb6f7c7a0dfc67379516fec3e6bac09781988cdd`
and matches the preserved Linux diagnostic archive.

This example has only eight unique rows and three columns, so it does not pass
the established carrier preparation requirements of at least 3,000 unique
rows and four continuous columns. It proves a direct-function distinction but
not that the preregistered carrier domain reaches it or that the two tail
orientations change a scientifically defined result. The classification remains
inconclusive while those questions are unresolved.
