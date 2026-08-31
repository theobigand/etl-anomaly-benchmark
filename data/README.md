# Datasets

## Credit Card Fraud (Kaggle)
- Source : https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
- Fichier attendu : `data/creditcard.csv`
- Taille : 284 807 lignes × 31 colonnes
- Anomalies : 492 fraudes (0.172%)
- Label : colonne `Class` (0 = normal, 1 = fraude)

## Synthétique par type d'anomalie
- Généré par : `python experiments/generate_synthetic.py` (déterministe)
- Fichier attendu : `data/synthetic.csv` (non versionné)
- Générateur : `src/etl_benchmark/synthetic.py`
- ~12 360 lignes × 12 colonnes, 6 types d'anomalies injectés à 3 % chacun
- Labels : `anomaly` (booléen) et `anomaly_type` (`clean` + 6 catégories)
- Colonnes d'analyse : voir `synthetic.FEATURE_COLUMNS` (l'`customer_id` et
  les colonnes de vérité terrain sont exclues)

## À venir
- `data/water_quality.csv` — UCI (été 2026)
