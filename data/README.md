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

## Water Quality
- Source : https://raw.githubusercontent.com/MainakRepositor/Datasets/master/water_potability.csv
  (miroir du jeu "Water Potability", proche du UCI Water Quality)
- Fichier attendu : `data/water_quality.csv` (non versionné)
- 3 276 lignes × 10 colonnes, 9 features numériques
- Label : colonne `Potability` (1 = potable, 0 = non potable)
- Anomalie retenue : `Potability == 0` (non potable), 61 % des lignes
- Valeurs manquantes réelles : `ph` (491), `Sulfate` (781), `Trihalomethanes` (162)
- Régime différent des deux autres : la classe cible est fréquente, pas rare.
  Sert à tester les détecteurs hors de leur domaine d'emploi, sur des nulls réels.

## À venir
- rien de bloquant
