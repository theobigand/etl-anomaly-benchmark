# Mutations du code scientifique

La campagne porte sur les modules de `src/etl_benchmark` qui calculent un
résultat (chargement, découpage, métriques, pipeline, registre, générateur
synthétique, détecteurs) et sur les dix scripts de `experiments/`. Elle utilise
mutmut 3.8.0 et les tests qui exercent ces fichiers ; les tests qui contrôlent
des archives (filiation, tableaux du manuscrit) ne sont pas lancés pour chaque
mutant. `config.py`, `logging_setup.py`, `__main__.py` et les fichiers
`__init__.py` ne sont pas mutés.

Résultat de `make verify-deep` : **4 487 mutants éliminés sur 4 594 (97,67 %)**,
sans mutant ignoré, expiré, en erreur ou sans test.

| Périmètre | Éliminés | Total | Taux |
| --- | --- | --- | --- |
| `src/etl_benchmark` | 1 824 | 1 900 | 96,00 % |
| `experiments/*.py` | 2 663 | 2 694 | 98,85 % |

La première campagne, limitée à `metrics.py`, donnait 86/97 (88,66 %) ; élargie
aux autres modules de `src/` sans test supplémentaire, elle tombait à 74,5 %.
Les scripts partaient de 24,3 % (1 136/4 666) avant les tests de sorties
décrits plus bas. Le chargement des scripts sous le nom `experiments.<script>`
(`tests/conftest.py`) est ce qui permet à mutmut de relier leurs fonctions aux
tests.

## Ce qui a été corrigé

- Les messages d'erreur étaient testés par fragment (`match="..."` cherche
  une sous-chaîne) ; ils sont maintenant comparés en entier, car ils disent
  quel contrat a échoué.
- Découpage : la stratification n'était contrôlée sur aucune graine, les
  ratios nuls et les trois groupes de dates exacts n'étaient pas testés, ni
  l'ordre des lignes à horodatage égal, ni les fuseaux horaires.
- Générateur synthétique : les bornes, l'arrondi, les formats, les quantiles
  utilisés par les anomalies multivariées et la sévérité n'étaient pas
  vérifiés. Un test fixe aussi l'empreinte du jeu de référence (graine 42),
  car les tableaux publiés en dépendent ; il élimine d'un coup les mutants qui
  modifient un paramètre de distribution, et un changement volontaire du
  générateur oblige à mettre l'empreinte à jour avec le rejeu.
- Pipeline : chronométrage de chaque étape, journaux, étiquette par défaut et
  fichiers écrits.
- Détecteurs : valeurs par défaut, colonnes explicites, écart type ou IQR
  égal à 1, comptage des violations par ligne, valeurs manquantes à
  l'évaluation, seuil exactement atteint, fenêtre minimale et plafond de 4
  écarts types du détecteur de dérive.
- Du code redondant a été retiré (comportement inchangé, mêmes données
  synthétiques) : `recall_score` et `f1_score` sans `zero_division` (les deux
  classes sont présentes), validation des ratios partagée, `clip` mort sur le
  montant moyen, `fillna(False)` après `any`, conditionnelles dont le cas vide
  est déjà géré par pandas.

## Survivants

Les 76 mutants restants de `src/` ne sont pas retirés du dénominateur et aucun n'a été
exclu. Leur classement est une lecture des diffs, pas une preuve formelle.

