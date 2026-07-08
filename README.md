# etl-anomaly-benchmark

Pipeline ETL open-source et benchmark reproductible comparant trois familles de détection d'anomalies — **règles statistiques**, **ML classique** et **deep learning** — pour la qualité des données.

> Master Thesis · Theo Bigand · ESILV M1/M2 · 2026-2027

## État actuel

- ✅ Pipeline ETL minimal (Extract → Transform → Quality → Load)
- ✅ Interface `Detector` unifiée (ABC compatible PyOD)
- ✅ Baseline Z-score fonctionnelle + tests
- ⏳ IQR + Great Expectations (séance 2, mai 2026)
- ⏳ Isolation Forest, LOF, One-Class SVM via PyOD (juin 2026)
- ⏳ Dataset Faker synthétique (6 types d'anomalies)
- ⏳ Autoencoder, LSTM-Autoencoder (M2)

## Installation (conda)

```bash
conda env create -f environment.yml
conda activate etl-benchmark
```

Le package est installé en mode éditable (`pip install -e .`) via `environment.yml`, donc tes modifications sont prises en compte sans réinstallation.

## Télécharger Credit Card Fraud

Dataset non inclus (~150 Mo) :

1. https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
2. Place `creditcard.csv` dans `data/`

## Commandes utiles

```bash
make run       # python -m etl_benchmark
make test      # pytest
make lint      # ruff check + format check
make clean     # supprime artefacts
```

## Structure

```
etl-anomaly-benchmark/
├── pyproject.toml            # Metadata & deps (PEP 621)
├── environment.yml           # Env conda
├── Makefile                  # Raccourcis
├── src/
│   └── etl_benchmark/        # Package principal (src-layout)
│       ├── __init__.py
│       ├── __main__.py       # python -m etl_benchmark
│       ├── config.py         # Chemins & seuils par défaut
│       ├── logging_setup.py
│       ├── extract.py        # Stage Extract
│       ├── transform.py      # Stage Transform
│       ├── load.py           # Stage Load
│       ├── pipeline.py       # Orchestrateur
│       └── quality/
│           ├── base.py       # Detector (ABC)
│           └── rules.py      # ZScoreDetector (+IQR, GX à venir)
├── tests/                    # pytest
├── data/                     # Datasets bruts (gitignored)
├── experiments/results/      # Sorties benchmark
├── notebooks/                # Analyses exploratoires
└── paper/                    # Papier LaTeX IEEE
```

## Ajouter un nouveau détecteur

Tous les détecteurs héritent de `etl_benchmark.quality.base.Detector` et implémentent `fit` + `predict`. Exemple minimal :

```python
from etl_benchmark.quality.base import Detector

class MyDetector(Detector):
    name = "my_detector"

    def fit(self, df):
        # ... learn parameters ...
        return self

    def predict(self, df):
        # return boolean Series
        ...
```

Les wrappers PyOD (IF, LOF, OC-SVM) et Keras/PyTorch (AE, LSTM-AE) suivront cette même interface.

## Licence

MIT (à ajouter avant publication).
