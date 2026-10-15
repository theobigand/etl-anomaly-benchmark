# État des vérifications

Le dépôt contient le pipeline Python (`src/etl_benchmark`), les expériences
(`experiments`) et le manuscrit. Le résultat global reste **INCOMPLETE** : les
tests exécutés et le seuil de couverture passent et la mutation du code de
`src/etl_benchmark` dépasse 95 %, mais les scripts d'`experiments/` n'ont pas
de campagne de mutation. Le suivi chronologique a un premier protocole testé ;
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
quatre tableaux principaux du manuscrit sont comparés aux CSV archivés par
`test_publication_tables.py` ; ce contrôle a révélé neuf arrondis à corriger.
Les figures et le PDF ont été reconstruits. Le découpage chronologique et le
suivi par fenêtres ont leurs propres tests ; ils ne changent pas les métriques
du benchmark stratifié.
Une comparaison supplémentaire emploie une contamination fixe de 0,02 pour
les détecteurs classiques sur les trois jeux réels. Elle réutilise les mêmes
partitions, mais demeure exploratoire : sa valeur a été fixée après lecture
des résultats du protocole principal. Les fichiers correspondants sont
archivés séparément et leurs chiffres sont rapprochés du manuscrit par un test.

## Résultats des commandes

| Commande | Résultat | Détail |
| --- | --- | --- |
| `make verify-fast` | Réussite locale | 447 tests réussis, 2 tests réels et 14 essais de défauts exclus ; lignes et branches couvertes. |
| `make verify-deep` | Réussite locale | 1824 mutants éliminés sur 1900 dans `src/etl_benchmark` (96,00 %) ; les scripts d'`experiments/` ne sont pas mutés. |
| `make verify-faults` | Réussite locale | 14 défauts introduits dans une copie temporaire, tous détectés par un test prévu. |
| `make verify-real` | Réussite locale | 2 tests et contrôle des trois CSV présents. |
| `python verification/scaling.py` | Réussite locale | 27 mesures sur trois tailles, hors FAST. |
| `make verify-all` | Réussite locale sur `src/` | DEEP ne couvre pas `experiments/` ; le statut reste INCOMPLETE. |

FAST mesure **1466/1466 lignes et 300/300 branches (100 % chacune)**.
La mesure inclut désormais les commandes lancées en sous-processus. Les
scripts `fetch_cardio.py`, `generate_synthetic.py` et l'entrée principale
sont désormais parcourus par FAST avec des données construites localement. Le détail par
fichier est dans le profil généré `verification/profile.json` et
`coverage.json`. Aucune ligne
ni branche n'est exclue.

La campagne de mutation porte sur les modules de `src/etl_benchmark` qui
calculent un résultat (mutmut 3.8.0) : 1900 mutants produits, 1824 éliminés,
76 survivants, aucun cas classé sans test, ignoré, expiré ou en erreur. Le
taux mesuré est **96,00 %** sur ce périmètre. Elle avait commencé à 88,66 %
sur `metrics.py` seul et à 74,5 % une fois élargie sans nouveaux tests.
`mutation_notes.md` classe les survivants (états intermédiaires, `dtype`
équivalents, noms internes). Les scripts d'`experiments/` n'ont pas de score
de mutation ; le profil indique donc `NOT_RUN` pour la portée complète et sa
valeur numérique zéro n'est pas une mesure.

## Rejeu du 15 octobre 2026

Tous les essais archivés ont été rejoués sur le code courant (banc synthétique,
sévérité, courbes, trois jeux réels, trois calibrages fixes, étude de
croissance). Toutes les métriques de détection, les courbes, les scores par
type et les partitions exactes (contenu des archives décompressées) sont
identiques à l'archive précédente (écart inférieur à 1e-9). Seuls les temps de
calcul (`detect_s`) et l'allocation Python mesurée par l'étude de croissance
varient. Les enregistrements des essais gardent maintenant les détecteurs non exécutés avec leur raison (`not_run`) et les jeux
demandés mais absents (`skipped_datasets`). Les deux tableaux du manuscrit qui
affichent des temps et le paragraphe sur la montée en charge ont été mis à
jour ; les figures sont identiques octet pour octet.

## Ce que les contrôles couvrent

Les tests unitaires, de contrat, d'intégration, de propriété et de CLI
utilisent de petits jeux construits dans des répertoires temporaires. FAST ne
lit pas les CSV de recherche et ne demande pas d'accès réseau. Les deux tests
sur données complètes sont marqués `real` et passent par `make verify-real`.
Les connexions réseau sont bloquées dans le processus pytest et, par un
module chargé au démarrage, dans les commandes Python qu'il lance.

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
Les CSV bruts ne sont pas archivés ici. Le CSV Water Quality correspond au
miroir annoncé, et la conversion du fichier ADBench reproduit le CSV Cardio.
`make verify-real` compare maintenant les copies locales aux valeurs attendues
du manifeste. La révision du téléchargement Credit Card et les droits propres
au jeu Cardio restent non établis pour une redistribution brute.

La CI lance FAST et conserve ses rapports. Le profil passe localement sur
cette révision ; le résultat distant reste à vérifier. Les règles de protection de la branche distante n'ont
pas été inspectées. DEEP et REAL restent des commandes locales ; elles ne
bloquent pas encore une publication distante.

## Travail restant

Il faut étendre la mutation aux scripts d'`experiments/` et revoir les 76
survivants si un module change. Il manque également des
tests de panne et de schéma défavorable, une évaluation temporelle sur données réelles, les
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
