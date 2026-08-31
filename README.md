# etl-anomaly-benchmark

A reproducible benchmark comparing three families of anomaly detectors for data quality (rule-based, classical ML, deep learning), each run inside a small ETL pipeline rather than in isolation. This is the code for my master's thesis at ESILV.

The question it tries to answer: does adding machine learning to an ETL pipeline actually improve anomaly detection over plain rules, and if so, for which kinds of anomalies? The planned original contribution is a per-anomaly-type comparison (a method-by-type heatmap on a controlled synthetic dataset), which existing benchmarks such as ADBench measure only in aggregate.

> Theo Bigand, ESILV M1/M2, 2026-2027

## Status

- [x] ETL pipeline as composable stages (extract, transform, detect, load)
- [x] Common `Detector` interface (fit / predict / score, PyOD-compatible)
- [x] Rule-based detectors: Z-score, IQR, Great Expectations
- [x] Reproducible benchmark on Credit Card Fraud (metrics + latency)
- [x] Classical ML detectors: Isolation Forest, LOF, One-Class SVM (via PyOD)
- [x] Synthetic dataset (6 anomaly types) and the method-by-type heatmap
- [ ] Autoencoder, LSTM-Autoencoder (M2)
- [ ] Third dataset (UCI Water Quality)

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

The synthetic per-anomaly-type dataset is generated locally (deterministic, not committed):

```bash
make synthetic   # writes data/synthetic.csv from src/etl_benchmark/synthetic.py
```

## Usage

```bash
make pipeline    # ETL demo: run one detector through the pipeline, write the sorted CSVs
make benchmark   # score every detector on Credit Card Fraud, print and save the metrics
make synthetic   # generate the per-anomaly-type dataset
make heatmap     # method-by-anomaly-type benchmark, renders paper/figures/heatmap_synthetic.png
make run         # pipeline then benchmark
make test        # pytest
make lint        # ruff check + format check
make clean       # remove generated artifacts
```

The demo runs Z-score by default and accepts any registered detector:

```bash
python -m etl_benchmark --detector iqr
python -m etl_benchmark --detector isolation_forest
```

Registered detectors: `zscore`, `iqr`, `great_expectations`, `isolation_forest`, `lof`, `ocsvm`.

The benchmark has a quick mode for iterating (`--limit 20000`), and can fit the
detectors on a sample while still scoring every row, which keeps the quadratic
One-Class SVM tractable on the full dataset:

```bash
python experiments/run_benchmark.py --fit-sample 20000
```

## Current results

### Credit Card Fraud (full dataset, 283,726 rows after dedup, 0.167% fraud)

Latency is the in-pipeline fit+predict+score time. Isolation Forest is fitted on a
20,000-row sample and scored on every row.

| Detector | Prec | Rec | F1 | ROC-AUC | PR-AUC | Flag % | Latency |
|---|---|---|---|---|---|---|---|
| Z-score | 0.011 | 0.899 | 0.022 | 0.944 | 0.090 | 13.4 | 0.2 s |
| IQR | 0.003 | 0.968 | 0.007 | 0.922 | 0.020 | 48.6 | 0.6 s |
| Great Expectations | 0.039 | 0.710 | 0.075 | 0.848 | 0.206 | 3.0 | 13.2 s |
| Isolation Forest | 0.014 | 0.882 | 0.028 | 0.949 | 0.157 | 10.4 | 3.2 s |

LOF (superlinear scoring) and One-Class SVM (quadratic training) do not run at this
scale in the pipeline, so they are compared with the rest on the synthetic dataset.
No method reaches a precision you could put in production on a class this imbalanced.

### Synthetic dataset, detection rate by anomaly type

Full run: `make heatmap`. Renders `paper/figures/heatmap_synthetic.png`.

| Method | missing | duplicate | univ. outlier | multiv. outlier | drift | invalid fmt |
|---|---|---|---|---|---|---|
| Z-score | 0.00 | 0.00 | 0.91 | 0.00 | 0.00 | 0.21 |
| IQR | 0.05 | 0.06 | 0.99 | 0.05 | 0.26 | 1.00 |
| Great Expectations | 1.00 | 0.00 | 0.22 | 0.00 | 0.00 | 0.21 |
| Isolation Forest | 0.02 | 0.06 | 0.95 | 0.41 | 0.21 | 0.40 |
| LOF | 0.14 | 0.03 | 0.39 | 0.10 | 0.35 | 0.61 |
| One-Class SVM | 0.02 | 0.05 | 0.99 | 0.31 | 0.22 | 0.42 |
| transform dedup | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Aggregate metrics make the families look interchangeable; this view shows each has a
narrow competence. Missing values go to declarative rules, single-column outliers to
any statistical rule, implausible combinations to Isolation Forest or One-Class SVM,
duplicates to the transform stage. Temporal drift is caught well by none of them yet.

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
│       ├── registry.py       # detector registry (name -> instance)
│       ├── synthetic.py      # per-anomaly-type dataset generator
│       └── quality/
│           ├── base.py       # Detector ABC (fit/predict/score)
│           ├── rules.py      # ZScoreDetector, IQRDetector
│           ├── gx.py         # GreatExpectationsDetector
│           └── ml.py         # IsolationForest / LOF / OneClassSVM (PyOD)
├── experiments/
│   ├── run_benchmark.py           # Credit Card Fraud benchmark
│   ├── generate_synthetic.py      # write data/synthetic.csv
│   └── run_synthetic_benchmark.py # method-by-anomaly-type + heatmap
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

    def score(self, df):          # optional
        # continuous score Series
        ...
```

Then add one line to `src/etl_benchmark/registry.py`, and both the demo and the benchmark pick it up. The PyOD wrappers (`quality/ml.py`) follow this interface through a small `PyODDetector` base; the deep models (AE, LSTM-AE) will do the same.

## License

MIT (to add before any publication).
