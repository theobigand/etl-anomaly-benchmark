# Mutations du code scientifique

La campagne porte sur les modules de `src/etl_benchmark` qui calculent un
résultat : chargement, découpage, métriques, pipeline, registre, générateur
synthétique et détecteurs (`quality/`). Elle utilise mutmut 3.8.0 et les tests
qui exercent ces modules ; les tests qui contrôlent des fichiers archivés
(filiation, tableaux du manuscrit, CLI en sous-processus) ne sont pas lancés
pour chaque mutant. `config.py`, `logging_setup.py`, `__main__.py` et les
fichiers `__init__.py` ne sont pas mutés. Les scripts de `experiments/` ont
une mesure séparée, plus bas.

Résultat : 1824 mutants éliminés sur 1900, soit **96,00 %**, sans mutant
ignoré, expiré, en erreur ou sans test. La première campagne, limitée à
`metrics.py`, donnait 86/97 (88,66 %) ; élargie aux autres modules sans test
supplémentaire, elle tombait à 1323/1775 (74,5 %).

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

Les 76 mutants restants ne sont pas retirés du dénominateur et aucun n'a été
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

## Scripts d'`experiments/` (mesure de référence, hors porte)

Une campagne séparée a été lancée le 15 octobre 2026 sur les dix scripts :
4 666 mutants, 1 136 tués (**24,3 %**), 882 survivants, 742 sans test et 6
expirés. Elle n'entre pas dans `make verify-deep`, qui exige 95 % et porterait
sur un périmètre où ce seuil n'est pas atteint. `tests/conftest.py` charge
désormais les scripts sous le nom `experiments.<script>`, ce qui permet à
mutmut de relier chaque fonction à ses tests.

| Script | Tués | Survivants | Sans test | Expirés |
| --- | --- | --- | --- | --- |
| `check_mutation.py` | 47 | 7 | 0 | 0 |
| `fetch_cardio.py` | 0 | 0 | 60 | 0 |
| `generate_synthetic.py` | 20 | 75 | 0 | 0 |
| `provenance.py` | 154 | 85 | 0 | 2 |
| `run_benchmark.py` | 108 | 68 | 272 | 0 |
| `run_curves.py` | 217 | 235 | 0 | 0 |
| `run_severity.py` | 42 | 163 | 123 | 0 |
| `run_synthetic_benchmark.py` | 210 | 102 | 287 | 2 |
| `verification_report.py` | 208 | 94 | 0 | 0 |
| `verify_real.py` | 130 | 53 | 0 | 2 |

Les mutants « sans test » sont dans des fonctions que seuls les tests en
sous-processus (`test_cli_smoke.py`) exécutent : la couverture que mutmut
observe ne les voit pas. Pour refaire la mesure, ajouter `"experiments"` à
`source_paths`, `"experiments/*.py"` à `only_mutate`, retirer les `--ignore`
des tests de scripts et ajouter `"environment.yml"` à `also_copy`, puis lancer
`mutmut run "experiments*"` (environ cinq minutes). Cette mesure n'a pas été
analysée mutant par mutant.

## Limites

- Les scripts de `experiments/` ne sont pas dans la porte de 95 % ; leur
  mesure de référence est ci-dessus.
- Un mutant éliminé par le test d'empreinte du jeu de référence prouve que le
  jeu publié ne change pas, pas que chaque paramètre a le bon sens
  statistique ; les moments et les bornes sont contrôlés à part.
- La campagne complète dure environ neuf minutes sur cette machine.
