# Decision sous derive temporelle : protocole et hypotheses (issue #63)

Ce document est ecrit et archive avant tout resultat sur Bank Marketing et avant tout calcul de
cette etude. Les resultats du pilote chronologique de Credit Card (`temporal_pilot.md`) sont deja
connus : les hypotheses ci-dessous ont donc ete ecrites en sachant que le classement de Credit Card
change et que le seuil appris sur le passe ne suit pas. Elles ne valent pas comme test independant
pour ce jeu ; Bank Marketing est la seule epreuve nouvelle.

## Question

Les scores des detecteurs survivent-ils au temps, et les decisions prises avec un seuil fixe sur le
passe aussi ? Quatre sous-questions :

1. **Classement** : l'ordre des detecteurs par PR-AUC change-t-il entre un decoupage stratifie et un
   decoupage chronologique ?
2. **Transfert du point de fonctionnement** : comment evoluent precision, rappel et taux de fausses
   alertes quand le seuil vient (a) de l'entrainement, (b) de la fenetre de validation la plus
   recente, (c) d'une recalibration glissante, toutes sans etiquettes de la periode evaluee ?
3. **Prevalence** : quelle part de l'ecart entre les deux decoupages reste quand le controle
   stratifie est apparie sur la prevalence du test chronologique ?
4. **Contexte** : le cout de detection est mesure par l'etude de couts (issue #53) et n'est pas
   repete ici.

## Jeux et droits

- **Credit Card Fraud** (Kaggle, ODbL/DbCL ; `Time` en secondes depuis la premiere transaction,
  environ deux jours) : deja utilise ; le fichier est ordonne par `Time`.
- **Bank Marketing** (UCI 222, CC BY 4.0 lue sur la page du jeu, 45 211 lignes, anomalie = classe
  rare `y = yes`, 11,7 %) : la page UCI dit que les fichiers sont ordonnes par date, de mai 2008 a
  novembre 2010 ; la colonne `month` du fichier utilise confirme l'ordre (trois annees, les mois se
  suivent sans retour en arriere). Le fichier ne donne pas le jour : l'horodatage est le mois, avec
  l'ordre du fichier a l'interieur du mois.
- **Exclus** : AnoShift / Kyoto-2006+ (annees reelles 2006 a 2015) : telechargement de plusieurs
  Go et droits d'usage des donnees non verifies a la source ; exclu de cette etude et signale comme
  suite possible. Aucun decalage simule n'est utilise.

## Protocole

Detecteurs : zscore, iqr, great_expectations, isolation_forest, aux reglages par defaut du
registre, ajustes sur l'entrainement ; contamination egale a la prevalence d'entrainement. Pour
Bank Marketing les variables categorielles sont encodees en indicatrices (valeur manquante =
categorie), sans autre transformation.

- **Decoupage chronologique** 70/15/15 par le temps (entrainement le plus ancien, test le plus
  recent). **Controle stratifie** : meme decoupage 70/15/15 stratifie sur l'etiquette, cinq graines
  (42, 1, 2, 3, 4).
- **Score** de chaque detecteur sur entrainement, validation et test. Prevalence d'entrainement
  `pi`.
- **Politiques de seuil** (sur les scores, un score est signale s'il depasse le seuil) :
  - P0 : quantile `1 - pi` des scores d'entrainement ;
  - P1 : quantile `1 - pi` des scores de la validation ;
  - P2 : le test est coupe en 20 blocs consecutifs de meme taille ; le seuil d'un bloc est le
    quantile `1 - pi` des scores des deux blocs precedents (les dernieres lignes de la validation
    pour les premiers), sans etiquette.
- **Mesures** : PR-AUC et ROC-AUC sur le test ; a chaque politique : precision, rappel, F1, taux de
  fausses alertes, part de lignes signalees rapportee a la prevalence du test.
- **Incertitude** : intervalle bootstrap par blocs (50 blocs consecutifs du test, 1 000 tirages,
  graine 42) pour le PR-AUC chronologique ; moyenne et ecart-type sur cinq graines pour le controle.
- **Controle apparie** : le test stratifie est sous-echantillonne (graine = graine du controle) pour
  atteindre la prevalence du test chronologique, en retirant des positifs ou des negatifs.

## Hypotheses

- **H1 (classement)** : la correlation de rang de Spearman entre l'ordre des detecteurs par PR-AUC
  (stratifie moyen contre chronologique) est d'au moins 0,8 sur chaque jeu.
- **H2 (seuil)** : sur chaque jeu, l'erreur mediane sur les detecteurs de la part signalee,
  `|log(part signalee / pi)|`, est plus petite avec P2 qu'avec P1 et plus petite avec P1 qu'avec P0.
- **H3 (decision)** : le F1 de P2 est au moins egal a celui de P0 pour au moins la moitie des
  couples detecteur-jeu.
- **H4 (prevalence)** : l'ecart de PR-AUC entre controle apparie et test chronologique (mediane sur
  les detecteurs) est au plus la moitie de l'ecart entre controle stratifie et test chronologique,
  sur chaque jeu.

## Limites annoncees

Deux jeux, dont un de deux jours ; l'horodatage de Bank Marketing est au mois ; les etiquettes de
Bank Marketing ne sont pas des anomalies de qualite de donnees (classe rare d'une campagne) ; les
detecteurs gardent leurs reglages par defaut ; la contamination vient des etiquettes
d'entrainement, la seule information etiquetee que les politiques utilisent. Les resultats
n'etablissent pas une regle generale.
