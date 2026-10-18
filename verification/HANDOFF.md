# Reprise de la mission de vérification

État détaillé dans `milestones.json` (jalons M00 à M13) et `remediation.md`
(anomalies 38 à 49, point de reprise de la remédiation post-audit).

- Environnement : `export PATH=/Users/theo/miniconda3/envs/etl-benchmark/bin:$PATH` (python 3.11.17). Le typage se vérifie dans un venv avec `pip install -e ".[dev]" mypy==2.4.0 pandas-stubs==3.0.5.260914`.
- Branche : `verify/m12-manuscript-consistency`, PR brouillon n° 37 (non fusionnée). La protection de `main` n'est pas appliquée.
- Certification : `make verify-release` rend CERTIFIED (non attesté, local) quand toutes les preuves de `release_policy.json` (fast, deep, faults, real, tools, types, reproduction) existent pour un commit dont le code n'a pas changé depuis. Après tout commit qui touche du code, relancer `make verify-fast verify-tools verify-types verify-faults verify-real verify-deep verify-reproduce verify-release`, puis `python -m verification.claims archive --id <id> --platform "<machine>"` et mettre à jour le manuscrit. Voir `certification.md`.
- Toute modification de `src/` ou de `experiments/*.py` hors des fonctions de provenance non scientifiques change l'empreinte scientifique v2 : rejouer les archives (voir `report.md`, `outputs.md`).
- Reste à faire avec l'accord du propriétaire : exécuteur auto-hébergé pour REAL (`real_evidence.md`, contrôle préalable `python -m verification.real_preflight`, script `runner/provision_runner.sh`), application de la protection de `main` (`branch_protection_proposal.md`), fusion de la PR.
