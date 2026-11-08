# Equivalence candidates for `research/lstm_detector.py` — proposed, not accepted

Source revision d296f2f; mutants identified as `research.lstm_detector.xǁLSTMAutoencoderǁ<function>__mutmut_<n>`.
These nine mutants survive both the hosted Linux native run (run 42433394723) and direct execution of the
detector tests. Each carries a semantic argument by the author of the tests. **None is accepted**: the
mechanism in `verification/mutation_policy.py` requires an independent reviewer, a record bound to the
source and catalog digests, and the author may not approve their own proposal. Raw outcomes stay as
`survived` and count in every raw score.

| Mutant | Mutation | Argument | Check made |
| --- | --- | --- | --- |
| `_reconstruction_error__31` | `dim=-1` becomes `dim=+1` | `+1` and `-1` address the same last axis of a 2-D tensor | numeric identity on the tested shapes |
| `_reconstruction_error__35` | `.astype(float)` becomes `.astype(None)` | in the installed pandas/numpy, `astype(None)` yields float64, the same dtype | `pd.DataFrame.astype(None)` returns float64 |
| `_windows__2` | `astype(float)` becomes `astype(None)` | same as above | same |
| `fit__16` | `astype(float)` becomes `astype(None)` | same as above | same |
| `fit__43`, `fit__55` | `replace=False` becomes `replace=None` | numpy's `Generator.choice` tests `replace` for truth; `None` is falsy, so sampling stays without replacement | a distinctness test on 120 of 150 windows passes for the mutant |
| `fit__50` | validation cap `>` becomes `>=` | when the window count equals the cap, `choice` of all indices followed by `np.sort` is the identity | order-preservation test passes for the mutant |
| `settings__41`, `settings__46` | `version("torch")` becomes `version("TORCH")` (and numpy) | distribution names are normalised case-insensitively (PEP 503) | `version("TORCH") == version("torch")` |

Limits: the dtype arguments depend on the pinned pandas and numpy versions; a different version could change them,
which is why an approved record must be bound to the source and catalog digests. Mutants once believed to be
candidates (`fit__29`, a `spread > 1` variant, and `fit__86`, an initial stale counter) were not equivalent and are
now killed by tests: a column with spread below one must be scaled by it, and a non-improving first epoch must count
towards the patience.
