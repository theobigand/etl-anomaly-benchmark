# Pilote d'évaluation chronologique (issue 51)

Ce document est écrit et versionné **avant** toute exécution du pilote. Aucun
score de détecteur n'a été calculé sur les partitions de validation et de test
au moment de la rédaction. Seuls des comptes (lignes, fraudes, dates) ont été
lus pour juger l'éligibilité des données.

## 1. Les trois jeux ont-ils un temps authentique ?

| Jeu | Colonne de temps | Verdict |
| --- | --- | --- |
| Cardio | aucune (21 variables standardisées, un enregistrement par ligne) | inéligible : l'ordre des lignes n'est pas un temps |
| Water Quality | aucune | inéligible |
| Credit Card | `Time`, secondes écoulées depuis la première transaction (documentation du jeu ULB/Kaggle), 0 à 172 792 s, soit deux jours | **éligible** |

Pour Credit Card, le temps est une origine relative (aucune date civile ne
figure dans le fichier) ; le fichier est trié par `Time`, avec de nombreuses
égalités (résolution d'une seconde : 160 215 doublons de date sur 284 807
lignes). La série présente un cycle quotidien net (peu de transactions entre
0 h et 7 h, puis entre 24 h et 31 h après l'origine). Les fraudes sont réparties
sur toute la période. Il n'existe **aucune vérité terrain de changement de
distribution** : le jeu fournit des étiquettes de fraude par ligne, pas
d'événements de dérive. Un second jeu n'est pas nécessaire pour ce pilote.
Aucune date n'est fabriquée : `Time` est converti en horodatage avec l'origine
conventionnelle 1970-01-01 UTC, déclarée comme relative.

Droits d'usage : voir `data/README.md` et le manifeste (ODbL, base de données
ouverte). Le fichier est celui des archives (sha256 du manifeste), jamais
redistribué.

## 2. Questions et hypothèses

Question : un protocole chronologique (apprendre sur le passé, évaluer sur le
futur) change-t-il la performance par ligne des détecteurs non supervisés du
benchmark principal, à données, variables et prétraitement identiques ?

- **H1 (primaire).** Pour chacun des quatre détecteurs de Credit Card
  (Z-score, IQR, Great Expectations, Isolation Forest), le PR-AUC de test sous
  partition chronologique est inférieur à celui sous partition stratifiée
  aléatoire (bras témoin, section 4). Sens prédit : plus bas, parce que la
  prévalence et la distribution futures s'écartent de celles du passé. Un écart
  est dit établi si l'intervalle de confiance à 95 % du PR-AUC chronologique
  exclut la moyenne stratifiée.
- **H2.** Le premier rang de PR-AUC reste le même détecteur dans les deux
  protocoles.
- **H3 (contrôle synthétique de dérive).** Sur le futur réel de test, avec un
  décalage de moyenne injecté à une date connue, le moniteur de fenêtres détecte
  un décalage de 2 écarts types en au plus deux fenêtres, sans fausse alerte
  avant le changement ; un décalage de 0,5 écart type peut rester non détecté,
  ce qui sera rapporté comme tel.

Hors périmètre, déclaré : la dérive naturelle de Credit Card n'a pas de vérité
terrain ; on ne la qualifie pas comme « détectée » ou « manquée ». Le moniteur
de fenêtres n'est évalué que sur le contrôle synthétique.

## 3. Cible et séparation des métriques

Deux problèmes distincts, jamais additionnés :

