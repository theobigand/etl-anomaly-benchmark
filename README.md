# etl-anomaly-benchmark

![ci](https://github.com/theobigand/etl-anomaly-benchmark/actions/workflows/ci.yml/badge.svg)

A reproducible benchmark comparing three families of anomaly detectors for data quality (rule-based, classical ML, deep learning), each run inside a small ETL pipeline rather than in isolation. This is the code for my master's thesis at ESILV.

The question it tries to answer: does adding machine learning to an ETL pipeline actually improve anomaly detection over plain rules, and if so, for which kinds of anomalies? The planned original contribution is a per-anomaly-type comparison (a method-by-type heatmap on a controlled synthetic dataset), which existing benchmarks such as ADBench measure only in aggregate.

> Theo Bigand, ESILV M1/M2, 2026-2027

## Status

- [x] ETL pipeline as composable stages (extract, transform, detect, load)
- [x] Common `Detector` interface (fit / predict / score, PyOD-compatible)
- [x] Rule-based detectors: Z-score, IQR, Great Expectations
- [x] Classical ML detectors: Isolation Forest, LOF, One-Class SVM (via PyOD)
- [x] Synthetic dataset (6 anomaly types), per-type recall + precision, heatmap
- [x] Evaluation protocol: stratified 70/15/15 split, 5 seeds, mean ± std
- [x] ML contamination read from the train-set prevalence
- [x] Four datasets: Credit Card Fraud, Cardio (rare anomalies), Water Quality, synthetic
- [x] Time-aware `drift` detector; injection severity is a tunable multiplier
- [x] Precision-recall curves, contamination sweep, detection-vs-severity curves
- [x] CI (GitHub Actions: ruff + pytest)
- [ ] Autoencoder, LSTM-Autoencoder (M2)
- [ ] A windowed drift monitor; more imbalanced real datasets

## Install

```bash
conda env create -f environment.yml
conda activate etl-benchmark
```

`environment.yml` installs the package in editable mode (`pip install -e .`), so code changes are picked up without reinstalling.

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
make verify-deep       # focused mutation pilot
make verify-real       # inspect locally available real datasets
make clean             # remove generated artifacts
```

The demo runs Z-score by default and accepts any registered detector:

```bash
python -m etl_benchmark --detector iqr
python -m etl_benchmark --detector isolation_forest
```

Registered detectors: `zscore`, `iqr`, `great_expectations`, `isolation_forest`, `lof`,
`ocsvm`, plus `drift` (time-aware, opt-in, synthetic dataset only).

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

The [verification protocol](verification/README.md) records current coverage,
the mutation pilot and the checks required before a thesis release. The
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
| Great Expectations | 0.037 | 0.676 | 0.070 | 0.830 | 0.182 | 3.1 | 1.27 s |
| Isolation Forest | 0.202 | 0.206 | 0.203 | 0.934 | 0.120 | 0.2 | 1.73 s |

With contamination set to the prevalence, Isolation Forest flags only 0.17% of rows and
reaches a precision of 0.20 (the first usable operating point), at a recall of 0.21 and
with real seed variance (F1 = 0.20 ± 0.07). LOF and One-Class SVM do not scale to 284k
rows in the pipeline.

### Cardio (1,831 raw rows; 1,822 after deduplication, 9.6% anomalies)

| Detector | Prec | Rec | F1 | ROC-AUC | PR-AUC | Flag % |
|---|---|---|---|---|---|---|
| Z-score | 0.49 | 0.81 | 0.61 | 0.93 | 0.61 | 16.6 |
| Great Expectations | 0.50 | 0.21 | 0.29 | 0.59 | 0.19 | 4.6 |
| Isolation Forest | 0.64 | 0.61 | 0.62 | 0.94 | 0.70 | 9.9 |
| One-Class SVM | 0.56 | 0.61 | 0.58 | 0.94 | 0.63 | 10.7 |

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
│           ├── ml.py         # IsolationForest / LOF / OneClassSVM (PyOD)
│           └── drift.py      # TemporalDriftDetector (time-aware)
├── experiments/
│   ├── run_benchmark.py           # real-dataset benchmark (--dataset)
│   ├── fetch_cardio.py            # download data/cardio.csv
│   ├── generate_synthetic.py      # write data/synthetic.csv
│   ├── run_synthetic_benchmark.py # multi-seed per-type + heatmap
│   ├── run_curves.py              # precision-recall curves + contamination sweep
│   └── run_severity.py            # detection-vs-severity curves
├── .github/workflows/ci.yml       # ruff + pytest on push / PR
├── slides/                   # thesis progress presentation (HTML)
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

Then add one line to `src/etl_benchmark/registry.py`, and both the demo and the benchmark pick it up. The PyOD wrappers (`quality/ml.py`) follow this interface through a small `PyODDetector` base; the deep models (AE, LSTM-AE) will do the same.

## License

MIT (to add before any publication).
