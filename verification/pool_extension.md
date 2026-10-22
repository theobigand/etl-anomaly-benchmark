# Extension de toutes les etudes au pool : protocole et hypotheses

Ce document est ecrit et archive avant tout resultat de l'extension. Un resultat qui contredit une
hypothese est rapporte tel quel ; un jeu qui echoue ou qui n'est pas eligible est consigne avec sa
raison, jamais omis en silence.

## Question

Les etudes approfondies (courbes precision-rappel, balayage de contamination, seuil sans etiquette,
balayage de severite, pipeline ETL de bout en bout, decoupage chronologique, controle des fichiers)
n'ont ete faites que sur trois jeux d'exemple et sur le jeu synthetique. Les conclusions tiennent-elles
sur tout le pool de 152 jeux ouverts (36 ADBench, 116 UCI) ?

## Regle d'application

Une etude est appliquee a tous les jeux du pool pour lesquels elle est definie ; la liste des jeux
ecartes et la raison de chaque ecart sont archivees avec les resultats. Les regles d'eligibilite sont
celles des protocoles existants, sauf la ligne ci-dessous. Aucun jeu n'est retire apres avoir vu un
resultat.

## Etudes et protocole

1. **Passage unique sur les 100 problemes etiquetes** (17 detecteurs : 3 regles, 8 classiques, 6
   neuronaux), meme normalisation (`research/normalise.py`), decoupage 70/15/15 stratifie, cinq
   graines, contamination egale a la prevalence d'entrainement, modeles neuronaux ajustes sur au plus
   20 000 lignes. Pour chaque couple (probleme, graine, detecteur), un seul ajustement fournit :
   - les metriques au seuil de la prevalence d'entrainement (deja archivees) ;
   - les metriques au seuil sans etiquette de 0,02, derive des scores d'entrainement conserves a
     l'ajustement (le seuil de PyOD est le quantile `1 - contamination` de ces scores) ; l'equivalence
     avec un ajustement a 0,02 est verifiee par un test sur les 17 detecteurs ;
   - le temps de detection (ajustement, prediction, score) ;
   - la courbe precision-rappel de la graine 42 (au plus 200 points) et la precision moyenne ;
   - le balayage de contamination d'Isolation Forest sur la grille 0,001 / 0,01 / 0,05 / 0,10 / 0,20
     (meme derivation que pour le seuil de 0,02).
2. **Injection typee sur toute table eligible du pool** : les 116 tables UCI et les 36 jeux ADBench
   (classe normale seule pour un jeu etiquete), regle d'eligibilite inchangee (au moins 3 000 lignes
   apres nettoyage, 4 colonnes continues), 17 detecteurs plus `drift` et la regle de deduplication,
   cinq graines, severite de reference. Les jeux non eligibles sont listes avec leur raison.
3. **Balayage de severite** sur chaque table eligible : multiplicateurs 0,5, 1, 2 et 4, graines 42, 1
   et 2, rappel par type pour les trois types dont l'injection a une amplitude (aberrantes
   univariees, aberrantes multivariees, derive).
4. **Pipeline ETL de bout en bout** sur chacun des 152 jeux : le jeu est ecrit en CSV (variables et,
   s'il est etiquete, l'etiquette), puis extraction, transformation (deduplication), detection avec
   Z-score et Isolation Forest, ecriture des deux fichiers triees, un processus neuf par mesure ; temps
   de chaque etape, lignes lues et conservees, memoire maximale.
5. **Decoupage chronologique et decisions sous derive** sur chaque jeu etiquete du pool qui a une
   variable de temps reelle. Un jeu est eligible si une colonne de date ou d'heure est lisible, si au
   moins 3 000 lignes subsistent apres nettoyage et si la partition de test chronologique compte au
   moins 20 anomalies ; les jeux ADBench, fournis sans colonne de temps, sont ecartes. Protocole du
   pilote (ajustement sur les 70 % les plus anciens, test sur les 15 % les plus recents, controle
   stratifie, seuils P0, P1 et P2 de `temporal_decision.md`), 17 detecteurs.
6. **Controle des fichiers** : chaque fichier local du pool est compare a l'empreinte du manifeste
   epingle (taille, empreinte, nombre de lignes et de colonnes, prevalence des etiquettes) par un test
   marque `real`, puis par la verification locale.

## Hypotheses

- **P1 (seuil sans etiquette)** : pour au moins 12 des 17 detecteurs, la mediane du F1 sur les 100
  problemes est plus basse au seuil de 0,02 qu'au seuil de la prevalence d'entrainement.
- **P2 (classement)** : le classement des detecteurs par precision moyenne (courbes) est celui du
  PR-AUC median deja publie (correlation de rang de Spearman d'au moins 0,99).
- **P3 (severite)** : pour chacun des 17 detecteurs, le rappel median sur les aberrantes multivariees
  (mediane sur les tables) a la severite 4 depasse celui de la severite 0,5.
- **P4 (pipeline)** : sur les jeux de plus de 50 000 lignes, la detection represente plus de 30 % du
  temps du pipeline avec Isolation Forest et moins de 10 % avec le Z-score (ordre de grandeur de
  Credit Card).
- **P5 (chronologie)** : sur les jeux eligibles, le PR-AUC chronologique est inferieur au PR-AUC
  stratifie pour au moins deux tiers des couples (jeu, detecteur).
- **P6 (controle)** : aucun fichier du pool ne differe du manifeste.

Avec cinq graines (trois pour la severite) les intervalles sont indicatifs ; aucune hypothese n'est un
test formel.

## Limites annoncees

Les etiquettes UCI viennent d'une regle (la classe la plus rare), pas d'experts ; les jeux ne sont pas
independants (19 sources apparaissent deux fois) ; les temps du passage unique sont mesures avec
plusieurs processus en parallele et ne sont pas des temps d'execution isoles (l'etude de cout les
mesure seuls) ; les modeles neuronaux gardent les reglages par defaut de PyOD ; la chronologie ne couvre
que les jeux qui ont une variable de temps, aucun temps n'etant invente pour les autres.