1. **Anomalie par ligne** : PR-AUC (principal), ROC-AUC, précision, rappel et
   F1 au seuil du benchmark (prévalence d'entraînement), nombre de lignes
   signalées.
2. **Dérive par fenêtre** : délai de détection (en fenêtres et en secondes),
   taux de fausses alertes avant le changement (`event_metrics`), événements
   manqués. Aucune de ces valeurs n'est comparée aux rappels par ligne.

## 4. Protocole

- Données : `data/creditcard.csv` (sha256 du manifeste), dédoublonnage exact
  conservant la première occurrence, comme dans le benchmark (283 726 lignes).
- Variables : V1 à V28 et Amount. **`Time` est retirée** des variables des deux
  bras (le benchmark principal la laissait dans les variables ; ce choix est une
  différence connue avec les tableaux publiés, qui ne sont pas modifiés). Les
  valeurs publiées servent de repère, pas de comparaison appariée.
- Bras chronologique : `chronological_split` sur l'horodatage, ratios 0,70 /
  0,15 / 0,15 du benchmark (`config.SPLIT_RATIOS`) ; les égalités de date restent
  dans une seule partition.
- Bras témoin : `stratified_split` aléatoire aux ratios et graines du
  benchmark, mêmes données, mêmes variables, mêmes détecteurs.
- Ajustement : train seul (statistiques, règles, imputation, échelle, seuil).
  Contamination de Isolation Forest = prévalence du train, comme dans le
  benchmark. Aucun hyperparamètre n'est réglé : réglages par défaut du registre.
  La validation chronologique ne sert à aucun réglage ; elle fixe uniquement le
  seuil du moniteur (voir plus bas) et décrit la dérive de prévalence.
- Détecteurs : `zscore`, `iqr`, `great_expectations`, `isolation_forest`
  (ceux de `DATASETS["credit_card"]`), via `detect(test, detecteur,
  fit_df=train)`.
- Graines : 42, 1, 2, 3, 4 (`config.BENCHMARK_SEEDS`). La graine ne pilote que
  la partition du bras témoin : Isolation Forest garde `random_state` égal à
  `config.RANDOM_SEED` (42) quelle que soit la graine de partition, comme dans le
  benchmark. Le bras chronologique est donc entièrement déterministe, et sa
  seule incertitude est celle du bootstrap par blocs. (Correction d'une phrase
  de la première version, avant toute exécution.)
- Incertitude : bootstrap par blocs temporels sur le test chronologique (blocs
  de 30 minutes, 1 000 rééchantillonnages, graine 42, intervalle percentile à
  95 %) ; bras témoin : moyenne et écart type sur les cinq graines. Le test
  chronologique compte peu de fraudes (de l'ordre de 70) : les intervalles
  seront larges et rapportés tels quels.
- Contrôle de dérive : moniteur `WindowDriftMonitor` sur les colonnes V1 à V5,
  fenêtres d'au moins 1 000 lignes, ajusté sur le train. **Seuil fixé avant
  le test** : le plus grand score de fenêtre observé sur la validation (aucune
  fausse alerte en validation par construction). Injection sur le test : les
  lignes d'horodatage supérieur ou égal à la médiane du test reçoivent un
  décalage additif de δ écarts types du train sur V1 à V5, pour δ dans
  {0,5 ; 1 ; 2}. Un témoin sans injection mesure les fausses alertes sur le test.
- Invariants testés : toute date d'ajustement précède toute date évaluée ; aucun
  recalage de la référence ; aucune fenêtre ne franchit une frontière de
  partition ; l'injection ne modifie que les lignes postérieures au changement.
- Budget de calcul : quelques minutes sur CPU de portable ; hors FAST et hors
  CI (script séparé, `research/temporal_pilot.py`, jamais lancé par `make
  verify-fast`).

## 5. Ce que le pilote ne prétend pas

Un seul jeu, deux jours de transactions, 70 fraudes environ en test : les
résultats sont un pilote, pas une loi. Les conclusions possibles sont une
direction et un ordre de grandeur de l'écart chronologique-stratifié ; elles
ne généralisent pas à d'autres jeux. Si H1 est infirmée, le résultat est
rapporté comme tel. Les résultats défavorables, y compris un détecteur qui ne
converge pas ou un seuil inutilisable, sont conservés dans l'archive.

## 6. Contribution attendue pour le mémoire

Une section méthodologique et un tableau court « chronologique contre
stratifié » placés à part de la comparaison principale, plus un contrôle de
délai de détection. Les résultats ne sont ajoutés au manuscrit qu'après
vérification du protocole et des preuves.
