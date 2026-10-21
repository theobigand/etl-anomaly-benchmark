# Injection typee sur donnees reelles : protocole et hypotheses (issue #65)

Ce document est ecrit et archive avant tout resultat. Il fixe le protocole et les hypotheses ; un
resultat qui les contredit est rapporte tel quel.

## Question

Sur donnees synthetiques (Faker), chaque methode de detection a un profil par type d'anomalie
(figure `heatmap_synthetic`). Ce profil tient-il sur des distributions reelles ?

## Jeux utilises

Regle fixee d'avance, appliquee au pool de l'issue #66 (`pool_manifest.json`) : jeux UCI ayant le
role de porteur, au moins 3 000 lignes apres normalisation, au moins 4 colonnes continues (au moins
10 valeurs distinctes). Pour un jeu etiquete, seules les lignes de la classe normale servent de
support ; la classe d'anomalie d'origine est exclue (elle reste dans une colonne a part, hors
evaluation). Au plus 20 000 lignes par jeu (tirage aleatoire, graine 0) pour borner le cout de LOF
et OC-SVM. Aucun jeu n'est retire apres avoir vu un resultat.

## Injection

Six types, taux de 3 % par type, severite 1 (meme valeurs que le jeu synthetique), colonnes
continues seulement :

- valeur manquante : une ou deux cellules mises a NaN ;
- doublon : copie exacte d'une ligne propre, ajoutee ;
- aberrante univariee : une colonne portee a la moyenne plus ou moins u ecarts-types, u tire dans
  [6, 12] ;
- aberrante multivariee : la paire de colonnes la plus correlee (en valeur absolue) recoit une
  valeur au quantile 97 % pour l'une et 3 % pour l'autre, de sorte que la correlation est violee
  alors que chaque marginale reste dans la plage observee ;
- derive temporelle : une colonne `t` (ordre d'arrivee) est ajoutee ; les lignes derivees sont dans
  les 10 % les plus recents et trois colonnes sont decalees de +1,5 ecart-type ;
- valeur invalide : changement de signe, valeur sentinelle (-999) ou erreur d'echelle (facteur
  1 000) sur une colonne positive.

Protocole identique au jeu synthetique : decoupage 70/15/15 par groupe d'identite, cinq graines
(42, 1, 2, 3, 4), detecteurs ajustes sur l'entrainement avec contamination egale a la prevalence
d'entrainement, rappel par type sur le test (negatifs restreints aux lignes propres).

## Hypotheses

- **H1 (specialisation)** : les profils tiennent. Valeur manquante : great_expectations a un rappel
  d'au moins 0,9 sur chaque jeu. Doublon : seule la regle de deduplication atteint 0,9. Aberrante
  univariee : zscore, iqr et les detecteurs ML depassent 0,7 en rappel median.
- **H2 (multivarie)** : le rappel median de isolation_forest et ocsvm sur l'aberrante multivariee
  depasse celui de zscore et iqr d'au moins 0,4 ; zscore et iqr restent sous 0,2.
- **H3 (derive)** : aucune methode n'atteint 0,5 de rappel median sur la derive temporelle.
- **H4 (stabilite)** : la correlation de rang moyenne entre les matrices methode par type de deux
  jeux est d'au moins 0,7 ; elle est plus faible pour l'aberrante multivariee et la derive que pour
  les trois types structurels (manquante, doublon, invalide).
- **H5 (dependance au jeu)** : le rappel de isolation_forest sur l'aberrante univariee diminue avec
  le nombre de colonnes continues (correlation de rang negative).

Les intervalles sont des bootstraps sur les jeux (resume groupe) et sur les graines (par jeu).

## Limites annoncees

Les anomalies sont injectees et non naturelles ; le doublon et la valeur manquante sont des
defauts de structure et non des valeurs atypiques ; la derive repose sur un ordre d'arrivee
synthetique sauf pour les jeux ordonnes dans le temps.
