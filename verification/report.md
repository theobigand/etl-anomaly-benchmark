# État des vérifications

Le dépôt contient le pipeline Python (`src/etl_benchmark`), les expériences
(`experiments`) et le manuscrit. Le résultat global reste **INCOMPLETE** : les
tests exécutés et le seuil de couverture passent et la mutation du code de
`src/etl_benchmark` et d'`experiments/` dépasse 95 %. Restent ouverts le
modèle LSTM, l'évaluation chronologique sur données réelles, l'étude de coût
dans un environnement contrôlé et les points de la section « Travail restant ».
Le suivi chronologique a un premier protocole testé ;
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
| `make verify-fast` | Réussite locale | 763 tests réussis, 3 tests réels et 23 essais de défauts exclus ; lignes et branches couvertes. |
| `make verify-deep` | Réussite locale | 4 626 mutants éliminés sur 4 732 (97,76 %) dans `src/etl_benchmark` et `experiments/` ; 106 survivants, dont 1 propre à macOS. |
| `make verify-faults` | Réussite locale | 23 défauts introduits dans une copie temporaire, tous détectés par un test prévu. |
| `make verify-real` | Réussite locale | 2 tests et contrôle des trois CSV requis ; échoue si l'un manque ou si le registre est vide. |
| `python verification/scaling.py` | Réussite locale | 27 mesures sur trois tailles, hors FAST. |
| `make verify-all` | Réussite locale | FAST, DEEP, défauts introduits et REAL passent ; le statut reste INCOMPLETE (travail restant ci-dessous). |

FAST mesure **1531/1531 lignes et 320/320 branches (100 % chacune)**. Le code de
vérification de `verification/` est mesuré à part (`make verify-tools` : 732/732
lignes et 218/218 branches).
La mesure inclut désormais les commandes lancées en sous-processus. Les
scripts `fetch_cardio.py`, `generate_synthetic.py` et l'entrée principale
sont désormais parcourus par FAST avec des données construites localement. Le détail par
fichier est dans le profil généré `verification/profile.json` et
`coverage.json`. Aucune ligne
ni branche n'est exclue.

La campagne de mutation porte sur les modules de `src/etl_benchmark` qui
calculent un résultat et sur les dix scripts de `experiments/` (mutmut 3.8.0) :
4 732 mutants produits, 4 626 éliminés, 106 survivants, aucun cas classé sans
test, ignoré, expiré ou interrompu. Le taux mesuré est **97,76 %**, dont 95,76 %
sur le calcul scientifique seul et 98,90 % sur l'orchestration et les scripts
(voir `mutation_notes.md`). Elle avait commencé à 88,66 % sur
`metrics.py` seul, à 74,5 % une fois élargie à `src/` sans nouveaux tests et à
24,3 % sur les scripts. `mutation_notes.md` classe les survivants par lecture des
diffs (valeurs par défaut de bibliothèques, noms internes) ; ce classement est
une hypothèse, pas une preuve. Le profil
généré par FAST garde un champ de mutation à zéro : il signifie « non lancé
par FAST », pas un score nul ; le résultat de DEEP est dans ce rapport.

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
du manifeste. Le fichier Credit Card a la taille de la version 3 de la fiche Kaggle
(mars 2018) ; son hash n'a pas pu être comparé à un nouveau téléchargement.
Cardio vient de l'UCI sous licence CC BY 4.0 (`data/README.md`).

La CI lance FAST et conserve ses rapports. Le profil passe localement sur
cette révision ; le résultat distant reste à vérifier. Les règles de protection de la branche distante n'ont
pas été inspectées. DEEP et REAL restent des commandes locales ; elles ne
bloquent pas encore une publication distante.

## Travail restant

Il faut revoir les 106 survivants si un module change. Il manque également des
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

## Ajouts de la mission de renforcement (octobre 2026)

| Élément | Où |
| --- | --- |
| REAL échoue si les trois jeux requis ne passent pas tous | `experiments/verify_real.py` |
| La barrière de mutation refuse comptes invalides, campagne interrompue, mutants sans test ou ignorés | `experiments/check_mutation.py` |
| Enveloppe de preuve validée pour FAST, DEEP, FAULTS, REAL | `verification/evidence_schema.py` |
| Certification de version (`make verify-release`) : CERTIFIED, INCOMPLETE ou REJECTED, rapport « local, non attesté » | `verification/release.py` |
| Empreinte scientifique v2 (sans les barrières de vérification) et filiation des archives historiques | `experiments/provenance.py`, `verification/lineage.py`, `evidence/lineage.json` |
| Verrou d'environnement (`make lock`) | `verification/environment/` |
| Reproductibilité par niveaux | `reproducibility.md` |
| Couverture du code de vérification (`make verify-tools`) | 732/732 lignes, 218/218 branches |
| Typage : `verification/` propre, code scientifique sans nouvelle erreur (`make verify-types`) | `check_types.py`, `typing_baseline.txt` |
| Chiffres cités par le manuscrit | `claims.json`, `tests/test_manuscript_claims.py` |

Le statut général reste **INCOMPLETE** : les archives des expériences datent d'un
arbre de travail modifié et d'une empreinte de première génération ; seul
Cardio a été rejoué avec le code actuel (identique). Un rejeu complet sur une
révision propre est nécessaire avant toute certification.
