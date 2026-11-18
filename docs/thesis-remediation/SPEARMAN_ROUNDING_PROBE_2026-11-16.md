# Temporal H1 rounding boundary

`research.temporal_decision.x_hypotheses__mutmut_119` changes rounding of a
Spearman coefficient from 9 to 10 decimal places before comparison with 0.8.
Source SHA-256:
`f402ba92cdbd8a143608f9ce9d1ab98f68cad5b6c881318f504ab8c0380742d8`.
The preregistered study compares detector rankings and requires correlation at
least 0.8; the default study currently uses four methods.

A rank-space enumeration of every pair of nonconstant tied or untied rank
vectors for two through four methods found no decision difference between the
rounding rules (5,476 pairs at four methods). For at most 17 methods, a simple
exact-arithmetic bound provides additional context: double-centered ranks are
integers; if `r = p/sqrt(A*B)` is not exactly 4/5, then
`|r - 4/5| >= 1/(45*M^2)` for `M = n*(n^2-1)/3`. At `n=17` that lower bound
is approximately `8.34e-9`, larger than the rounding window. Floating-point
error is not formally bounded by that integer argument; constant ranks also
produce NaN and were excluded from the enumeration. The executable enumeration
and output are `spearman-rounding.py.txt` and `spearman-rounding-output.txt`
in `evidence/continuation-2026-11-15/`, run with SciPy 1.17.1 and NumPy 2.4.6
in both local environments.

The public `hypotheses` function itself does not enforce a maximum method
count, so the bounded study argument does not establish equivalence for all
accepted inputs. The mutant remains **inconclusive**, not an owner proposal.
Do not add a numerical-fingerprint test without a supported scientific
contract for such a boundary. No archived measurement changed.
