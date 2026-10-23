# Mutations du code scientifique

La campagne porte sur les modules de `src/etl_benchmark` qui calculent un
résultat (chargement, découpage, métriques, pipeline, registre, générateur
synthétique, détecteurs) et sur les dix scripts de `experiments/`. Elle utilise
mutmut 3.8.0 et les tests qui exercent ces fichiers ; les tests qui contrôlent
des archives (filiation, tableaux du manuscrit) ne sont pas lancés pour chaque
mutant. `config.py`, `logging_setup.py`, `__main__.py` et les fichiers
`__init__.py` ne sont pas mutés.

Résultat de `make verify-deep` du run local `local-22f1602` (commit
`22f1602b`, macOS arm64, 23 octobre 2026, non attesté ; preuves scellées dans
`evidence/runs/local-22f1602/`) : **4 975 mutants éliminés sur 5 102
(97,51 %)**, 127 survivants, sans mutant ignoré, expiré, en erreur, interrompu
ou sans test (la barrière `check_mutation.py` refuse ces cas). Le périmètre est
contrôlé par un relevé indépendant (voir « Périmètre contrôlé ») : 28 fichiers
dans le périmètre, 27 ayant reçu des mutants. Les 68 mutants de plus que la
campagne précédente (4 751) viennent des fonctions de provenance, d'empreinte de
mesure et d'écriture atomique des enregistrements, qui sont mutées ; trois
survivants qui y apparaissaient ont été éliminés par des tests (séparateur des
segments, arrêt au premier fichier manquant) ou supprimés parce qu'équivalents
(`directory / name` avec un nom absolu donne déjà ce nom). Les chiffres de la
campagne du 16 octobre (4 643 sur 4 751, 97,73 %, commit `3779905`) sont
historiques.

La note ci-dessous sépare le calcul scientifique de l'orchestration, sans
retirer aucun mutant du dénominateur :

| Périmètre | Éliminés | Total | Taux |
| --- | --- | --- | --- |
| Calcul scientifique : `split`, `metrics`, `synthetic`, `datasets`, `registry`, `transform`, `quality/` | 1 922 | 2 014 | 95,43 % |
| Orchestration, entrées-sorties, scripts : `extract`, `load`, `pipeline`, `atomic`, `experiments/*.py` | 3 053 | 3 088 | 98,87 % |
| Ensemble | 4 975 | 5 102 | 97,51 % |

Le calcul scientifique reste au-dessus de 95 %, mais avec une marge plus
faible que l'ensemble : l'agrégat ne doit pas être lu comme la garantie des
seules fonctions de calcul.

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

Les 74 mutants restants de `src/` ne sont pas retirés du dénominateur et aucun n'a été
exclu. Leur classement est une lecture des diffs, pas une preuve formelle ;
la colonne « Raison » est une hypothèse, sauf mention d'un test.

