# Reprise de la mission de vérification

État détaillé dans `milestones.json` (source de vérité). Ce fichier donne le point de reprise.

- Environnement : `export PATH=/Users/theo/miniconda3/envs/etl-benchmark/bin:$PATH` (python 3.11.17).
- Jalon courant : M00 terminé côté mesure (FAST : 561 tests, 100 % lignes et branches). Suite : M01.
- Piège : toute modification de `src/` ou `experiments/*.py` change l'empreinte de provenance et fait
  échouer `tests/test_artifact_lineage.py` jusqu'au rejeu des archives. Regrouper ces modifications,
  rejouer une seule fois (`python verification/archive_evidence.py`).
- Ne pas pousser ni fusionner sans accord.
