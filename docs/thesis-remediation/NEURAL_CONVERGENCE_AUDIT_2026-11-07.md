# Convergence audit of the neural detectors — 2026-11-07

## Purpose and method

This audit separates an execution with no recorded exception from evidence of
convergence. It inspected the installed PyOD 3.6.7 signatures, the repository
adapters, the protocols and the archives already under version control. It does
not modify the historical partitions or any numerical result.

**T055 status: partially evidenced.** Convergence is verified for the
autoencoder of the typed benchmark only. For the other five detectors the
archives cannot establish convergence; that is a documented limitation, not a
verified convergence check.

## Available budgets and diagnostics

| detector | origin and budget of the evaluated implementation | stopping rule / retained diagnostic |
| --- | --- | --- |
| `autoencoder` | `MLPRegressor`, at most 300 iterations | `settings()` keeps `max_iter`, `n_iter` and `converged`; the five files `verification/evidence/deep_typed/seed_*.json` have `converged: true`. |
| `vae` | PyOD 3.6.7, default `epoch_num=30` | fixed budget; the registry archives keep neither a loss curve nor a stopping indicator. |
| `deep_svdd` | PyOD 3.6.7, default `epochs=100` | `validation_size=0.1` is a model argument; no convergence diagnostic is exported in the registry archives. |
| `dif` | PyOD 3.6.7, random representations and forests; no epoch parameter | gradient-descent convergence does not apply; no stability measure of the representations is archived. |
| `ae1svm` | PyOD 3.6.7, default `epochs=50` | fixed budget; no loss history or convergence state is exported. |
| `lunar` | PyOD 3.6.7, default `n_epochs=200` | `val_size=0.1` is a model argument; no convergence diagnostic is exported in the registry archives. |

The score adaptations of ECOD/COPOD, VAE, DIF and AE1SVM are described in
`INDUCTIVE_DETECTORS_2026-11-03.md`; they are not convergence checks.

## Archived numerical failures

The 100 envelopes in `verification/evidence/full_registry/pool_deep/runs/` each
have an empty `errors` field. The 100 envelopes in
`verification/evidence/pool_extension/pool_full_deep/runs/` also have an empty
`errors` field; they contain 500 runs per detector, that is 3,000 runs of the
six detectors with no recorded exception. Skips of expensive models remain
separate protocol skips.

These fields only show that the scripts retained no exception. The registry
archives do not keep the effective settings, the losses, the iterations
actually performed or the numerical warnings. They therefore cannot establish
that a PyOD training converged, that it did not silently diverge, or that its
budget was sufficient.

## Consequence for the results and next steps

The wording of the manuscript is limited to the absence of a recorded
exception; it no longer presents this as evidence of convergence. Effective
convergence is documented only for the separate autoencoder case of the typed
benchmark. The LSTM pilot lies outside the registry and keeps its own negative
result: its five Credit Card trainings reached the 20-epoch budget without
converging.

Any new registry campaign must keep, per seed and detector, the effective
arguments, the number of epochs or iterations performed, a stopping reason,
the losses or an appropriate diagnostic, the warnings and the exceptions. Such
a campaign would be prospective and does not rewrite the historical
conclusions.
