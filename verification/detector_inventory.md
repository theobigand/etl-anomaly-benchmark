# Comparable detector inventory

This is the prospective inventory for T048--T050. It covers the 17 detectors
in the comparable registry: three rules, eight classical models and six neural
models. `drift` is intentionally absent: it requires a time column and remains
an opt-in temporal study detector. The sequence and membership are checked by
`tests/test_detector_inventory.py` against `registry.py`.

All learned models accept a numeric `pandas.DataFrame`; the shared detector
base selects numeric features, median-imputes and standardizes from the training
frame only. Scores are indexed by the evaluated rows and are oriented so larger
values mean more anomalous. For PyOD models, `contamination` is fixed from the
training prevalence (bounded by the recorded configuration) before scoring;
the library's fitted decision threshold then produces flags. No detector selects
a threshold from validation or test labels.

| Name | Family | Implementation origin | Accepted input | Preprocessing | Training cap | Score and direction | Decision threshold / adaptation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `zscore` | Rule | project implementation | numeric frame | train mean and standard deviation | none | maximum absolute standardized deviation; higher is anomalous | fixed 3-sigma rule |
| `iqr` | Rule | project implementation | numeric frame | train quartiles and IQR | none | largest distance beyond a train IQR fence; higher is anomalous | fixed 1.5-IQR fences |
| `great_expectations` | Rule suite | Great Expectations 1.24.0 wrapper | numeric and nullable columns | train missingness and 0.1%/99.9% numeric bounds | none | fraction of active expectations violated; higher is anomalous | any failed expectation flags a row |
| `isolation_forest` | Classical ML | PyOD 3.6.7 / scikit-learn backend | numeric frame | shared train-only imputation and scaling | none | PyOD anomaly score; higher is anomalous | train-prevalence contamination |
| `lof` | Classical ML | PyOD 3.6.7 | numeric frame | shared train-only imputation and scaling | skipped above 50,000 train rows | PyOD local-density anomaly score; higher is anomalous | train-prevalence contamination |
| `ocsvm` | Classical ML | PyOD 3.6.7 | numeric frame | shared train-only imputation and scaling | skipped above 20,000 train rows | PyOD signed anomaly score; higher is anomalous | train-prevalence contamination |
| `ecod` | Classical ML | PyOD 3.6.7, inductive project scorer | numeric frame | shared train-only imputation and scaling | none | train empirical-tail score; higher is anomalous | train-prevalence contamination; test batch does not alter tails |
| `copod` | Classical ML | PyOD 3.6.7, inductive project scorer | numeric frame | shared train-only imputation and scaling | none | train copula-tail score; higher is anomalous | train-prevalence contamination; test batch does not alter tails |
| `hbos` | Classical ML | PyOD 3.6.7 | numeric frame | shared train-only imputation and scaling | none | inverse histogram-density score; higher is anomalous | train-prevalence contamination |
| `knn` | Classical ML | PyOD 3.6.7 | numeric frame | shared train-only imputation and scaling | skipped above 50,000 train rows | k-nearest-neighbour distance; higher is anomalous | train-prevalence contamination |
| `pca` | Classical ML | scikit-learn 1.9.1 project implementation | numeric frame | shared train-only imputation and scaling | none | mean reconstruction error; higher is anomalous | train-prevalence contamination; retains 95% train variance |
| `autoencoder` | Neural | project PyTorch MLP autoencoder | numeric frame | shared train-only imputation and scaling | 20,000 train rows | reconstruction error; higher is anomalous | train-prevalence contamination |
| `vae` | Neural | PyOD 3.6.7, deterministic latent scorer | numeric frame | shared train-only imputation and scaling | 20,000 train rows | reconstruction error using latent mean; higher is anomalous | train-prevalence contamination; no score-time sampling |
| `deep_svdd` | Neural | PyOD 3.6.7 | numeric frame | shared train-only imputation and scaling | 20,000 train rows | distance from learned centre; higher is anomalous | train-prevalence contamination |
| `dif` | Neural | PyOD 3.6.7, train-scaled representation scorer | numeric frame | shared train-only imputation and scaling | 20,000 train rows | isolation score in train-standardized representation; higher is anomalous | train-prevalence contamination; no test-batch scaling |
| `ae1svm` | Neural | PyOD 3.6.7, padded batch wrapper | numeric frame | shared train-only imputation and scaling | 20,000 train rows | PyOD AE1SVM anomaly score; higher is anomalous | train-prevalence contamination; singleton final batches are padded then trimmed |
| `lunar` | Neural | PyOD 3.6.7 | numeric frame | shared train-only imputation and scaling | 20,000 train rows | learned neighbour-distance score; higher is anomalous | train-prevalence contamination |

PyOD model defaults are retained unless the documented adaptation is necessary
to meet the per-row inductive contract. The adaptation audit in
`docs/thesis-remediation/INDUCTIVE_DETECTORS_2026-11-03.md` distinguishes those
fixes from changes to the reference algorithms. The table records protocol and
implementation facts; it does not claim comparable measured performance or
convergence for every detector. Those remain separate experimental tasks.
