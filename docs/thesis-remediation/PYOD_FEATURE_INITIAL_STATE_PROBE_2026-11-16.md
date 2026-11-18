# PyOD feature-name initial state

`etl_benchmark.quality.ml.xǁPyODDetectorǁ__init____mutmut_4` changes the initial `feature_names_` from `None` to an empty string. Current source SHA-256: `4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`; generated Linux diagnostic source SHA-256: `7fb6810432676164f022092e34f924a43b6405ab06f263e11a9e3e3143974fbe`.

The executable `evidence/continuation-2026-11-15/pyod-feature-init-probe.py.txt` compares generated original and mutant constructors using a real isolation-forest detector. In Python 3.11.17, NumPy 2.4.6, pandas 3.1.1 and PyOD 3.6.7, fresh construction and a failed no-numeric-column fit expose the different attribute values, while both score calls report the same not-fitted error. After a successful fit, feature names and a scored value match. The fitted feature names are tested and consumed, but no repository consumer of the pre-fit value was found. The initial attribute is externally observable and its supported pre-fit contract is not specified; this remains inconclusive. Other wrapped estimators, concurrent mutation, and dependency environments were not exhausted.

The generated source is also saved as `evidence/continuation-2026-11-15/ml-diagnostic-generated.py.gz`. The probe reads it from the extracted diagnostic tree; restore it there before rerunning, without replacing the live mutation cache.
