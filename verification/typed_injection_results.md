# Injection typee sur donnees reelles : resultats (issue #65)

Protocole et hypotheses : `typed_injection.md`, ecrits avant tout resultat et inchanges depuis.
Donnees : 42 jeux UCI du pool de l'issue #66 (porteurs, au moins 3 000 lignes et 4 colonnes
continues apres normalisation, classe normale seule pour les jeux etiquetes). Cinq graines,
sept detecteurs plus la regle de deduplication, rappel par type sur la partition de test.
Resultats bruts : `evidence/typed_injection/runs/` (un fichier par jeu, avec l'empreinte du fichier
source), synthese : `evidence/typed_injection/typed_results.{md,json}`, figures `typed_pooled.png`
et `typed_panels.png`. Code : `research/injection.py`, `typed_benchmark.py`, `typed_run.py`,
`typed_summary.py`.

## Verdict sur les hypotheses

| Hypothese | Verdict | Valeurs |
|---|---|---|
| H1 specialisation | non confirmee | great_expectations detecte 100 % des valeurs manquantes sur chaque jeu (conforme). Le rappel de la deduplication est 1,00, mais iqr atteint au moins 0,9 sur certains jeux (0,98 au maximum) parce qu'il signale beaucoup de lignes. Univarie : iqr 1,00, ocsvm 0,75, lof 0,68, isolation_forest 0,61, zscore 0,00 (voir masquage). |
| H2 multivarie | non confirmee | rappel median isolation_forest 0,37, ocsvm 0,17, iqr 0,39, zscore 0,00 ; l'ecart exige (0,4 en faveur du ML) est de -0,22. |
| H3 derive | non confirmee | iqr 0,64, isolation_forest 0,45, lof 0,34, ocsvm 0,31. Le detecteur de derive ne signale aucune ligne (0,00), comme sur le jeu synthetique. |
| H4 stabilite | confirmee de peu | correlation de rang moyenne 0,83 ; par type : manquante 0,82, invalide 0,77, doublon 0,75, aberrante multivariee 0,74, derive 0,70. Les deux types difficiles sont sous les trois types structurels, mais l'ecart est faible (0,74 contre 0,75). |
| H5 dependance au jeu | confirmee | correlation de rang entre le nombre de colonnes continues et le rappel de isolation_forest sur l'aberrante univariee : -0,96 sur 42 jeux. |

## Ce que les resultats disent

- Les deux types de structure gardent leur specialiste : valeurs manquantes pour great_expectations,
  doublons pour la regle de deduplication (cette regle signale aussi l'original de chaque copie,
  soit 3,5 % de fausses alarmes).
- Le rappel seul est trompeur. iqr obtient le meilleur rappel sur plusieurs types, mais sa
  fausse alarme mediane sur lignes propres est de 0,22 (jusqu'a 0,99 sur certains jeux larges
  ou a queue lourde) ; zscore 0,00 (jusqu'a 0,47), great_expectations 0,001, les trois detecteurs
  ML environ 0,13 (fixe par la contamination), deduplication 0,035.
- Le z-score s'effondre sur les valeurs aberrantes univariees (0,00 de rappel median) alors qu'il
  atteignait 0,93 sur le jeu synthetique. Diagnostic (non prevu, realise apres coup et signale
  comme tel, `evidence/typed_injection/masking_diagnostic.json`) : les lignes de type valeur
  invalide (valeur sentinelle ou facteur 1 000) gonflent l'ecart-type calcule sur la partition
  d'entrainement et masquent les valeurs moderees. Sans ces lignes dans l'entrainement le rappel du
  z-score est de 1,00 sur les 42 jeux. C'est un resultat sur la fragilite des statistiques non
  robustes quand l'entrainement est contamine, pas sur le z-score a donnees propres.
- Sur ces distributions reelles les detecteurs ML ne retrouvent pas le profil du jeu synthetique
  pour l'aberrante multivariee (0,89 et 0,90 sur Faker pour isolation_forest et ocsvm, 0,37 et
  0,17 ici) : la paire de colonnes la plus correlee d'un jeu reel est souvent a queue lourde et la
  violation de correlation est moins separable que dans une population gaussienne.

## Limites

Anomalies injectees et non naturelles ; magnitudes fixees d'avance et non ajustees ; un seul niveau
de severite ; colonnes continues seulement (les variables categorielles ne portent pas
d'injection) ; la derive repose sur un ordre d'arrivee synthetique ; la stabilite des rangs est
en partie mecanique parce que beaucoup de cellules valent 0 ou 1 ; le rappel n'est pas corrige des
fausses alarmes ; le diagnostic de masquage est exploratoire. Les modeles profonds (autoencodeur,
LSTM) ne sont pas dans cette matrice : ils font l'objet de l'issue #64.
