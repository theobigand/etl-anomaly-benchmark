# etl-anomaly-benchmark

Pipeline ETL et benchmark reproductible comparant trois familles de détection d'anomalies — **règles statistiques**, **ML classique** et **deep learning** — pour la qualité des données.

> Master Thesis · Theo Bigand · ESILV M1/M2 · 2026-2027

## État actuel

- [x] Pipeline ETL en étapes composables (extract → transform → detect → load)
- [x] Interface `Detector` unifiée (fit / predict / score, compatible PyOD)
- [x] Détecteurs à base de règles : Z-score, IQR, Great Expectations
- [x] Benchmark reproductible sur Credit Card Fraud (métriques + latence)
- [ ] Isolation Forest, LOF, One-Class SVM via PyOD
- [ ] Dataset Faker synthétique (6 types d'anomalies) + heatmap méthode × type
- [ ] Autoencoder, LSTM-Autoencoder (M2)

## Installation (conda)

```bash
conda env create -f environment.yml
conda activate etl-benchmark
```

Le package est installé en mode éditable (`pip install -e .`) via `environment.yml`, donc les modifications sont prises en compte sans réinstallation.

## Télécharger Credit Card Fraud

Dataset non inclus (~150 Mo) :

1. https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
2. Placer `creditcard.csv` dans `data/`

## Commandes

```bash
make pipeline    # démo ETL : un détecteur à travers le pipeline, écrit les CSV triés
make benchmark   # compare tous les détecteurs, affiche et sauvegarde les métriques
make run         # les deux (pipeline puis benchmark)
make test        # pytest
make lint        # ruff check + format check
make clean       # supprime les artefacts générés
```

La démo tourne avec Z-score par défaut, mais accepte n'importe quel détecteur du registre :

```bash
python -m etl_benchmark --detector iqr
python -m etl_benchmark --detector great_expectations
```

Le benchmark accepte un mode rapide : `python experiments/run_benchmark.py --limit 20000`.

## Résultats actuels (règles seules)

Credit Card Fraud complet, 283 726 lignes après déduplication, 0,167 % de fraudes. La latence est le temps fit+predict+score dans le pipeline.

| Détecteur | Prec | Rec | F1 | ROC-AUC | PR-AUC | Flag % | Latence |
|---|---|---|---|---|---|---|---|
| Z-score | 0.011 | 0.899 | 0.022 | 0.944 | 0.090 | 13.4 | 0.2 s |
| IQR | 0.003 | 0.968 | 0.007 | 0.922 | 0.020 | 48.6 | 0.6 s |
| Great Expectations | 0.039 | 0.710 | 0.075 | 0.848 | 0.206 | 3.0 | 13.2 s |

Sur des données fortement déséquilibrées, PR-AUC est plus informatif que ROC-AUC. Aucune règle n'atteint une précision utilisable : c'est le trou que le ML doit combler.

## Architecture

Le pipeline est découpé en étapes réutilisables. La démo (`make pipeline`) et le benchmark (`make benchmark`) partagent les mêmes étapes : le benchmark fait passer chaque détecteur par l'étape `detect()`, ce qui mesure la latence sur le vrai chemin du pipeline.

```
etl-anomaly-benchmark/
├── pyproject.toml            # métadonnées & deps (PEP 621)
├── environment.yml           # env conda
├── Makefile                  # raccourcis
├── src/
│   └── etl_benchmark/        # package principal (src-layout)
│       ├── __main__.py       # python -m etl_benchmark (démo)
│       ├── config.py         # chemins & seuils par défaut
│       ├── logging_setup.py
│       ├── extract.py        # étape Extract (read_csv)
│       ├── transform.py      # étape Transform (dédup)
│       ├── load.py           # étape Load (write_csv)
│       ├── pipeline.py       # étapes composables + detect() + run_pipeline()
│       ├── registry.py       # registre des détecteurs (nom -> instance)
│       └── quality/
│           ├── base.py       # Detector (ABC : fit/predict/score)
│           ├── rules.py      # ZScoreDetector, IQRDetector
│           └── gx.py         # GreatExpectationsDetector
├── experiments/
│   └── run_benchmark.py      # le benchmark
├── tests/                    # pytest
├── data/                     # datasets bruts (gitignored)
├── experiments/results/      # sorties générées (gitignored)
├── notebooks/                # analyses exploratoires (à venir)
└── paper/                    # papier LaTeX IEEE
```

## Ajouter un nouveau détecteur

Tous les détecteurs héritent de `etl_benchmark.quality.base.Detector` et implémentent `fit` + `predict`. La méthode `score` (score continu, plus élevé = plus anormal) a une valeur par défaut binaire ; on la surcharge quand on peut produire un score gradué, ce qui rend ROC-AUC / PR-AUC pertinents.

```python
from etl_benchmark.quality.base import Detector

class MyDetector(Detector):
    name = "my_detector"

    def fit(self, df):
        # ... apprend les paramètres ...
        return self

    def predict(self, df):
        # retourne une Series booléenne (True = anormal)
        ...

    def score(self, df):          # optionnel
        # retourne une Series de scores continus
        ...
```

Il suffit ensuite d'ajouter le détecteur à `build_detectors()` dans `experiments/run_benchmark.py`. Les wrappers PyOD (IF, LOF, OC-SVM) et deep (AE, LSTM-AE) suivront cette même interface.

## Licence

MIT (à ajouter avant publication).
