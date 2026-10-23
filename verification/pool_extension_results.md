# Resultats de l'extension de toutes les etudes au pool

Protocole : `pool_extension.md` (ecrit et archive avant les resultats). Code :
`research/pool_full.py`, `pool_typed.py` (eligibility, reference, severity), `pool_etl.py`,
`pool_chrono.py`, `time_scan.py`, `pool_extension_summary.py`, `pool_extension_paper.py`. Preuves :
`evidence/pool_extension/`. Le papier (sous-section "Every study on the whole pool") est genere
depuis ces archives.

## Hypotheses

| | Enonce | Resultat | Valeurs |
| --- | --- | --- | --- |
| P1 | seuil sans etiquette : F1 median plus bas pour au moins 12 detecteurs sur 17 | soutenue | 14 sur 17 ; les trois regles ne changent pas |
| P2 | classement par precision moyenne = classement par PR-AUC (Spearman >= 0,99) | non soutenue | 0,8995 |
| P3 | rappel multivarie median plus haut a la severite 4 qu'a 0,5 pour les 17 detecteurs | non soutenue | 13 sur 17 ; Z-score, Great Expectations, HBOS a 0, LOF 0,33 contre 0,32 |
| P4 | pipeline : detection > 30 % avec Isolation Forest et < 10 % avec le Z-score au-dela de 50 000 lignes | soutenue | 14 jeux ; 62 % et 4 % |
| P5 | PR-AUC chronologique plus bas que le stratifie pour au moins deux tiers des couples | non soutenue | 31 couples sur 64 |
| P6 | aucun fichier du pool ne differe du manifeste | soutenue | 152 sur 152 |

## Couverture et ecarts

- Passage unique : 100 problemes etiquetes sur 100, 17 detecteurs, 0 echec.
- Injection typee et severite : 58 tables eligibles sur 152 (42 UCI, 16 ADBench) ; les 94 autres sont
  listees avec leur raison dans `typed/eligibility.json` (colonnes continues ou lignes insuffisantes).
- Pipeline ETL : 152 jeux, 304 mesures, 290 reussies. 14 echecs sur 7 jeux UCI : table sans colonne
  numerique, colonne lue comme du texte a cause d'en-tetes parasites, colonne d'entrainement vide.
- Chronologie : 5 jeux etiquetes avec une variable de temps reelle (Credit Card, Bank Marketing,
  Occupancy Detection, Online Shoppers, Room Occupancy) ; Room Occupancy est exclu (0 anomalie de
  test). 11 tables UCI avec une date n'ont pas d'etiquette : etude indefinie. ADBench n'a pas de colonne
  de temps.

## Ce que les chiffres montrent

- Le seuil de 0,02 sans etiquette abaisse le F1 median de 14 detecteurs ; le classement par courbes
  bouge par rapport au PR-AUC median, car plusieurs medianes sont a un centieme pres.
- Isolation Forest : le F1 median monte jusqu'a la plus grande contamination (0,2, le double de la
  prevalence mediane 0,10) ; la precision reste a 0,14-0,16 des 0,05 : les scores sont faibles sur
  ces etiquettes, pas le seuil.
- Severite : LUNAR est le plus haut a toutes les severites (0,60 a 0,68) ; les detecteurs par colonne
  (Z-score, Great Expectations, HBOS) restent a 0 sur les valeurs aberrantes multivariees.
- Chronologie : Bank Marketing (prevalence de 5,8 % a 39,3 %) explique l'echec de P5 : aucun detecteur n'y
  perd de PR-AUC.

## Limites

Les temps du passage unique et du pipeline ont ete mesures avec plusieurs processus en parallele ; ce
sont des ordres de grandeur (l'etude de cout, machine au repos, donne les temps isoles). Etiquettes UCI
issues d'une regle, 19 sources presentes deux fois, reglages par defaut de PyOD, trois graines pour la
severite, cinq autres ; les intervalles sont indicatifs.
