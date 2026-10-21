# Registre complet de detecteurs : protocole et hypotheses

Ce document est ecrit et archive avant tout resultat de ces nouveaux detecteurs. Un resultat qui
contredit une hypothese est rapporte tel quel, ainsi qu'un modele qui ne converge pas ou qui echoue.

## Question

Le registre comptait six detecteurs (trois regles, trois modeles classiques), un detecteur de derive
et un autoencodeur. Les conclusions (pas de methode universelle, le regime decide, les modeles
appris n'ajoutent que peu sur des etiquettes rares) tiennent-elles quand le registre couvre les
familles de detecteurs non supervises les plus utilisees, classiques et profondes ?

## Detecteurs ajoutes

Tous viennent de PyOD 3.6.7, sauf PCA (voir plus bas) (meme interface `fit` / `predict` / `score`, meme preparation que les
detecteurs existants : colonnes numeriques, imputation par la mediane, standardisation sur
l'entrainement). Reglages par defaut de PyOD, aucun reglage apres avoir vu un resultat. Le seuil de
decision est le quantile `1 - contamination` des scores, la contamination etant la prevalence
d'entrainement bornee comme pour les autres modeles.

Classiques (ajoutes a `DETECTOR_NAMES`) :

- **ECOD** : fonctions de repartition empiriques par colonne, queues gauche et droite combinees ;
- **COPOD** : copule empirique, probabilite de queue conjointe des colonnes ;
- **HBOS** : histogrammes par colonne, score en log-densite inverse ;
- **KNN** : distance au k-ieme voisin (k = 5) ;
- **PCA** : erreur quadratique moyenne de reconstruction apres projection sur les composantes qui
  expliquent 95 % de la variance (scikit-learn ; la classe `PCA` de PyOD note une distance ponderee
  aux vecteurs propres, ce qui n'est pas une erreur de reconstruction). Une ligne qui reste dans le
  sous-espace conserve n'est pas signalee : c'est une limite du modele, pas un defaut de
  l'implementation.

Profonds (dans `DEEP_NAMES`, avec l'autoencodeur MLP existant) :

- **VAE** : autoencodeur variationnel, score par erreur de reconstruction ;
- **Deep SVDD** : reseau entraine a ramener les lignes normales dans une petite hypersphere ;
- **DIF** (Deep Isolation Forest) : isolation par arbres dans des representations aleatoires d'un reseau ;
- **AE1SVM** : autoencodeur combine a une approximation de OC-SVM ;
- **LUNAR** : reseau de neurones sur les distances aux plus proches voisins.

L'autoencodeur LSTM reste hors registre : il lit des fenetres de lignes ordonnees et ne partage pas
le contrat par ligne. Il est conserve tel qu'a l'issue #64.

## Ecarts a PyOD, fixes avant tout run

Le contrat du projet veut qu'un detecteur ajuste associe un score a une ligne, sans regarder les
autres lignes evaluees. Quatre modeles PyOD ne le respectent pas ; seule l'etape de score est
modifiee (les tests de contrat du registre le verifient pour les 19 noms) :

- **ECOD et COPOD** recalculent les fonctions de repartition sur les lignes d'entrainement plus les
  lignes evaluees. Ils sont recodes ici avec les seules lignes d'entrainement (la ligne est classee
  comme si elle y etait ajoutee, ce que PyOD calcule pour un lot d'une ligne ; un test compare les
  deux), et le signe de l'asymetrie est fixe a l'ajustement ;
- **VAE** tire un code latent au hasard au moment du score ; le score utilise la moyenne du code ;
- **DIF** standardise les representations des lignes evaluees avec leur propre moyenne et variance ;
  la standardisation est celle des lignes d'entrainement ;
- **AE1SVM** echoue sur une seule ligne ; la ligne est dupliquee pour le score.

Les modeles PyTorch tournent en float32 sur CPU (PyTorch 2.14.1, conda-forge), graine fixee a la
graine de la repetition. Le registre ne les importe qu'a l'ajustement.

## Protocole

Meme protocole que les etudes existantes, sans modification :

- **Benchmark principal** (Credit Card, Cardio, Water Quality) : decoupage 70/15/15 stratifie, cinq
  graines, contamination egale a la prevalence d'entrainement. Sur Credit Card, KNN est exclu
  (quadratique, comme LOF et OC-SVM) ; ECOD, COPOD, HBOS et PCA y sont lances ;
- **Matrice par type du jeu synthetique** (12 360 lignes, six types), cinq graines ;
- **Injection typee** sur les 42 tables eligibles ;
- **100 problemes etiquetes du pool**, cinq graines ;
- **Deux schemas supplementaires** (transactions, capteurs) en plus du tableau clients.

Les modeles profonds sont ajustes sur au plus 20 000 lignes d'entrainement tirees au hasard (graine
de la repetition), pour borner la duree ; la limite est enregistree dans chaque run. Les modeles a
voisins (LOF, KNN) sont sautes au-dela de 50 000 lignes d'entrainement et OC-SVM au-dela de 20 000,
chaque saut etant consigne. Les graines torch sont fixees a la graine de la repetition ; un modele
qui echoue est consigne avec sa raison, jamais omis. Les etudes chronologique et de decisions sous
derive restent sur leurs quatre detecteurs : leur protocole etait ferme avant l'ajout et n'est pas
rouvert.

## Sorties

Pour chaque detecteur et chaque etude : les metriques de l'etude (precision, rappel, F1, ROC-AUC,
PR-AUC, part de lignes signalees ; rappel par type pour les etudes typees), mediane et intervalle
bootstrap sur les jeux pour le pool et l'injection typee, temps de detection, et pour les modeles
profonds les reglages et versions. Resume : tableaux par etude et classement par PR-AUC median.

## Hypotheses

- **H1 (classiques sur le pool)** : au moins un des cinq nouveaux detecteurs classiques (ECOD, COPOD,
  HBOS, KNN, PCA) a un PR-AUC median sur les 100 problemes superieur a celui de Isolation Forest.
- **H2 (profond sur le pool)** : aucun detecteur profond n'a un PR-AUC median superieur de plus de
  0,02 a celui du meilleur detecteur classique (ancien ou nouveau).
- **H3 (marges seules)** : sur le jeu synthetique, le rappel moyen sur les valeurs aberrantes
  multivariees de ECOD, COPOD et HBOS est au plus 0,20 chacun, et celui de Isolation Forest depasse
  le meilleur des trois d'au moins 0,50.
- **H4 (lineaire contre non lineaire)** : sur les valeurs aberrantes multivariees du jeu synthetique,
  le rappel moyen de PCA est a moins de 0,10 de celui de l'autoencodeur MLP.
- **H5 (derive)** : sur le jeu synthetique, aucun nouveau detecteur (classique ou profond) ne depasse
  de plus de 0,10 le meilleur rappel par ligne des detecteurs deja presents sur la derive temporelle.
- **H6 (convergence et echecs)** : aucun detecteur profond n'echoue sur plus de 5 % des problemes du
  pool hors sauts documentes.

Avec cinq graines les intervalles sont indicatifs ; aucune hypothese n'est un test formel.

## Limites annoncees

Reglages par defaut de PyOD : un modele profond mal regle est un resultat sur ses reglages, pas sur
sa famille. La limite de 20 000 lignes d'ajustement desavantage les modeles profonds sur les grands
jeux. Les etiquettes UCI viennent d'une regle ; 19 sources apparaissent deux fois dans le pool. Les
jeux synthetiques encodent mes hypotheses sur l'aspect de chaque type. Les etudes chronologique et
de decisions ne contiennent pas les nouveaux detecteurs.