| Mutants | Ce qui change | Raison |
| --- | --- | --- |
| 27 | Valeur initiale `None` remplacée par `""` ou `True`, `or` remplacé par `and` dans le test « non ajusté » | `fit` affecte ces attributs ensemble ; l'état intermédiaire n'est pas atteignable depuis l'API. |
| 17 | `dtype=None` ou `astype(None)` au lieu de `float`, `int` ou `np.int64` | Même résultat que `float64` pour les entrées acceptées ; vérifié sous numpy 2.4 pour booléens, entiers, flottants et chaînes numériques. |
| 19 | `replace=None` et `NaN` remplacé par `None` (génération), `index=None` (`to_csv`), `reset_index(drop=None ou False)` et `mode=None` (GX), `kind="STABLE"`, `tz_localize("utc")` (2), tolérance `>=` 1e-6, bornes `>=` de `moved` et `outlier_z`, `/ direction` à la place de `*`, `row[gross] = None`, `reshape(None)`, `warnings.simplefilter("ignore")` sans catégorie, nom de paquet en majuscules dans `importlib.metadata.version` (2) | Même sortie observable : valeur fausse équivalente, casse acceptée par la bibliothèque, égalité exacte entre flottants inatteignable, signe valant ±1, `NaN` remis à 0 ensuite. |
| 6 | Noms internes `pandas`, `asset`, `batch` du contexte Great Expectations | Étiquettes sans effet sur les lignes signalées. |
| 3 | `Faker("en_US")` : `None`, `en_us`, `EN_US` | La locale par défaut est `en_US` et Faker normalise la casse. |
| 0 | Plafond du taux de Poisson à 91 ou supprimé | Cités à tort comme inatteignables : un revenu supérieur à 360 000 est possible (environ 5 écarts types, probabilité de l'ordre de 5·10⁻⁷ par ligne). Éliminés par `test_the_transaction_rate_never_exceeds_ninety`, qui force le tirage de revenu. |
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

## Survivants des outils de certification

Les outils ajoutés (`check_mutation.py`, `provenance.py`, `verify_real.py`)
ont produit treize survivants à leur première campagne. Douze étaient de vraies
lacunes (texte des messages, code de sortie, opérateur booléen, tri des clés,
séparateur) et sont éliminés par des tests ; le dernier,
`x_scientific_fingerprint__mutmut_19` (`"PYPROJECT.TOML"` au lieu de
`"pyproject.toml"`), survit seulement parce que le système de fichiers de macOS
ignore la casse. Deux survivants de `_environment_lock` (`"VERIFICATION"`,
`"ENVIRONMENT"`) sont dans le même cas. Ces trois mutants seraient éliminés sur
Linux, donc par la CI (non vérifié) ; ils restent comptés comme survivants.

## Périmètre contrôlé

Le périmètre de mutation n'est plus seulement celui de `pyproject.toml`.
`verification/mutation_scope.json` nomme les racines (`src/etl_benchmark`,
`experiments`), les quatre exclusions justifiées (`__init__.py`, `__main__.py`,
`config.py`, `logging_setup.py`) et le fichier qui ne reçoit aucun mutant
(`quality/__init__.py`). `verification/mutation_scope.py` découvre les
fichiers éligibles dans l'arbre ; un test de FAST compare ce relevé aux motifs
de `pyproject.toml`, et la porte de certification le compare aux fichiers
réellement mutés (`mutants/results.txt`, enregistrés dans le résultat DEEP).
Un module ajouté sans être mué, ou retiré du périmètre, fait échouer le test
puis la certification, quel que soit le score.

## Écart Linux / macOS observé en CI

La campagne DEEP exécutée sur Linux (run 38967428334, `421ea6f`) a donné 109
survivants contre 108 en local. Comparaison des listes : trois survivants
propres à macOS (les trois mutants de casse ci-dessus, éliminés sur Linux) et
quatre propres à Linux, les mutants `datetime.now(UTC)` -> `datetime.now(None)`
de `main` dans `run_benchmark`, `run_curves`, `run_severity` et
`run_synthetic_benchmark`. Sur un exécuteur dont le fuseau local est UTC, ces
mutants sont équivalents ; ils n'étaient éliminés en local que grâce au fuseau
de la machine. Une fixture de `tests/conftest.py` impose désormais un fuseau
décalé (Asia/Kolkata), et les quatre mutants sont éliminés y compris avec
`TZ=UTC`. La campagne Linux corrigée (run 38974460893, commit `292648a`, 4 751
mutants) donne 105 survivants (4 646 / 4 751, soit 97,79 %) : exactement les
108 survivants locaux de l'époque moins les trois mutants de casse, sans
survivant propre à Linux. Cette mesure décrit un état antérieur du code et n'est
pas citée par le manuscrit, qui cite le run local `local-e1fcbb0` (voir
`claims.json`).

## Mutant sensible au temps

`experiments.run_severity.x_run__mutmut_31` (`groupby(sort=False)` devenu
`sort=None`) est équivalent : pandas traite `None` comme `False` pour cet appel
(vérifié sur pandas 3.0.6). Il survit sous Linux (CI) et, en local, mutmut l'a
classé tantôt « tué », tantôt « expiré » quand la machine était chargée. Les
campagnes locales qui comptent des expirations (cinq mutants dont celui-ci, sur
une exécution concurrente d'autres tâches) ont été rejouées pour ces mutants
seulement (`mutmut run <noms>`) ; le résultat retenu est celui du run `local-e1fcbb0` (sept mutants expirés ou suspects sous charge, rejoués seuls dans l'arbre propre : tous éliminés ; aucun mutant n'a été retiré du dénominateur).

## Survivants des modules du registre complet

Les dix détecteurs ajoutés (`quality/ml.py`, `quality/deep.py`,
`quality/_torch_models.py`) apportent des mutants dont 29 survivent. Classement par lecture, sans preuve formelle :

- 10 mutants des valeurs provisoires posées dans `__init__` de
  `TailProbabilityModel` et de `PCAReconstruction` (`np.empty((0, 0))`,
  `float("nan")`, `None`, `float("NAN")`, `svd_solver` omis). Ces valeurs ne
  servent qu'à donner un type aux attributs avant `fit`, qui les remplace ;
  aucun test ne lit un estimateur non ajusté. Équivalents au sens du
  comportement observable après `fit`.
- 8 mutants de `FitScalerDIF._deep_representation` : arguments du
  `DataLoader` (`shuffle`, `drop_last`, `batch_size` omis), appareil `None` et
  clé du dictionnaire des normalisations. Le chargeur ne mélange rien et le
  résultat est le même quel que soit le lot ; l'appareil `None` revient à
  l'appareil par défaut sur CPU ; la clé n'est lue qu'au même endroit.
  Équivalents sur CPU, non prouvés ailleurs.
- 4 mutants de `TailProbabilityModel.decision_function` et `fit` :
  `side` omis dans les deux `searchsorted` (même résultat hors égalités
  exactes entre une ligne et une valeur d'ajustement), `* -1` devenu `/ -1`
  (identique en virgule flottante) et `axis` omis (valeur par défaut). Les deux
  premiers ne sont pas tués faute d'un test avec égalités : c'est une lacune
  des tests, pas une équivalence.
- 7 mutants de `predict` (`astype(None)` donne des flottants de même valeur,
  `>=` au lieu de `>` ne diffère que si un score égale exactement le seuil) et
  des constructeurs `ECODDetector._build_estimator` (méthode `None`, `"ECOD"`,
  `"XXecodXX"`) : la méthode inconnue retombe sur la branche ECOD de
  `decision_function`, donc le résultat de ECOD est inchangé.

Un mutant de `pipeline._features` est apparu comme suspect pendant la
campagne (machine chargée), puis tué quand il est rejoué seul ; les statistiques
exportées après ce rejeu (`mutmut export-cicd-stats`) donnent 4 975 éliminés
et 0 suspect, et la preuve `deep` a été reproduite à partir d'elles sur l'arbre
propre.

## Équivalences invoquées

Aucune équivalence n'est prouvée formellement. Deux familles se vérifient dans
la documentation des bibliothèques : `dtype=None` signifie le type flottant par
défaut de numpy, et `index=None` de `to_csv` est traité comme faux. La tolérance
`>=` 1e-6 de `_check_ratios` est inatteignable en arithmétique binaire (la
somme moins un est un multiple de 2⁻⁵², jamais égal à 1e-6). Les autres lignes
du tableau restent des hypothèses de lecture.
