# Étude de coût et de montée en charge (issue 53)

Protocole écrit et versionné **avant** toute mesure. L'essai préliminaire de
100/300/900 lignes (`scaling.md`, `scaling.json`, état `LEGACY`) n'est ni
modifié ni réutilisé : il ne permet pas d'extrapoler.

## 1. Question

Comment le coût de la détection (temps et mémoire du processus) croît-il avec
le nombre de lignes pour les détecteurs du dépôt, jusqu'à l'échelle de Credit
Card (284 000 lignes), et quelle part de ce coût représente la détection dans
une exécution ETL complète sur ce jeu ?

Aucune hypothèse de classement n'est testée. Le résultat est descriptif : une
courbe de coût par méthode, avec ses échecs et exclusions.

## 2. Ce qui est mesuré, et ce qui ne l'est pas

- **Temps de détection** : `fit_s`, `predict_s`, `score_s` et leur somme
  `detect_s`, tels que les chronomètre `pipeline.detect` (inchangé). C'est la
  latence de l'étape de détection, **pas** la latence d'un ETL complet.
- **Temps ETL complet** (une seule étude, Credit Card réel) : lecture du CSV,
  transformation (dédoublonnage), détection, écriture du CSV trié, chacun
  chronométré à part, avec `time.perf_counter`.
- **Mémoire** : pic de mémoire résidente du processus (`ru_maxrss`, allocations
  natives comprises) dans un **processus neuf par mesure**. On rapporte le pic
  avant détection (interpréteur, bibliothèques, données chargées) et le pic
  après ; la différence est le surcoût de mémoire de la détection, valeur
  plancher (un pic antérieur plus haut la masquerait, ce qui est rapporté par
  une différence nulle). La mémoire d'un enfant lancé par la bibliothèque n'est
  pas mesurée. `tracemalloc` n'est pas utilisé.
- **Non mesuré** : énergie, E/S disque détaillée, GPU, partage du processeur
  entre processus (seulement enregistré, voir 4).

## 3. Matrice bornée

- Données : matrices numériques synthétiques (loi normale, graine 42), 8
  variables ; une seconde série à 29 variables à 30 000 lignes. Les mêmes lignes
  servent à l'ajustement et à l'évaluation (mesure de coût, pas de qualité).
- Tailles : 1 000, 3 000, 10 000, 30 000, 100 000, 300 000 lignes.
- Méthodes : Z-score, IQR, Isolation Forest, LOF, One-Class SVM, autoencodeur
  par ligne (`scikit-learn`), LSTM-autoencodeur (fenêtre 10, 32 unités, au plus 5
  époques, 50 000 lignes d'ajustement au plus, plafond déclaré ; il a une
  implémentation validée depuis l'issue 52).
- Répétitions : 5 jusqu'à 30 000 lignes, 3 au-delà. Un essai de chauffe non
  retenu précède chaque série (même processus, hors mesure).
- Budget : 300 secondes maximum par mesure (le processus est tué) ; un échec ou
  un dépassement est enregistré (`TIMEOUT`, `FAIL` et sa raison) et les tailles
  supérieures de cette méthode ne sont **pas** tentées (exclusion déclarée).
  Durée totale visée : moins de 60 minutes.
- Étude ETL réelle : Credit Card complet, détecteurs Z-score et Isolation
  Forest (ceux de `DATASETS["credit_card"]` sans les méthodes quadratiques),
  3 répétitions, processus neuf.

## 4. Conditions d'exécution

CPU seul, un seul fil de calcul demandé pour le LSTM (`torch.set_num_threads(1)`)
et les réglages par défaut des autres bibliothèques. Machine unique, enregistrée
(modèle, coeurs, mémoire, système, versions). La charge moyenne est lue avant et
après chaque mesure ; une mesure faite avec une charge supérieure à la moitié des
coeurs est **marquée** `contended` (elle n'est pas écartée). L'exécution attend
que la charge retombe sous ce seuil, dans la limite de 10 minutes, avant de
commencer. Aucune garantie d'isolement n'est faite et elle n'est pas prétendue.

## 5. Statistiques et présentation

Médiane, premier et troisième quartiles et minimum/maximum par méthode et taille ;
exposant empirique de croissance (pente de `log(temps)` sur `log(lignes)`) estimé
par régression sur les tailles réussies, rapporté **avec les points**, sans
extrapolation au-delà de la plus grande taille mesurée. Aucun seuil absolu de
temps n'est imposé ni testé dans la CI ou dans FAST.

## 6. Provenance

Chaque mesure enregistre graine, taille, variables, répétition, version des
bibliothèques, charge avant et après, et son statut. L'enregistrement de run
(`provenance.write_record`) porte l'empreinte de la méthode de mesure
(`measurement_fingerprint`, qui couvre `verification/scaling.py` et le
chronométrage de `pipeline.detect`) et l'empreinte scientifique. Le script
`research/cost_study.py` est hors de ces deux empreintes ; son `sha256` est
enregistré. `scaling.json` reste `LEGACY` et intact.

## 7. Ce que l'étude ne prétend pas

Une machine, partagée avec d'autres tâches : les temps absolus ne se
généralisent pas, seule la forme de croissance et l'ordre de grandeur sont
rapportés. Les données synthétiques gaussiennes ne reproduisent pas la
structure de Credit Card. La latence de détection n'est pas la latence d'un
ETL complet ; seule l'étude réelle de la section 3 donne la seconde, pour deux
détecteurs.
