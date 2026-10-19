# Vérifier le benchmark

Utiliser l'environnement défini par `environment.yml`. Les commandes ci-dessous
se lancent à la racine du dépôt.

| Commande | Ce qu'elle fait |
| --- | --- |
| `make verify-fast` | Ruff, tests hors données réelles, couverture des lignes et branches. |
| `make verify-deep` | Mutations de `src/etl_benchmark` et `experiments/` avec mutmut (environ vingt-cinq minutes) ; seuil de 95 %. |
| `make verify-faults` | Vingt-trois défauts scientifiques appliqués à une copie temporaire ; chacun doit faire échouer un test prévu (environ deux minutes). |
| `make verify-real` | Tests sur les trois CSV locaux et contrôle de leurs tailles, labels et sommes de contrôle. |
| `make verify-scale` | Étude locale de croissance sur trois tailles ; aucune limite de temps n'est imposée à FAST. |
| `make verify-all` | Lance FAST, DEEP, les défauts introduits et REAL, et conserve leurs échecs. |
| `make verify-tools` | Couverture ligne et branche de `verification/` (100 % exigé), à part de FAST. |
| `make verify-types` | mypy (version épinglée dans la CI ; à lancer avec mypy et pandas-stubs installés dans l'environnement actif, sinon le résultat diffère) : `verification/` sans erreur, le reste sans nouvelle erreur par rapport à `typing_baseline.txt`. |
| `real_evidence.md` | Procédure et frontière de confiance de la preuve REAL à distance (exécuteur auto-hébergé, archives à liste blanche). |
| `make verify-reproduce` | Reproduction contrôlée de cardio (archive, deux essais, environnement verrouillé, sensibilité) et preuve `reproduction`. |
| `make verify-release` | Réunit les preuves exigées par `release_policy.json` (voir `certification.md`) et décide CERTIFIED, INCOMPLETE ou REJECTED ; le rapport est produit localement et n'est pas une attestation indépendante. |
| `make lock` | Enregistre les paquets conda et pip exacts de l'environnement actif. |
| `python -m verification.reproduce` | Rejoue Cardio et classe l'accord (voir `reproducibility.md`). |

FAST produit `coverage.json`, `experiments/results/pytest.xml`,
`experiments/results/verification_fast.json` et `verification/profile.json`.
La configuration coverage suit aussi les processus Python lancés par les
tests de commandes ; leurs lignes et branches sont réunies dans le rapport.
Le profil est reconstruit depuis `profile.template.json` avec la révision et
les dénominateurs du moment ; le fichier produit reste hors Git. La CI conserve
ces rapports en pièces jointes. Les données réelles ne sont pas nécessaires à
FAST. Installer l'outil optionnel avec `python -m pip install -e '.[deep]'`
avant DEEP.

Les trois CSV de recherche ne sont pas versionnés. Les tables, figures et
enregistrements des essais conservés sont dans `evidence/`, avec leur manifeste.
Les archives `split_ids_*.json.gz` des jeux réels contiennent les positions
train, validation et test après déduplication pour chaque graine, ainsi que
le sous-échantillon d'apprentissage lorsqu'il est plafonné.
Les fichiers `fixed_benchmark_*.csv` documentent séparément le préréglage
de contamination 0,02. Les archives `fixed_split_ids_*.json.gz` sont
comparées aux partitions du protocole principal par un test ; les mêmes
observations sont ainsi évaluées avec les deux seuils.
Les sommes de contrôle de ce manifeste servent aux tests de traçabilité ; il
n'est pas nécessaire de les recopier dans les pages de lecture.
`function_matrix.md` recense les fonctions, leurs tests principaux et les
lacunes connues. Les jeux construits dans `tests/conftest.py` retournent des
copies indépendantes ; le même fichier bloque les connexions réseau dans le
processus pytest. Un module chargé au démarrage des sous-processus Python
applique le même blocage aux commandes d'expérience exécutées par les tests.
Ce contrôle porte sur les processus Python lancés depuis pytest.

## Points contrôlés

- `test_scientific_contracts.py` vérifie que les copies synthétiques ne passent
  pas d'une partition à l'autre et que la déduplication ne regarde pas le test.
- `test_detector_protocol.py` et `test_metric_contract.py` contrôlent les
  entrées des détecteurs, l'alignement des sorties et les définitions des
  mesures, y compris les cas où une mesure est indéfinie.
- `test_adverse_schemas.py` couvre les colonnes d'entraînement vides, les
  infinis, les colonnes absentes et les colonnes constantes.
- `test_cli_smoke.py` exécute quatre commandes sur de petits fichiers.
  `test_artifact_lineage.py` et `test_publication_tables.py` relient l'archive
  aux quatre tableaux du manuscrit.
- `test_temporal_protocol.py` traite séparément les partitions chronologiques
  et les alertes par fenêtre. Sa méthode est décrite dans `temporal.md`.
- `test_fault_matrix.py` applique des défauts scientifiques à une copie
  temporaire et exige qu'un test prévu échoue (`fault_matrix.md`).
  `test_verification_policy.py` interdit les skips hors tests `real`, les
  exclusions de couverture, les erreurs avalées et les mocks des bibliothèques
  de calcul.
- `test_scaling_study.py` vérifie les étapes chronométrées et la taille des
  entrées. `scaling.md` décrit l'essai local de croissance.

## Prêt et terminé

Avant de commencer un changement qui touche un résultat :

- le comportement attendu et son sens scientifique tiennent en une phrase ;
- le test qui devra échouer est nommé, sur de petites données générées ;
- aucun CSV réel n'est nécessaire pour ce test.

Le changement est terminé quand :

- le test a d'abord échoué pour la bonne raison, puis passe avec la même
  assertion ;
- `make verify-fast` passe ;
- `make verify-deep` et `make verify-faults` passent si le code scientifique
  ou une protection a changé ;
- les résultats archivés et le manuscrit sont rejoués ensemble si un chiffre
  publié change (`python verification/archive_evidence.py` après les
  commandes de `report.md`) ;
- ce qui reste non vérifié est écrit dans `issues.md`.

Exemple pour un défaut de découpage :

```bash
pytest tests/test_split.py -k rare_class    # échoue : le défaut est reproduit
# corriger src/etl_benchmark/split.py
pytest tests/test_split.py -k rare_class    # passe : même assertion
make verify-fast
```

Sont admis sans test préalable : la documentation, la mise en forme, un
refactor pur (un test de caractérisation vert existe d'abord) et une
exploration jetable. Un changement de comportement exécutable sans test
préalable se signale comme exception dans le message de validation.

## Évolution du schéma et cas limites

- Avec `pipeline.detect`, les colonnes d'évaluation doivent être les mêmes que
  celles d'ajustement, dans le même ordre ; sinon l'appel échoue.
- Un détecteur appelé directement lit ses variables par nom : une colonne en
  plus ou un ordre différent ne change aucun score, une colonne requise absente
  est une erreur.
- Une colonne d'entraînement vide, une valeur infinie ou une colonne non
  numérique est une erreur ; une colonne constante donne des sorties finies.
- Un type d'anomalie sans ligne dans une partition donne `NaN` dans les
  tableaux par type, jamais une colonne absente. Un jeu demandé mais absent est
  listé dans `skipped_datasets` de l'enregistrement, un détecteur non exécuté
  dans `not_run` avec sa raison.
- Une classe trop rare pour être stratifiée fait échouer le découpage, sans
  repli vers un tirage aléatoire.

Cas non résolus : un schéma qui change en cours de flux réel n'est pas géré (le
benchmark lit un fichier figé) ; les horodatages invalides sont rejetés par le
découpage chronologique mais pas testés de bout en bout dans les scripts
d'expérience ; les classes à une seule observation positive sont refusées au
lieu d'être traitées.

## Transformations permises et interdites

Les propriétés de `test_properties.py` et les tests de lot s'appuient sur
cette liste.

| Transformation | Effet attendu |
| --- | --- |
| Permuter les lignes d'un lot évalué (détecteurs par ligne) | Les scores suivent les lignes ; rien d'autre ne change. |
| Évaluer une ligne seule ou dans un lot | Même score (aucune statistique du lot). |
| Renuméroter l'index | Les sorties portent le nouvel index ; les valeurs sont les mêmes. |
| Permuter les lignes d'un jeu à horodatage | Les partitions chronologiques et les fenêtres sont les mêmes (l'ordre vient du temps). |
| Changer l'ordre des colonnes entre ajustement et évaluation | Interdit : rejeté par `detect`. |
| Changer les labels du test | Interdit d'influencer le seuil ou l'ajustement ; seules les métriques changent. |
| Modifier une ligne future | Ne change aucune fenêtre ni aucun score antérieur. |

`manuscript_check.md` consigne la relecture factuelle du manuscrit contre le
code et les archives, avec les corrections apportées.

Pour changer une mesure publiée, commencer par un cas qui montre l'erreur,
exécuter le test avant la correction, puis relancer le même test après. Lancer
ensuite le gate concerné et refaire les tables ou figures touchées. Les tests
sur durées ne doivent pas dépendre d'un nombre précis de secondes.

Les résultats actuels et les travaux encore ouverts sont dans `report.md` et
`issues.md`. FAST passe sur l'ensemble mesuré ; DEEP dépasse son seuil sur
`src/etl_benchmark` et `experiments/` (97,75 % au run `local-561ac38`). Le statut
général est **CERTIFIED en local, non attesté**, et **CERTIFIED en CI, non attesté indépendamment** (run 39112662862, REAL
hébergé à partir de téléchargements publics vérifiés) ; voir `certification.md`.
