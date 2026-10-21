# Lignes deep dans la matrice methode par type : protocole et hypotheses (issue #64)

Ce document est ecrit et archive avant tout resultat. Un resultat qui contredit une hypothese est
rapporte tel quel, ainsi qu'un entrainement qui ne converge pas.

## Question

La matrice methode par type du jeu synthetique (`heatmap_synthetic`) n'a que des lignes de
detecteurs par ligne et un detecteur de derive a fenetre. Un autoencodeur et un autoencodeur LSTM
changent-ils la matrice, en particulier sur la derive temporelle, la colonne la plus faible
(meilleur rappel 0,35) ?

## Donnees et decoupage

Jeu synthetique de `make_synthetic` (12 360 lignes, six types a 3 %), meme decoupage que le
benchmark par type : 70/15/15 par identite client, stratifie sur le type, cinq graines (42, 1, 2, 3,
4), jeu regenere par graine. Les detecteurs existants sont recalcules par le meme code
(`run_synthetic_benchmark.evaluate`) sur le meme decoupage, de sorte que les lignes deep et les
autres lignes sont comparables ligne a ligne ; l'archive publiee n'est pas modifiee.

## Modeles

- **autoencodeur** (`AutoencoderDetector`, registre, reglages par defaut) : colonnes numeriques,
  contamination egale a la prevalence d'entrainement, graine d'initialisation egale a la graine de
  la repetition ;
- **autoencodeur LSTM** (`research/lstm_detector.py`, valide a l'issue #52) : six colonnes
  numeriques, fenetres causales de 10 lignes ordonnees par `signup_date`, construites une
  partition a la fois, 32 unites, centre et echelle calcules sur l'entrainement, seuil au quantile
  `1 - prevalence` des erreurs d'entrainement. Les lignes de validation ne servent qu'a l'arret
  precoce sur la perte de reconstruction (sans etiquette).

Difference avec le pilote #52 : l'entrainement va jusqu'a la convergence (au plus 300 epoques,
patience 5) sur toutes les fenetres d'entrainement, au lieu d'un plafond de 20 epoques. Aucun
hyperparametre n'est retouche apres avoir vu un resultat.

## Sorties

Par graine, par methode et par type : rappel et precision (negatifs restreints aux lignes
propres), taux de faux positifs sur lignes propres, et pour chaque modele deep : epoques
effectuees, meilleure epoque, indicateur de convergence (arret par patience avant le plafond),
pertes, versions, duree. Resume : moyenne et ecart-type sur les graines.

## Hypotheses

- **H1 (derive)** : le rappel moyen de l'autoencodeur LSTM sur la derive temporelle depasse celui
  de chacun des detecteurs par ligne (zscore, iqr, great_expectations, isolation_forest, lof,
  ocsvm, autoencodeur) d'au moins 0,10. Le detecteur `drift` est compare a part, sans test.
- **H2 (types par ligne)** : sur les valeurs manquantes, les doublons et les formats invalides,
  le rappel du LSTM ne depasse pas de plus de 0,05 le meilleur detecteur par ligne.
- **H3 (convergence)** : chaque modele deep s'arrete par patience avant le plafond sur au moins
  quatre graines sur cinq.
- **H4 (autoencodeur)** : sur les valeurs aberrantes multivariees, le rappel de l'autoencodeur est
  au moins egal a celui de zscore et iqr (il reconstruit les correlations), sans etre superieur
  de plus de 0,05 a isolation_forest.

Les intervalles sont ceux des cinq graines (moyenne et ecart-type) ; avec cinq graines ils sont
indicatifs et aucune des hypotheses n'est un test formel.

## Limites annoncees

Les lignes du jeu synthetique sont des clients independants : l'ordre par date d'inscription n'a
de structure sequentielle que pour la derive (les lignes derivees sont les plus recentes). Le
LSTM ne voit que les colonnes numeriques (les valeurs manquantes sont imputees par la mediane
d'entrainement, l'email, le pays et la date ne sont pas lus). Un seul schema ; le LSTM reste hors
du registre et de l'empreinte scientifique.
