# Datasets

## Credit Card Fraud (Kaggle)
- Source : https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
- La fiche Kaggle indique « Open Database / Database Contents ». La révision
  exacte téléchargée n'a pas été conservée ; la copie locale est identifiée
  par le manifeste et reste hors dépôt.
- Fichier attendu : `data/creditcard.csv`
- Taille : 284 807 lignes × 31 colonnes
- Anomalies : 492 fraudes (0.172%)
- Label : colonne `Class` (0 = normal, 1 = fraude)
- Après suppression des doublons exacts : 283 726 lignes, 473 fraudes.

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
  (miroir du jeu « Water Quality » d'Aditya Kadiwal sur Kaggle). La copie
  locale est identique, octet par octet, au miroir vérifié le 13 octobre
  2026. La fiche du jeu original indique CC0 ; le miroir ne précise pas
  séparément ses conditions. Ce jeu ne doit pas être présenté comme une
  version du dépôt UCI.
- Fichier attendu : `data/water_quality.csv` (non versionné)
- 3 276 lignes × 10 colonnes, 9 features numériques
- Label : colonne `Potability` (1 = potable, 0 = non potable)
- Anomalie retenue : `Potability == 0` (non potable), 61 % des lignes
- Valeurs manquantes réelles : `ph` (491), `Sulfate` (781), `Trihalomethanes` (162)
- La transformation conserve 3 276 lignes, dont 1 998 positives.
- Régime différent des deux autres : la classe cible est fréquente, pas rare.
  Sert à tester les détecteurs hors de leur domaine d'emploi, sur des nulls réels.

## Cardio (anomalies rares, régime cible)
- Source : `experiments/fetch_cardio.py` (télécharge un `.npz` cardiotocographie)
- Source exacte : `adbench/datasets/Classical/6_cardio.npz` dans ADBench.
  La conversion du fichier source vérifié le 13 octobre 2026 reproduit
  exactement le CSV local. ADBench publie son dépôt sous BSD-2-Clause ;
  les droits du jeu Cardio sous-jacent ne sont pas précisés séparément.
- Fichier attendu : `data/cardio.csv` (non versionné)
- 1 831 lignes × 22 colonnes, 21 features déjà standardisées
- Label : colonne `label` (1 = anomalie), 9.6 % d'anomalies
- Le dataset vraiment déséquilibré du benchmark : le régime pour lequel les
  détecteurs non supervisés sont conçus.
- Après suppression des doublons exacts : 1 822 lignes, 175 anomalies.

Les sommes de contrôle des copies utilisées pour les expériences sont dans
`verification/evidence/manifest.json`. `make verify-real` compare les fichiers
présents sur la machine à ce manifeste. La révision exacte du téléchargement
Credit Card et les droits sous-jacents de Cardio restent à établir avant une
redistribution des données brutes ; celles-ci ne sont pas archivées ici.

## À venir
- rien de bloquant
