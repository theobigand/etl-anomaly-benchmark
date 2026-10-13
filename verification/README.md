# Vérifier le benchmark

Utiliser l'environnement défini par `environment.yml`. Les commandes ci-dessous
se lancent à la racine du dépôt.

| Commande | Ce qu'elle fait |
| --- | --- |
| `make verify-fast` | Ruff, tests hors données réelles, couverture des lignes et branches. |
| `make verify-deep` | Mutations de `metrics.py` avec mutmut ; seuil de 95 %. |
| `make verify-real` | Tests sur les trois CSV locaux et contrôle de leurs tailles, labels et sommes de contrôle. |
| `make verify-scale` | Étude locale de croissance sur trois tailles ; aucune limite de temps n'est imposée à FAST. |
| `make verify-all` | Lance les trois commandes et conserve leurs échecs. |

FAST produit `coverage.json`, `experiments/results/pytest.xml`,
`experiments/results/verification_fast.json` et `verification/profile.json`.
Le profil est reconstruit depuis `profile.template.json` avec la révision et
les dénominateurs du moment ; le fichier produit reste hors Git. La CI conserve
ces rapports en pièces jointes. Les données réelles ne sont pas nécessaires à
FAST. Installer l'outil optionnel avec `python -m pip install -e '.[deep]'`
avant DEEP.

Les trois CSV de recherche ne sont pas versionnés. Les tables, figures et
enregistrements des essais conservés sont dans `evidence/`, avec leur manifeste.
Les sommes de contrôle de ce manifeste servent aux tests de traçabilité ; il
n'est pas nécessaire de les recopier dans les pages de lecture.

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
- `test_scaling_study.py` vérifie les étapes chronométrées et la taille des
  entrées. `scaling.md` décrit l'essai local de croissance.

Pour changer une mesure publiée, commencer par un cas qui montre l'erreur,
exécuter le test avant la correction, puis relancer le même test après. Lancer
ensuite le gate concerné et refaire les tables ou figures touchées. Les tests
sur durées ne doivent pas dépendre d'un nombre précis de secondes.

Les résultats actuels et les travaux encore ouverts sont dans `report.md` et
`issues.md`. FAST et DEEP échouent toujours à leurs seuils ; le statut général
reste **INCOMPLETE**.
