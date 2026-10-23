# etl-anomaly-benchmark

![ci](https://github.com/theobigand/etl-anomaly-benchmark/actions/workflows/ci.yml/badge.svg)

A reproducible benchmark comparing three families of anomaly detectors for data quality (rule-based, classical ML, deep learning), each run inside a small ETL pipeline rather than in isolation. This is the code for my master's thesis at ESILV.

The question it tries to answer: does adding machine learning to an ETL pipeline actually improve anomaly detection over plain rules, and if so, for which kinds of anomalies? The planned original contribution is a per-anomaly-type comparison (a method-by-type heatmap on a controlled synthetic dataset), which existing benchmarks such as ADBench measure only in aggregate.

> Theo Bigand, ESILV M1/M2, 2026-2027

## Status

- [x] ETL pipeline as composable stages (extract, transform, detect, load)
- [x] Common `Detector` interface (fit / predict / score, PyOD-compatible)
- [x] Rule-based detectors: Z-score, IQR, Great Expectations
- [x] Classical ML detectors (via PyOD): Isolation Forest, LOF, One-Class SVM, ECOD, COPOD, HBOS, KNN, PCA
- [x] Neural detectors (opt-in, PyTorch, CPU): autoencoder, VAE, Deep SVDD, DIF, AE1SVM, LUNAR; the LSTM autoencoder stays in `research/`
- [x] Synthetic dataset (6 anomaly types), per-type recall + precision, heatmap
- [x] Evaluation protocol: stratified 70/15/15 split, 5 seeds, mean ± std
- [x] ML contamination read from the train-set prevalence
- [x] Real and synthetic data: a pool of 152 open datasets, with Credit Card Fraud, Cardio (rare anomalies) and Water Quality worked out as examples, plus Faker-generated synthetic datasets
- [x] Time-aware `drift` detector; injection severity is a tunable multiplier
- [x] Precision-recall curves, contamination sweep, detection-vs-severity curves
- [x] CI (GitHub Actions: ruff + pytest)
- [x] CPU reconstruction autoencoder (opt-in: registered, not yet in the thesis tables)
- [x] Chronological split and a windowed drift monitor, tested separately from the row-level metrics
- [x] Causal sliding windows with leakage and alignment tests, ready for a sequence model
- [x] Pool of 152 open datasets, pinned by checksum (`verification/dataset_pool.md`)
- [x] Typed anomaly injection on 42 real tables (`verification/typed_injection.md`)
- [x] Benchmark on the 100 labelled pool problems: `python research/labelled_benchmark.py --output <dir>` then `python research/labelled_summary.py --runs <dir> --output <dir>` (`verification/labelled_pool.md`, results in `verification/evidence/labelled_pool/`)
- [x] Every study extended to the whole pool (`verification/pool_extension.md`, results in `verification/pool_extension_results.md`, archives in `verification/evidence/pool_extension/`): one-pass run on the 100 labelled problems (`python research/pool_full.py`), typed injection and severity on the 58 eligible tables (`python research/pool_typed.py eligibility|reference|severity`), end-to-end pipeline on the 152 datasets (`python research/pool_etl.py`), chronological split on the 5 labelled datasets with a time variable (`python research/pool_chrono.py`, `python research/time_scan.py`), file check (`make verify-pool`)
- [x] Chronological pilot, LSTM autoencoder pilot, cost study
- [x] Autoencoder and LSTM autoencoder rows in the per-type matrix, trained to convergence (`verification/deep_typed.md`, `.venv/bin/python research/deep_typed.py --output <dir>`)
- [x] Two further synthetic schemas, transactions and sensors (`verification/multi_schema.md`, `python research/multi_schema.py --output <dir>`)
- [x] Related work with verified references (`verification/references.md`) and the IMRaD manuscript with the verification in appendices
- [x] Complete detector registry: 8 classical and 6 neural detectors added, every study rerun, 6 pre-registered hypotheses (`verification/full_registry.md`, results in `verification/full_registry_results.md`; neural runs: `python research/full_registry.py real|synthetic --output <dir>`, `research/labelled_benchmark.py --methods deep`, `research/typed_run.py --methods deep`, `research/multi_schema.py --methods deep`; tables and figures: `python research/full_registry_summary.py`)
- [x] Decision-level study under temporal shift on Credit Card and Bank Marketing (`verification/temporal_decision.md`, `python research/temporal_decision.py --output <dir>`)
- [ ] Author review of the related work and the IMRaD draft, Kyoto-2006+ rights and download (M2)
- [ ] More imbalanced real datasets

## Install

```bash
conda env create -f environment.yml
conda activate etl-benchmark
```

`environment.yml` installs the package in editable mode (`pip install -e .`), so code changes are picked up without reinstalling. It also installs PyTorch (conda-forge `pytorch`), which only the six neural detectors need; it is imported when one of them is fitted. Install PyTorch from conda in this environment: a pip wheel brings its own OpenMP runtime, which clashes with the conda one. In CI, `pip install -e ".[dev]"` gets the CPU build from the PyTorch index.

## Data

The Credit Card Fraud dataset (~150 MB) is not committed. Download it and drop the CSV in `data/`:

1. https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
2. put `creditcard.csv` in `data/`

The synthetic dataset is generated locally (deterministic, not committed). The Water
Quality CSV is a small download, also not committed (see `data/README.md`).

```bash
make synthetic   # writes data/synthetic.csv from src/etl_benchmark/synthetic.py
```

## Usage

```bash
make pipeline          # ETL demo: run one detector through the pipeline
make benchmark         # Credit Card Fraud, 5 seeds, stratified split
make benchmark-water   # Water Quality
make benchmark-cardio  # fetch + benchmark the rare-anomaly Cardio dataset
make synthetic         # generate the per-anomaly-type dataset
make heatmap           # multi-seed per-type benchmark -> paper/figures/heatmap_synthetic.png
make curves            # precision-recall curves + Isolation Forest contamination sweep
make severity          # detection-rate versus injection-severity curves
make test              # pytest
make lint              # ruff check + format check
make verify-fast       # offline tests, coverage and evidence
make verify-deep       # mutation campaign on src/ and experiments/ (95% gate)
make verify-faults     # deliberate defects on a temporary copy must fail a test
make verify-real       # all three research datasets must match the manifest
make verify-release    # certify the evidence required by verification/release_policy.json (local report, not an attestation)
make clean             # remove generated artifacts
```

The demo runs Z-score by default and accepts any registered detector:

```bash
python -m etl_benchmark --detector iqr
python -m etl_benchmark --detector isolation_forest
```

Registered detectors: `zscore`, `iqr`, `great_expectations`, `isolation_forest`, `lof`,
`ocsvm`, `ecod`, `copod`, `hbos`, `knn`, `pca` (the default sweep), `drift` (time-aware, opt-in,
synthetic dataset only) and the opt-in neural ones `autoencoder`, `vae`, `deep_svdd`, `dif`, `ae1svm`, `lunar`.

Every benchmark uses a 70/15/15 split (fit on train, metrics on the held-out
test set), repeats over the seeds in `config.BENCHMARK_SEEDS`, and reports mean ± std.
Real datasets are stratified by label; the synthetic dataset groups rows by
`customer_id` before stratification so copies cannot cross partitions. The ML
contamination is set to the train-set anomaly prevalence, a label-informed
operating-point choice. The real-data CLI also accepts
`--calibration fixed --fixed-contamination 0.02` as a label-free preset. This
setting is chosen before evaluation and does not use the training, validation
or test labels to set the flag threshold. It is a separate comparator: the
tables below retain the train-prevalence policy. The synthetic benchmark and
the main curves use that same baseline; the contamination sweep deliberately
varies the threshold on a fixed grid to show sensitivity, without choosing a
winner from the test scores. `PR-AUC` is average precision.

The fixed 0.02 comparator has now been run on the three example datasets with
the same seeds and splits. Its tables are archived in
`verification/evidence/fixed_benchmark_*.csv`. The value was fixed before
these runs, but after the baseline results were known; this is an exploratory
sensitivity check, not an independent confirmatory test. For Isolation
Forest, F1 changes from 0.203 to 0.102 on Credit Card Fraud, 0.618 to 0.406
on Cardio, and 0.512 to 0.023 on Water Quality. The score ranking and PR-AUC
do not change with the threshold.

The [verification protocol](verification/README.md) records current coverage,
the mutation campaign and the checks required before a thesis release. The
repository-wide verification status is currently **INCOMPLETE**.

```bash
python experiments/run_benchmark.py --dataset water_quality --seeds 42
python experiments/run_synthetic_benchmark.py --seeds 42 --rows 3000   # quick
```

## Current results

Mean over 5 seeds on the 15% held-out test split.

### Credit Card Fraud (283,726 rows, 0.167% fraud)

| Detector | Prec | Rec | F1 | ROC-AUC | PR-AUC | Flag % | detect |
|---|---|---|---|---|---|---|---|
| Z-score | 0.011 | 0.870 | 0.021 | 0.926 | 0.078 | 13.4 | 0.03 s |
| IQR | 0.003 | 0.966 | 0.007 | 0.911 | 0.018 | 48.6 | 0.12 s |
| Great Expectations | 0.037 | 0.676 | 0.070 | 0.830 | 0.182 | 3.1 | 1.26 s |
| Isolation Forest | 0.202 | 0.206 | 0.203 | 0.934 | 0.120 | 0.2 | 1.70 s |
| ECOD | 0.260 | 0.268 | 0.262 | 0.930 | 0.175 | 0.2 | 3.04 s |
| COPOD | 0.310 | 0.299 | 0.303 | 0.927 | 0.213 | 0.2 | 3.04 s |
| HBOS | 0.337 | 0.318 | 0.326 | 0.931 | 0.216 | 0.2 | 0.97 s |
| PCA | 0.139 | 0.132 | 0.135 | 0.831 | 0.105 | 0.2 | 0.70 s |
| Autoencoder | 0.083 | 0.141 | 0.103 | 0.892 | 0.066 | 0.3 | n/m |
| VAE | 0.162 | 0.237 | 0.191 | 0.929 | 0.142 | 0.2 | n/m |
| Deep SVDD | 0.261 | 0.546 | 0.346 | 0.918 | 0.289 | 0.4 | n/m |
| DIF | 0.287 | 0.355 | 0.317 | 0.922 | 0.242 | 0.2 | n/m |
| AE1SVM | 0.184 | 0.223 | 0.201 | 0.937 | 0.144 | 0.2 | n/m |
| LUNAR | 0.138 | 0.535 | 0.216 | 0.941 | 0.136 | 0.7 | n/m |

With contamination set to the prevalence, Isolation Forest flags only 0.17% of rows and
reaches a precision of 0.20 (the first usable operating point), at a recall of 0.21 and
with real seed variance (F1 = 0.20 ± 0.07). HBOS, COPOD and ECOD do better on this dataset
(F1 0.33, 0.30, 0.26) and Deep SVDD has the best F1 (0.35 ± 0.08). LOF, KNN and One-Class SVM
do not scale to 284k rows in the pipeline. `n/m`: the neural models were run in parallel, so their
times are not published; the cost study measures them alone.

### Cardio (1,831 raw rows; 1,822 after deduplication, 9.6% anomalies)

| Detector | Prec | Rec | F1 | ROC-AUC | PR-AUC | Flag % |
|---|---|---|---|---|---|---|
| Z-score | 0.49 | 0.81 | 0.61 | 0.93 | 0.61 | 16.6 |
| IQR | 0.21 | 0.90 | 0.33 | 0.78 | 0.30 | 43.4 |
| Great Expectations | 0.50 | 0.21 | 0.29 | 0.59 | 0.19 | 4.6 |
| Isolation Forest | 0.64 | 0.61 | 0.62 | 0.94 | 0.70 | 9.9 |
| LOF | 0.25 | 0.27 | 0.26 | 0.62 | 0.24 | 10.7 |
| One-Class SVM | 0.56 | 0.61 | 0.58 | 0.94 | 0.63 | 10.7 |
| ECOD | 0.57 | 0.59 | 0.57 | 0.95 | 0.69 | 10.2 |
| COPOD | 0.61 | 0.61 | 0.60 | 0.93 | 0.69 | 9.9 |
| HBOS | 0.52 | 0.52 | 0.51 | 0.86 | 0.57 | 10.2 |
| KNN | 0.40 | 0.47 | 0.43 | 0.78 | 0.47 | 11.7 |
| PCA | 0.33 | 0.39 | 0.36 | 0.73 | 0.37 | 11.4 |
| Autoencoder | 0.32 | 0.38 | 0.35 | 0.74 | 0.35 | 11.7 |
| VAE | 0.41 | 0.46 | 0.43 | 0.87 | 0.45 | 11.2 |
| Deep SVDD | 0.26 | 0.41 | 0.32 | 0.69 | 0.29 | 15.8 |
| DIF | 0.53 | 0.69 | 0.59 | 0.94 | 0.67 | 13.1 |
| AE1SVM | 0.58 | 0.64 | 0.61 | 0.94 | 0.64 | 10.9 |
| LUNAR | 0.41 | 0.39 | 0.29 | 0.65 | 0.33 | 18.8 |

When the anomalies are genuinely rare and distributionally distinct, the unsupervised
detectors work: Isolation Forest reaches F1 ≈ 0.62 and PR-AUC ≈ 0.70. This is the
counterpoint to Credit Card Fraud (0.17% mixed-defect label) and Water Quality (61%
majority target).

### Synthetic dataset, mean recall by anomaly type

| Method | missing | duplicate | univ. outlier | multiv. outlier | drift | invalid fmt |
|---|---|---|---|---|---|---|
| Z-score | 0.00 | 0.00 | 0.93 | 0.00 | 0.00 | 0.24 |
| IQR | 0.05 | 0.04 | 0.99 | 0.04 | 0.25 | 1.00 |
| Great Expectations | 1.00 | 0.00 | 0.21 | 0.00 | 0.00 | 0.00 |
| Isolation Forest | 0.09 | 0.11 | 0.99 | 0.89 | 0.33 | 0.60 |
| LOF | 0.28 | 0.16 | 0.70 | 0.21 | 0.50 | 0.67 |
| One-Class SVM | 0.07 | 0.10 | 1.00 | 0.90 | 0.29 | 0.54 |
| ECOD | 0.10 | 0.13 | 0.68 | 0.52 | 0.26 | 0.36 |
| COPOD | 0.09 | 0.13 | 0.89 | 0.51 | 0.34 | 0.30 |
| HBOS | 0.00 | 0.00 | 0.90 | 0.00 | 0.00 | 0.32 |
| KNN | 0.09 | 0.10 | 1.00 | 0.39 | 0.41 | 0.81 |
| PCA | 0.10 | 0.12 | 1.00 | 0.48 | 0.23 | 0.58 |
| Autoencoder | 0.12 | 0.10 | 0.81 | 0.83 | 0.29 | 0.53 |
| VAE | 0.07 | 0.11 | 0.99 | 0.92 | 0.30 | 0.66 |
| Deep SVDD | 0.19 | 0.18 | 0.33 | 0.13 | 0.16 | 0.32 |
| DIF | 0.09 | 0.07 | 1.00 | 1.00 | 0.33 | 1.00 |
| AE1SVM | 0.09 | 0.10 | 0.99 | 0.78 | 0.27 | 0.61 |
| LUNAR | 0.44 | 0.39 | 1.00 | 0.63 | 0.65 | 0.90 |
| LSTM autoencoder | 0.08 | 0.09 | 0.97 | 0.68 | 0.25 | 0.53 |
| drift | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| transform dedup | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Per-type precision (clean rows as the only negatives) is also reported: Z-score has
precision 1.00 on its two columns, Great Expectations 0.94 on missing values, while
Isolation Forest catches 89% of multivariate outliers at only 0.23 precision. The
row-level `drift` detector scores 0 throughout the tested severity sweep; IQR,
Isolation Forest and One-Class SVM respond more as the shift grows. `make curves`
draws the precision-recall curves and the contamination sweep.

### Water Quality (3,276 rows, 61% "not potable")

Every ROC-AUC is 0.45–0.51 and every PR-AUC sits at the 0.61 base rate: the target class
is common, not rare, so the unsupervised detectors are at chance. A useful negative
result, and it exercises the pipeline on real missing data.

## Layout

The pipeline is split into reusable stages. The demo (`make pipeline`) and the benchmark (`make benchmark`) share them: the benchmark sends each detector through the same `detect()` stage, which is what lets it measure latency on the real pipeline path.

```
etl-anomaly-benchmark/
├── pyproject.toml            # metadata and deps (PEP 621)
├── environment.yml           # conda env
├── Makefile                  # shortcuts
├── src/
│   └── etl_benchmark/        # main package (src layout)
│       ├── __main__.py       # python -m etl_benchmark (demo)
│       ├── config.py         # paths and default thresholds
│       ├── logging_setup.py
│       ├── extract.py        # extract stage (read_csv)
│       ├── transform.py      # transform stage (dedup)
│       ├── load.py           # load stage (write_csv)
│       ├── pipeline.py       # composable stages + detect() + run_pipeline()
│       ├── split.py          # stratified train/val/test split
│       ├── registry.py       # detector registry + contamination handling
│       ├── datasets.py       # real-dataset specs (Credit Card, Cardio, Water Quality)
│       ├── synthetic.py      # per-anomaly-type dataset generator (severity knob)
│       └── quality/
│           ├── base.py       # Detector ABC (fit/predict/score)
│           ├── rules.py      # ZScoreDetector, IQRDetector
│           ├── gx.py         # GreatExpectationsDetector
│           ├── ml.py         # Isolation Forest, LOF, OC-SVM, ECOD, COPOD, HBOS, KNN, PCA (PyOD)
│           ├── deep.py       # VAE, Deep SVDD, DIF, AE1SVM, LUNAR (PyTorch, imported on fit)
│           ├── _torch_models.py # PyOD neural models with scores that depend on the fit rows only
│           ├── autoencoder.py # AutoencoderDetector (CPU reconstruction error, opt-in)
│           ├── drift.py      # TemporalDriftDetector (time-aware)
│           ├── window_drift.py # WindowDriftMonitor (chronological windows)
│           └── windows.py    # causal sliding windows for sequence models
├── experiments/
│   ├── run_benchmark.py           # real-dataset benchmark (--dataset)
│   ├── fetch_cardio.py            # download data/cardio.csv
│   ├── generate_synthetic.py      # write data/synthetic.csv
│   ├── run_synthetic_benchmark.py # multi-seed per-type + heatmap
│   ├── run_curves.py              # precision-recall curves + contamination sweep
│   └── run_severity.py            # detection-vs-severity curves
├── .github/workflows/ci.yml       # ruff + pytest on push / PR
├── slides/                   # living thesis presentation (HTML + PDF), rules in the repository instructions
├── tests/                    # pytest
├── data/                     # raw datasets (gitignored)
├── experiments/results/      # generated output (gitignored)
├── notebooks/                # exploratory analysis (later)
└── paper/                    # LaTeX IEEE paper + figures/
```

## Adding a detector

Every detector subclasses `etl_benchmark.quality.base.Detector` and implements `fit` and `predict`. The `score` method returns a continuous anomaly score (higher means more anomalous); it has a binary default, and you override it when a graded score is available so ROC-AUC and PR-AUC mean something.

```python
from etl_benchmark.quality.base import Detector


class MyDetector(Detector):
    name = "my_detector"

    def fit(self, df):
        # learn parameters
        return self

    def predict(self, df):
        # boolean Series, True where anomalous
        ...

    def score(self, df):  # optional
        # continuous score Series
        ...
```

Then add one line to `src/etl_benchmark/registry.py`, and both the demo and the benchmark pick it up. The PyOD wrappers (`quality/ml.py`) follow this interface through a small `PyODDetector` base; `AutoencoderDetector` reuses that base, and the LSTM-AE will do the same through `quality/windows.py`. A detector listed in the registry is checked by `tests/test_registry_contract.py`, so a new one cannot be added without passing the common fit / predict / score and leakage checks. Learned models stay opt-in (`DEEP_NAMES`) until `verification/deep_models.md` is satisfied. A PyOD neural model goes through `TorchDetector` in `quality/deep.py`, which fixes the seed and the arguments the protocol needs; if PyOD's scoring depends on the other scored rows (as it did for ECOD, COPOD, DIF and the VAE), a subclass in `quality/_torch_models.py` or a model in `quality/ml.py` fixes it, and the batch-independence contract test must pass.

## License

MIT (to add before any publication).
