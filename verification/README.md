# Vérifier le benchmark

Utiliser l'environnement défini par `environment.yml`. Les commandes ci-dessous
se lancent à la racine du dépôt.

| Commande | Ce qu'elle fait |
| --- | --- |
| `make verify-fast` | Ruff, tests hors données réelles, couverture des lignes et branches. |
| `make verify-deep` | Mutations de `src/etl_benchmark` avec mutmut (environ six minutes) ; seuil de 95 %. |
| `make verify-faults` | Quatorze défauts scientifiques appliqués à une copie temporaire ; chacun doit faire échouer un test prévu (environ une minute). |
| `make verify-real` | Tests sur les trois CSV locaux et contrôle de leurs tailles, labels et sommes de contrôle. |
| `make verify-scale` | Étude locale de croissance sur trois tailles ; aucune limite de temps n'est imposée à FAST. |
| `make verify-all` | Lance FAST, DEEP, les défauts introduits et REAL, et conserve leurs échecs. |

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

Pour changer une mesure publiée, commencer par un cas qui montre l'erreur,
exécuter le test avant la correction, puis relancer le même test après. Lancer
ensuite le gate concerné et refaire les tables ou figures touchées. Les tests
sur durées ne doivent pas dépendre d'un nombre précis de secondes.

Les résultats actuels et les travaux encore ouverts sont dans `report.md` et
`issues.md`. FAST passe sur l'ensemble mesuré ; DEEP dépasse son seuil sur
`src/etl_benchmark` mais ne couvre pas `experiments/`. Le statut général reste
**INCOMPLETE**.
