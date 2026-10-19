# Pilote LSTM-autoencodeur (issue 52)

Protocole écrit et versionné **avant** toute exécution du modèle. Il réutilise,
sans les modifier, les partitions et le cadre du pilote chronologique
(`temporal_pilot.md`, issue 51).

## 1. Raison d'inclure un modèle séquentiel, et ce qui la limite

Hypothèse falsifiable : le contexte récent du flux de transactions (les `k`
lignes qui précèdent) porte un signal de fraude que l'autoencodeur par ligne ne
voit pas. Limite déclarée : Credit Card est un flux anonyme, sans identifiant de
porteur ; la fenêtre est le flux global des `k` lignes précédentes, pas
l'historique d'un client. Un résultat nul est donc un résultat attendu et
informatif : il dirait que ce contexte global ne suffit pas.

## 2. Données et partitions

Credit Card seul (seul jeu avec un temps authentique, voir 51), mêmes lignes
nettoyées, variables V1 à V28 et Amount sans `Time`, partition chronologique
0,70/0,15/0,15 (`chronological_split`), train 198 609 lignes, test 42 557 lignes
dont 52 fraudes. Normalisation et imputation ajustées sur le train seul.
Les fenêtres sont construites une partition à la fois (`causal_windows`) : une
fenêtre de test ne contient aucune ligne du train, aucune ligne future.

## 3. Modèles comparés

- **A : `AutoencoderDetector`** du dépôt (perceptron `scikit-learn`, réglages
  par défaut), ligne par ligne.
- **B : LSTM-autoencodeur** (`research/lstm_detector.py`), fenêtre de
  `k = 10` lignes, une couche LSTM encodeur de 32 unités, une couche LSTM
  décodeur, reconstruction de la fenêtre, score = erreur quadratique moyenne de
  reconstruction de la **dernière** ligne de la fenêtre (le score revient à
  l'événement qui ferme la fenêtre). Seuil = quantile `1 - prévalence du train`
  des scores du train, comme les autres détecteurs ML.
- Références déjà mesurées au pilote 51 : Z-score, IQR, Great Expectations,
  Isolation Forest (non réentraînés ; mêmes partitions).

Architecture **fixée à l'avance** (`k`, taille cachée) : aucune sélection sur la
validation ni sur le test. La validation sert à l'arrêt anticipé uniquement :
perte de reconstruction sur les lignes de validation, sans étiquettes, patience
de 3 époques, 20 époques au plus.

## 4. Budget et équité

Mêmes lignes d'entraînement pour A et B : un sous-échantillon aléatoire fixe de
50 000 lignes d'entraînement (fenêtres construites sur le flux complet puis
échantillonnées pour B). Entraînement CPU seul. Les budgets d'entraînement
(itérations, époques) diffèrent par nature et sont rapportés, jamais comparés
comme des coûts égaux ; les temps ne sont pas un critère. Budget total visé :
moins de 60 minutes de CPU de portable.

## 5. Hypothèses et critères (exploratoires, fixés avant exécution)

- **H1.** Le PR-AUC de test de B dépasse celui de A. Critère : l'intervalle à
  95 % de la différence B - A, par bootstrap par blocs de 30 minutes sur le test
  (mêmes rééchantillonnages pour A et B, 1 000, graine 42), exclut zéro. C'est
  un critère exploratoire, pas un test d'hypothèse formel (52 fraudes, une seule
  période).
- **H2.** B reste en dessous d'Isolation Forest et de Great Expectations en
  PR-AUC (attente prudente : aucun modèle appris ne domine sur ce jeu).
- **Contrôle de faisabilité synthétique** : sur un flux synthétique où
  l'anomalie est une séquence (deux lignes consécutives anormales ensemble,
  normales séparément), B doit surpasser A ; sinon l'implémentation est suspecte
  avant même d'interpréter Credit Card.

Graines d'initialisation : 42 (principale), 1, 2, 3, 4 (robustesse : signe de la
différence rapporté pour chacune). Aucun hyperparamètre n'est retouché après
avoir vu un résultat.

## 6. Convergence, échecs et reproductibilité

Sont enregistrés pour chaque graine : époques effectuées, perte d'entraînement
et de validation, indicateur de convergence (arrêt anticipé ou budget épuisé),
versions des bibliothèques, graine, matériel, durée. Un modèle qui ne converge
pas, ou une exécution qui diverge, est archivé et rapporté tel quel. Les
réglages de déterminisme du framework sont fixés (CPU, `manual_seed`, threads
limités) et leurs limites déclarées.

## 7. Périmètre de l'implémentation

Le framework de calcul (PyTorch CPU) n'entre pas dans les dépendances du projet
ni dans l'empreinte scientifique : il est épinglé dans
`research/requirements-lstm.txt` et installé dans un environnement séparé. Le
détecteur vit dans `research/`, n'est pas enregistré dans le registre et ne
modifie ni `src/` ni `experiments/` : l'empreinte `cecbed00` et les archives
publiées restent valides, sans rejeu. Les tests rapides sans PyTorch (fenêtres,
alignement, absence de futur) sont dans la suite FAST ; ceux qui entraînent un
réseau miniature sont dans `research/tests/`, lancés avec l'environnement LSTM,
hors CI ordinaire.

## 8. Ce que le pilote ne prétend pas

Un jeu, deux jours, 52 fraudes en test, fenêtre sur un flux global et non sur un
client. Le résultat éventuel ne se généralise pas. Aucun tableau n'entre dans le
manuscrit avant vérification des preuves.
