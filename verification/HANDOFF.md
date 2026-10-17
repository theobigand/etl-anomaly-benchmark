# Reprise de la mission de vérification

État détaillé dans `milestones.json` (source de vérité).

- Environnement : `export PATH=/Users/theo/miniconda3/envs/etl-benchmark/bin:$PATH` (python 3.11.17).
- Jalons M00 à M13 terminés sur la chaîne de branches `verify/m00-baseline` ... `verify/m12-manuscript-consistency` (la pointe contient tout). Rien n'est fusionné ni poussé.
- Certification : `make verify-release` rend CERTIFIED (non attesté, local) quand toutes les preuves de `release_policy.json` (fast, deep, faults, real, tools, types, reproduction) existent pour le commit courant propre. Après tout nouveau commit, relancer `make verify-fast verify-tools verify-types verify-faults verify-real verify-deep verify-reproduce verify-release`. Voir `certification.md`.
- Toute modification de `src/` ou de `experiments/*.py` hors barrières de vérification change l'empreinte scientifique v2 : rejouer les archives (voir `report.md`).
- Reste à faire avec l'accord de l'utilisateur : pousser, vérifier la CI distante et la protection de branche.
