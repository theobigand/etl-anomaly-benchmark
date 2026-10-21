# Benchmark sur les 100 problemes etiquetes du pool : protocole et hypotheses

Ce document est ecrit et archive avant tout resultat. Il fixe le protocole et les hypotheses ; un
resultat qui les contredit est rapporte tel quel.

## Question

Le benchmark principal porte sur trois jeux reels. Le pool de l'issue #66 compte 152 jeux ouverts
(`dataset_pool.md`) : 100 d'entre eux ont des anomalies deja etiquetees (36 ADBench, 64 UCI), 116
servent de support a l'injection typee (42 retenus, `typed_injection.md`). Les conclusions sur les
trois jeux (une methode ne domine pas, le regime decide) tiennent-elles sur 100 problemes ?

## Jeux utilises

Les 100 problemes etiquetes du pool, sans autre filtre : `adbench_normalisation_report.json` (36
jeux, statut ok) et les lignes `labelled` de `uci_pool.json` (64 jeux). Les 16 jeux UCI etiquetables
presents dans les deux listes sont gardes avec leur derivation propre a chaque source et comptes
deux fois dans le pool ; le resume les distingue par la source. Aucun jeu n'est retire apres avoir
vu un resultat. Un jeu qui echoue est consigne avec sa raison, jamais omis en silence.

## Protocole

- normalisation unique de `research/normalise.py` (colonnes constantes, categories, doublons,
  imputation et standardisation sur l'entrainement) ;
- decoupage 70/15/15 stratifie sur l'etiquette, cinq graines (42, 1, 2, 3, 4) ;
- six detecteurs aux reglages par defaut du registre : zscore, iqr, great_expectations,
  isolation_forest, lof, ocsvm ; la derive (pas d'horloge) et l'autoencodeur (opt-in) sont exclus ;
- detecteurs ajustes sur l'entrainement, contamination egale a la prevalence d'entrainement (bornee
  comme dans le benchmark principal) ;
- LOF saute au-dela de 50 000 lignes d'entrainement et OC-SVM au-dela de 20 000 (seuils de
  `normalise.py`, fixes d'apres l'etude de couts) ; chaque saut est consigne ;
- metriques sur le test, celles du benchmark principal (`compute_metrics`) : precision, rappel, F1,
  ROC-AUC, PR-AUC (precision moyenne), part de lignes signalees ;
- un jeu est ecarte de la moyenne d'une methode seulement si la methode est sautee.

## Resume

PR-AUC et ROC-AUC moyennes sur les graines, puis mediane sur les jeux avec un intervalle bootstrap a
95 % (2 000 tirages de jeux). Rang de chaque methode par jeu (rang moyen en cas d'egalite). Les
jeux sont regroupes par prevalence d'anomalies : moins de 5 %, de 5 a 20 %, plus de 20 %.

## Hypotheses

- **H1 (pas de methode universelle)** : les intervalles a 95 % du PR-AUC median des deux meilleures
  methodes se recouvrent.
- **H2 (apport de l'apprentissage)** : le PR-AUC median de isolation_forest depasse celui de zscore
  et celui de iqr.
- **H3 (regime)** : la difference de PR-AUC entre isolation_forest et zscore est positive en
  mediane quand la prevalence est inferieure a 5 %, et ne l'est pas quand elle depasse 20 %.
- **H4 (cout en fausses alertes)** : au seuil de la prevalence d'entrainement, iqr signale en
  mediane plus de trois fois la prevalence, plus que tous les autres detecteurs.
- **H5 (source)** : l'ordre des methodes par PR-AUC median est le meme pour ADBench et pour UCI
  (correlation de rang de Spearman d'au moins 0,7).

## Limites annoncees

Les etiquettes UCI sont derivees par une regle (la classe la plus rare), pas par des experts, et ne
sont pas toutes des anomalies au sens du controle qualite ; les detecteurs gardent leurs reglages
par defaut ; la normalisation (standardisation, encodage) est commune et favorise les methodes
sensibles a l'echelle ; les jeux ne sont pas independants (19 sources sont presentes deux fois, de
la meme origine) ; aucun reglage par jeu.