| Mutants | Ce qui change | Raison |
| --- | --- | --- |
| 27 | Valeur initiale `None` remplacée par `""` ou `True`, `or` remplacé par `and` dans le test « non ajusté » | `fit` affecte ces attributs ensemble ; l'état intermédiaire n'est pas atteignable depuis l'API. |
| 17 | `dtype=None` ou `astype(None)` au lieu de `float`, `int` ou `np.int64` | Même résultat que `float64` pour les entrées acceptées ; vérifié sous numpy 2.4 pour booléens, entiers, flottants et chaînes numériques. |
| 19 | `replace=None` et `NaN` remplacé par `None` (génération), `index=None` (`to_csv`), `reset_index(drop=None ou False)` et `mode=None` (GX), `kind="STABLE"`, `tz_localize("utc")` (2), tolérance `>=` 1e-6, bornes `>=` de `moved` et `outlier_z`, `/ direction` à la place de `*`, `row[gross] = None`, `reshape(None)`, `warnings.simplefilter("ignore")` sans catégorie, nom de paquet en majuscules dans `importlib.metadata.version` (2) | Même sortie observable : valeur fausse équivalente, casse acceptée par la bibliothèque, égalité exacte entre flottants inatteignable, signe valant ±1, `NaN` remis à 0 ensuite. |
| 6 | Noms internes `pandas`, `asset`, `batch` du contexte Great Expectations | Étiquettes sans effet sur les lignes signalées. |
| 3 | `Faker("en_US")` : `None`, `en_us`, `EN_US` | La locale par défaut est `en_US` et Faker normalise la casse. |
| 2 | Plafond du taux de Poisson à 91 ou supprimé | Atteint seulement pour un revenu annuel supérieur à 360 000, soit plus de 4,5 écarts types de la loi utilisée ; aucun test n'impose un tirage de queue de cette taille. |
| 2 | `training=None` au lieu de `False` | `None` est évalué comme faux. |

## Scripts d'`experiments/`

Les tests des scripts vérifient, pour chacun, ce qu'il lit, journalise et écrit :
fichiers produits et noms horodatés, contenu exact des tableaux et de
l'enregistrement de provenance, lignes de journal, options et textes d'aide,
messages d'erreur, valeurs par défaut, et propriétés des figures (titres,
légendes, données tracées, couleurs, résolution, géométrie de la barre de
couleur). Ils s'appuient sur `main()` appelé dans le processus, sans
sous-processus, avec un faux `git` ou un faux `urlopen` quand c'est nécessaire.
Du code redondant a été retiré (lecture par blocs remplacée par
`hashlib.file_digest`, archive `gzip.compress(..., mtime=0)`, table des
compteurs de couverture, aide `_git` partagée, validation de la contamination
fixe dans le registre).

Les 31 survivants des scripts :

| Mutants | Ce qui change | Raison |
| --- | --- | --- |
| 5 | `index=None` dans `to_csv` ou `to_string` | pandas traite `None` comme `False`. |
| 5 | `strict` de `zip` absent ou valant `None`, `False` | Les deux listes ont toujours la même longueur. |
| 4 | `sort=None` dans un `groupby` | pandas traite `None` comme `False`. |
| 4 | `color=None` ou absent pour une courbe | Le cycle de couleurs par défaut de matplotlib est `tab10`. |
| 3 | `colorbar(None)`, `ax=None` ou `ax` absent | matplotlib retombe sur l'image et les axes courants. |
| 2 | `values=None` ou absent dans `pivot_table` | `recall` est la seule colonne numérique restante. |
| 2 | `zero_division` omis pour la précision | La valeur par défaut renvoie aussi 0 (avec un avertissement). |
| 2 | `astype(None)` au lieu de `astype(int)` | scikit-learn accepte les booléens sans conversion. |
| 2 | `index=None` ou omis dans `pd.Series(flags, index=...)` | Les deux séries ont déjà le même index. |
| 1 | `detect_s = None` à la place de `np.nan` | La colonne reste numérique et manquante. |
| 1 | `<=` au lieu de `<` dans la comparaison à 1e-9 | Égalité exacte entre flottants inatteignable. |

## Limites

- Un mutant éliminé par le test d'empreinte du jeu de référence prouve que le
  jeu publié ne change pas, pas que chaque paramètre a le bon sens
  statistique ; les moments et les bornes sont contrôlés à part.
- La campagne complète dure environ vingt-cinq minutes sur cette machine.
