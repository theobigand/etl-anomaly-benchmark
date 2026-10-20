# Résultats de l'étude de coût (issue 53)

Protocole : `cost_study.md` (commit `63b966f`, écrit avant toute mesure). Code :
`research/cost_study.py` (sha256 dans le résultat), tests : `research/tests/test_cost_study.py`.
Résultats et provenance : `evidence/cost_study/` (macOS 27.0.1 arm64, Apple M4, 10
coeurs, 16 Go, Python 3.11.17, numpy 2.4.6, pandas 3.0.6, scikit-learn 1.9.1, torch
2.14.1, empreinte scientifique `cecbed00`, empreinte de mesure `9cd603c6`, arbre propre,
jeu Credit Card sha256 `76274b69...`). Les 178 mesures ont été faites avec une charge
moyenne sous le seuil de contention (aucune mesure marquée `contended`, charge de départ
2,2). L'étude entière a duré environ douze minutes. `scaling.json` reste `LEGACY`, intact.

## Latence de détection (médiane de `detect_s`, 8 variables, mêmes lignes pour l'ajustement et l'évaluation)

| Méthode | 10 000 lignes | 100 000 | 300 000 | Exposant empirique | Surcoût de mémoire résidente au plus grand N |
| --- | --- | --- | --- | --- | --- |
| Z-score | 0,002 s | 0,013 s | 0,039 s | 0,64 | 70 Mo |
| IQR | 0,004 s | 0,029 s | 0,086 s | 0,70 | 116 Mo |
| Isolation Forest | 0,16 s | 1,09 s | 3,20 s | 0,72 | 140 Mo |
| Autoencodeur (MLP) | 1,49 s | 8,4 s | 12,7 s | 0,77 | 115 Mo |
| LSTM-autoencodeur (5 époques, 50 000 lignes d'ajustement au plus) | 1,10 s | 5,1 s | 7,3 s | 0,73 | 499 Mo |
| LOF | 0,73 s | 18,0 s | 133 s | 1,51 | 405 Mo |
| One-Class SVM | 5,6 s | dépassement de 300 s | non tenté | 1,99 (1 000 à 30 000) | 788 Mo à 30 000 |

Les exposants sont la pente de `log(temps)` sur `log(lignes)` des médianes, sur les tailles
réussies : aux petites tailles, des coûts fixes (démarrage, structures) aplatissent la
courbe, d'où des exposants inférieurs à 1 pour les méthodes dont le coût devient linéaire.
Ils ne se prolongent pas au-delà de la plus grande taille mesurée. One-Class SVM a dépassé
300 s à 100 000 lignes (une répétition, enregistrée `TIMEOUT`) et la taille 300 000 n'a pas
été tentée (`SKIPPED`, motif enregistré). Le plafond de 50 000 lignes d'ajustement et les 5
époques du LSTM sont une borne de budget : son coût ne croît pas avec N au-delà du plafond
pour l'ajustement, seul le scoring croît. À 30 000 lignes et 29 variables, Isolation Forest
passe de 0,38 s (8 variables) à 0,42 s, LOF de 3,2 s à 1,6 s, One-Class SVM de 43 s à 50 s, l'autoencodeur
de 1,1 s à 3,1 s : la dépendance aux variables est propre à chaque méthode.

## Étape de détection contre ETL complet (Credit Card réel, 284 807 lignes lues, 283 726 après dédoublonnage)

| Détecteur | Lecture | Transformation | Détection | Écriture | Total | Part de la détection | Pic mémoire |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Z-score | 0,61 s | 0,20 s | 0,13 s | 3,86 s | 4,8 s | 3 % | 0,73 à 0,76 Go |
| Isolation Forest | 0,62 s | 0,21 s | 3,7 s | 3,94 s | 8,5 s | 43 à 45 % | 0,94 à 0,98 Go |

(médianes de trois répétitions ; chaque processus est neuf.) L'écriture des deux CSV triés
domine pour le Z-score. La latence de l'étape de détection n'est donc pas la latence d'un
ETL complet, et l'écart dépend du détecteur.

## Limites

Une machine, partagée avec d'autres tâches (non contendue au sens du seuil du protocole mais
non isolée) ; données synthétiques gaussiennes, sans la structure de Credit Card ; mémoire :
`ru_maxrss` donne un pic de processus, et le surcoût est une valeur plancher (un pic antérieur
plus haut le masque, d'où des différences nulles aux petites tailles) ; une répétition de
One-Class SVM à 100 000 lignes suffit à déclarer le dépassement et à arrêter la méthode ;
pas de seuil de temps dans la CI.
