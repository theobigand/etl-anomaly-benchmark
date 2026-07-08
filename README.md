# etl-anomaly-benchmark

A reproducible benchmark comparing three families of anomaly detectors for data quality (rule-based, classical ML, deep learning), each run inside a small ETL pipeline rather than in isolation. This is the code for my master's thesis at ESILV.

The question it tries to answer: does adding machine learning to an ETL pipeline actually improve anomaly detection over plain rules, and if so, for which kinds of anomalies? The planned original contribution is a per-anomaly-type comparison (a method-by-type heatmap on a controlled synthetic dataset), which existing benchmarks such as ADBench measure only in aggregate.

> Theo Bigand, ESILV M1/M2, 2026-2027

## Status

- [x] ETL pipeline as composable stages (extract, transform, detect, load)
- [x] Common `Detector` interface (fit / predict / score, PyOD-compatible)
- [x] Rule-based detectors: Z-score, IQR, Great Expectations
- [x] Reproducible benchmark on Credit Card Fraud (metrics + latency)
- [ ] Isolation Forest, LOF, One-Class SVM through PyOD
- [ ] Synthetic Faker dataset (6 anomaly types) and the method-by-type heatmap
- [ ] Autoencoder, LSTM-Autoencoder (M2)

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

## Usage

```bash
make pipeline    # ETL demo: run one detector through the pipeline, write the sorted CSVs
make benchmark   # score every detector, print and save the metrics
make run         # both (pipeline then benchmark)
make test        # pytest
make lint        # ruff check + format check
make clean       # remove generated artifacts
```

The demo runs Z-score by default and accepts any registered detector:

```bash
python -m etl_benchmark --detector iqr
python -m etl_benchmark --detector great_expectations
```

The benchmark has a quick mode for iterating: `python experiments/run_benchmark.py --limit 20000`.

## Current results (rules only)

Full Credit Card Fraud dataset, 283,726 rows after dropping duplicates, 0.167% fraud. Latency is the in-pipeline fit+predict+score time.

| Detector | Prec | Rec | F1 | ROC-AUC | PR-AUC | Flag % | Latency |
|---|---|---|---|---|---|---|---|
| Z-score | 0.011 | 0.899 | 0.022 | 0.944 | 0.090 | 13.4 | 0.2 s |
| IQR | 0.003 | 0.968 | 0.007 | 0.922 | 0.020 | 48.6 | 0.6 s |
| Great Expectations | 0.039 | 0.710 | 0.075 | 0.848 | 0.206 | 3.0 | 13.2 s |

On a class this imbalanced, PR-AUC says more than ROC-AUC (both are reported; PR-AUC is not comparable across datasets, ROC-AUC is). None of the rules reach a precision you could put in production. That gap is what the ML detectors are meant to close.

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
│       └── quality/
│           ├── base.py       # Detector ABC (fit/predict/score)
│           ├── rules.py      # ZScoreDetector, IQRDetector
│           └── gx.py         # GreatExpectationsDetector
├── experiments/
│   └── run_benchmark.py      # the benchmark
├── tests/                    # pytest
├── data/                     # raw datasets (gitignored)
├── experiments/results/      # generated output (gitignored)
├── notebooks/                # exploratory analysis (later)
└── paper/                    # LaTeX IEEE paper
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

Then add one line to `src/etl_benchmark/registry.py`, and both the demo and the benchmark pick it up. The PyOD wrappers (IF, LOF, OC-SVM) and the deep models (AE, LSTM-AE) will follow the same interface.

## License

MIT (to add before any publication).
