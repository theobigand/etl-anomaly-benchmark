# Résultats du pilote chronologique (issue 51)

Protocole : `temporal_pilot.md` (commit `147448f`, écrit avant toute exécution ;
une phrase sur les graines a été corrigée avant exécution, commit suivant).
Code : `research/temporal_pilot.py` (sha256 dans le résultat) ; tests des
invariants : `tests/test_temporal_pilot.py`. Résultats et enregistrement de
provenance : `evidence/temporal_pilot/` (jeu Credit Card sha256
`76274b69...`, macOS arm64, Python 3.11.17, 10 coeurs, empreinte scientifique
`cecbed00`, arbre propre). Une seconde exécution complète a donné des résultats
identiques (hors provenance) : le pilote est déterministe.

Partitions chronologiques (0,70/0,15/0,15, dates égales groupées) : train
198 609 lignes, 366 fraudes (0,184 %), jusqu'à 132 906 s ; validation 42 560,
55 (0,129 %) ; test 42 557, 52 (0,122 %), de 151 321 s à 172 792 s.

## PR-AUC par ligne (test)

| Détecteur | Stratifié (5 graines) | Chronologique [IC 95 % par blocs] | ROC chron. | Signalées |
| --- | --- | --- | --- | --- |
| Z-score | 0,078 ± 0,015 | 0,048 [0,020 ; 0,087] | 0,935 | 12,8 % |
| IQR | 0,018 ± 0,003 | 0,013 [0,007 ; 0,023] | 0,917 | 47,1 % |
| Great Expectations | 0,183 ± 0,047 | 0,045 [0,013 ; 0,088] | 0,758 | 3,5 % |
| Isolation Forest | 0,110 ± 0,039 | 0,035 [0,016 ; 0,066] | 0,936 | 0,08 % |

## Verdict sur les hypothèses pré-enregistrées

- **H1 (PR-AUC chronologique plus bas, intervalle excluant la moyenne
  stratifiée, pour chaque détecteur) : partiellement soutenue.** Le sens prédit
  est observé pour les quatre détecteurs ; l'intervalle exclut la moyenne
  stratifiée pour Great Expectations et Isolation Forest seulement. Pour le
  Z-score (0,078 dans l'intervalle 0,020-0,087) et l'IQR (0,018 dans
  0,007-0,023), l'écart n'est pas établi avec 52 fraudes en test.
- **H2 (même détecteur en tête) : infirmée sur les estimations ponctuelles.**
  Great Expectations mène le bras stratifié ; le Z-score a la plus haute
  estimation chronologique (0,048 contre 0,045), avec des intervalles qui se
  recouvrent largement : le changement de rang n'est pas établi non plus.
- **H3 (contrôle synthétique de dérive) : soutenue.** Seuil 0,912 (plus grand
  score de fenêtre en validation, 42 fenêtres, aucune alerte en validation).
  Décalages de 1 et 2 écarts types détectés à la deuxième fenêtre après le
  changement (573 s) ; décalage de 0,5 non détecté, comme prévu ; témoin sans
  décalage sans alerte ; aucune fausse alerte avant le changement (22 fenêtres).

## Portée statistique du critère de H1

Le critère « l'intervalle chronologique exclut la moyenne stratifiée » a été
fixé à l'avance comme critère exploratoire. Ce n'est ni un intervalle de
confiance ni un test d'hypothèse sur la différence entre les deux protocoles :
le bootstrap par blocs ne mesure que l'incertitude du bras chronologique (52
fraudes, une seule période), la moyenne stratifiée est elle-même incertaine
(écart type sur cinq graines, jusqu'à 0,047) et n'est pas traitée comme un
paramètre connu. De plus, la part de fraudes change entre les partitions
(0,184 % en train, 0,122 % en test, contre environ 0,17 % sur l'ensemble pour
le bras stratifié) : une partie de l'écart peut venir de la seule prévalence,
puisque le PR-AUC d'un détecteur sans pouvoir dépend de la prévalence. Le pilote
ne sépare pas l'effet du temps de l'effet de la prévalence. Les hypothèses
ci-dessus et leurs verdicts restent ceux du protocole.

## Identité de l'implémentation du pilote

`research/` est hors de l'empreinte scientifique (`src/` et `experiments/*.py`,
recette 2) : l'empreinte `cecbed00` de l'enregistrement décrit le code des
détecteurs, des partitions et du moniteur utilisé, pas le script du pilote.
L'identité du script est portée par `script_sha256` dans les réglages de
l'enregistrement, avec `source_revision` (commit où le script a cette empreinte,
arbre propre), `dataset_sha256` (égal au manifeste) et `output_sha256`.
`tests/test_temporal_pilot.py::test_the_archived_pilot_record_identifies_this_implementation`
vérifie ces quatre liens et que le script actuel est celui de l'archive. La
recette d'empreinte n'a pas été étendue.

## Constat non prévu

Isolation Forest garde un ROC-AUC élevé (0,936) mais signale 0,08 % des lignes
futures et aucune des 52 fraudes : le seuil fixé sur les scores d'entraînement
(prévalence d'entraînement) ne se transfère pas à la période suivante. Le
classement des scores survit au passage du temps ; le point de fonctionnement
non. C'est un constat à confirmer, pas une loi (un jeu, deux jours, 52
positifs).

## Limites

Un seul jeu éligible ; origine du temps relative ; 52 fraudes en test donc
intervalles larges ; variables sans `Time`, différentes de celles des tableaux
du benchmark principal (le bras stratifié du pilote est le témoin apparié, les
valeurs publiées servent de repère) ; la dérive naturelle de Credit Card n'a
pas de vérité terrain et n'est pas évaluée ; le contrôle de dérive est
synthétique. Le coût de calcul du pilote est de quelques minutes sur CPU.
