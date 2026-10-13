# État des vérifications

Le dépôt contient le pipeline Python (`src/etl_benchmark`), les expériences
(`experiments`) et le manuscrit. Le résultat global reste **INCOMPLETE** : les
tests exécutés passent, mais les seuils de couverture et de mutation ne sont
pas atteints. Le suivi chronologique a maintenant un premier protocole testé ;
son évaluation sur données réelles, les modèles profonds et la montée en charge
restent ouverts.

## Point de départ et corrections

Au départ, 76 tests et Ruff tournaient dans la CI. Il n'y avait ni mesure de
couverture par branche, ni campagne de mutation, ni contrôle séparé des CSV
réels. Les fichiers de données étaient disponibles sur cette machine.

Les tests ajoutés ont mis en évidence plusieurs erreurs : une copie
synthétique pouvait se retrouver des deux côtés du découpage, la déduplication
regardait les données avant ce découpage, une série de stratification réordonnée
était utilisée par position, et un taux d'injection nul créait encore des
anomalies. Nous avons aussi corrigé la normalisation silencieuse des labels
manquants, les métriques non définies et l'acceptation de sorties de détecteur
mal alignées. Une colonne d'entraînement entièrement vide ou infinie pouvait
aussi produire des scores nuls dans les règles statistiques ; ces entrées sont
maintenant rejetées. Les cas de régression sont dans `tests/test_scientific_contracts.py`,
`test_split.py`, `test_dataset_contract.py`, `test_metric_contract.py` et
`test_detector_protocol.py` et `test_adverse_schemas.py`. Chaque correctif a été précédé d'un échec ciblé,
puis contrôlé avec le même test après modification.

Les expériences synthétiques ont été relancées après ces changements. Les
trois benchmarks réels ont ensuite été rejoués avec cinq graines chacun. Les
quatre tableaux du manuscrit sont comparés aux CSV archivés par
`test_publication_tables.py` ; ce contrôle a révélé neuf arrondis à corriger.
Les figures et le PDF ont été reconstruits. Le découpage chronologique et le
suivi par fenêtres ont leurs propres tests ; ils ne changent pas les métriques
du benchmark stratifié.

## Résultats des commandes

| Commande | Résultat | Détail |
| --- | --- | --- |
| `make verify-fast` | Échec | 163 tests réussis, 2 tests réels exclus ; couverture incomplète. |
| `make verify-deep` | Échec | 74 mutants éliminés sur 97 dans `metrics.py` ; seuil de 95 % non atteint. |
| `make verify-real` | Réussite locale | 2 tests et contrôle des trois CSV présents. |
| `python verification/scaling.py` | Réussite locale | 27 mesures sur trois tailles, hors FAST. |
| `make verify-all` | Échec | Reprend les échecs de FAST et DEEP. |

FAST mesure **962/1324 lignes (72,66 %)** et **173/262 branches (66,03 %)**.
Les scripts `fetch_cardio.py`, `generate_synthetic.py` et `run_severity.py`
ne sont pas parcourus par FAST ; `run_curves.py` l'est peu. Le détail par
fichier est dans le profil généré `verification/profile.json` et
`coverage.json`. Aucune ligne
ni branche n'est exclue.

La campagne de mutation n'a porté que sur `src/etl_benchmark/metrics.py` avec
mutmut 3.8.0 : 97 mutants produits, 74 éliminés, 23 survivants, aucun cas
classé sans test, ignoré, expiré ou en erreur. Le taux mesuré est **76,29 %**
sur ce seul module. Le reste du code n'a pas de score de mutation. Le profil
indique donc `NOT_RUN` pour la portée complète ; sa valeur numérique zéro
n'est pas une mesure de performance.

## Ce que les contrôles couvrent

Les tests unitaires, de contrat, d'intégration, de propriété et de CLI
utilisent de petits jeux construits dans des répertoires temporaires. FAST ne
lit pas les CSV de recherche et ne demande pas d'accès réseau. Les deux tests
sur données complètes sont marqués `real` et passent par `make verify-real`.
Un contrôle d'interdiction du réseau dans les tests manque encore.

Le vérificateur échoue lorsqu'un rapport de couverture manque, lorsqu'aucun
test n'a été exécuté ou lorsque les résultats de mutation sont incohérents.
Le test de filiation compare les fichiers archivés au manifeste et vérifie que
les enregistrements d'expérience correspondent au code scientifique courant.
Les essais de mutation ont conduit à renforcer les tests sur la dimension des
vecteurs, les longueurs incompatibles et l'absence de prédictions positives.
Un essai local de croissance sur 100, 300 et 900 lignes est décrit dans
`scaling.md`. Les tests contrôlent les étapes chronométrées et la taille des
entrées, sans seuil fixe sur la durée.

Les tests de panne d'écriture, de redémarrage et plusieurs schémas extrêmes
restent à faire. Le pipeline s'exécute séquentiellement ; il n'a ni
API, ni interface interactive, ni état partagé entre processus. Un contrôle de
types sera utile avant les nouveaux modèles ; aucun outil de typage n'est
encore configuré. Les seuils numériques des durées ne sont pas utilisés comme
critères de correction.

## Données, résultats et CI

Le contrôle local retrouve 283 726 lignes et 473 fraudes après déduplication
pour Credit Card Fraud, 3 276 lignes et 1 998 positives pour Water Quality,
1 822 lignes et 175 anomalies pour Cardio. Les sommes de contrôle et les
commandes de rejeu sont conservées dans `verification/evidence/manifest.json`.
Les CSV bruts ne sont pas archivés ici. Leur source exacte et leurs conditions
d'usage demandent encore une vérification avant publication.

La CI lance FAST et conserve ses rapports. Le job est actuellement rouge à
cause de la couverture. Les règles de protection de la branche distante n'ont
pas été inspectées. DEEP et REAL restent des commandes locales ; elles ne
bloquent pas encore une publication distante.

## Travail restant

Il faut couvrir les chemins manquants, examiner les 23 mutants survivants puis
étendre la mutation à tous les modules concernés. Il manque également des
tests de panne et de schéma défavorable, un protocole temporel séparé du
benchmark stratifié, une évaluation temporelle sur données réelles, les
détecteurs profonds et une étude de coût plus large dans un environnement
contrôlé.
Le tableau de suivi `verification/issues.md` relie ces
travaux aux tickets. Aucun résultat de ce rapport ne valide une livraison
finale du mémoire.

## Reproduire les vérifications

```bash
conda env update -f environment.yml --prune
conda activate etl-benchmark
make verify-fast
python -m pip install -e '.[deep]'
make verify-deep
make verify-real
python experiments/run_synthetic_benchmark.py --seeds 42 1 2 3 4
python experiments/run_severity.py
python experiments/run_curves.py --seed 42
python experiments/run_benchmark.py --dataset credit_card
python experiments/run_benchmark.py --dataset water_quality
python experiments/run_benchmark.py --dataset cardio
make verify-scale
latexmk -pdf -interaction=nonstopmode -halt-on-error -output-directory=paper paper/main.tex
```
