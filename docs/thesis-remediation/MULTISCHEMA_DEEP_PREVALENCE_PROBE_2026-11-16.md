# Multi-schema deep calibration counterexample

`research.multi_schema.x_evaluate__mutmut_21`, source SHA-256
`1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`,
passes `None` instead of the training anomaly prevalence to the deep detector
factory. The published evaluation protocol calibrates contamination from the
training partition; `None` instead selects the default contamination.

A direct generated-function probe restricted the run to a real, small CPU DIF
detector and reduced its ensemble size while preserving the factory's real
contamination handling. With 600 generated transaction rows and seed 4, the
training anomaly share was about 0.176. The original and mutant produced
different per-type recall and precision tables, and false-positive rates of
about 0.184 and 0.105 respectively. Two other row/seed combinations also
changed results. The values are observations, not numerical test targets. The
probe and output are `multischema-deep-prevalence.py.txt` and
`multischema-deep-prevalence-output.txt` under
`evidence/continuation-2026-11-15/`; generated source is preserved with the
nine-focused evidence.

This is a demonstrated scientific behavior difference, not an equivalence
proposal. Add a regression for the preregistered training-prevalence
calibration, verify RED on the generated mutant and GREEN on the original,
and obtain a native verdict after the current run finishes. It is not yet a
verified kill or a complete unit measurement.
