# Suivi de la remédiation post-audit (issues #38 à #49)

Ce fichier est le point de reprise de la remédiation. Une issue n'est fermée
qu'après exécution des contrôles listés ici, sur le commit indiqué.

| Issue | État | Commits | Preuves |
| --- | --- | --- | --- |
| #38 reproduction : niveau demandé NOT_RUN | terminé | `1d0278a`, `8df5b71` | RED : 6 tests de `tests/test_reproduce.py` en échec (pas de champ `outcome`, plantage sans rapport) ; GREEN : sortie 1 et `outcome` INCOMPLETE/FAIL pour tout niveau obligatoire qui n'est pas `PASS`, sensibilité jamais décisive ; CI Linux : `release-reproduce` réussi |
| #39 contrat de certification | terminé | `14fc288`, `6d4ba88`, `ffa02b2` | RED : tests de politique, des preuves `tools`/`types`/`reproduction` et de release ; GREEN : sept preuves exigées (`release_policy.json`, `certification.md`) ; la CI a révélé trois défauts corrigés (contexte d'exécution de FAST, couverture dépendante de mypy, partitions) ; verdict distant INCOMPLETE pour la seule raison REAL |
| #40 environnements scientifiques | terminé | `659d5ab` | RED : 15 tests en échec ; GREEN : versions des quatre paquets et mineure de Python identiques entre preuves, écart au verrou INCOMPLETE, `cross-platform` distingué de `exact-environment` ; CI : `exact-environment` |
| #41 périmètre de mutation | terminé | `540b2fd`, `80b6310` | RED : module absent puis 5 tests en échec ; GREEN : relevé indépendant, 28 fichiers dont 27 mutés ; DEEP local 4 707/4 815, Linux 4 710/4 815 |
| #42 chiffres et manuscrit | terminé | `6e30e9b`, `631b159`, `55ad398`, `e4c5cd4`, `ffa02b2`, `a8644e7` | chiffres liés à un run scellé (`claims.json`, `evidence/runs/local-ffa02b2/`), péremption refusée par la porte de certification, rapport réécrit, chiffres CI copiés de `evidence/ci/39041531141/` |
| #43 provenance de la mesure | terminé | `7526de2` | RED : 24 tests ; GREEN : empreinte de mesure distincte de l'empreinte scientifique (`44faa1f9` inchangée), `scaling.json` archivé laissé `LEGACY` |
| #44 preuve REAL à distance | **ouvert** : aucun exécuteur auto-hébergé (API : `total_count: 0`, 17 oct. 2026) | `30bd929`, `8df5b71`, voir ci-dessous | mécanisme testé ; job `real` durci (branche par défaut, `approved_sha`, venv jetable, jeux liés sans copie), contrôle préalable `verification.real_preflight`, script de provisionnement, procédure `real_evidence.md` ; exécution distante non démontrée |
| #45 reproduction étendue et verrou Linux | terminé | `7d7e6f4`, `8df5b71`, `a8644e7` | verrou Linux à empreintes validé sur un exécuteur propre (cardio : écart 0,0 contre l'essai Linux, 6,5e-5 contre l'archive macOS) ; rejeux locaux des quatre jeux ; rejeux verrouillés de water_quality, credit_card et synthetic en attente |
| #46 protection de `main` | **ouvert** : `AWAITING_OWNER_APPROVAL` | `69054d5` | contextes `test` et `faults` relevés, homonymie levée, charge utile validée, `verification.protection check` en lecture seule ; rien appliqué |
| #47 références externes | terminé | `3fe3505` | 12 entrées vérifiées (`references.md`) ; 12,9 M$ retiré ; AUC 0,5094 confirmée ; auteurs corrigés |
| #48 sorties atomiques | **ouvert** : écriture atomique sur place des CSV/figures non faite | `58556e5`, `80b6310` | enregistrement atomique, sorties hachées, archivage atomique et fermé ; la réécriture des écrivains CSV changerait l'empreinte scientifique et exige un rejeu complet décidé par le propriétaire (`outputs.md`) |
| #49 clôture indépendante | **ouvert** : preuve REAL à distance et protection absentes | voir le commentaire de l'issue | état exact du commit `a8644e7` dans le commentaire |


## Préparation de l'exécuteur REAL (après la clôture initiale)

- Écart de sécurité trouvé : le job `real` pouvait être lancé depuis n'importe
  quelle branche, donc exécuter du code non relu face aux jeux privés. RED :
  `test_the_real_job_runs_only_a_reviewed_revision_from_the_default_branch`.
  Correctif : exécution limitée à la branche par défaut, entrée `approved_sha`
  obligatoire, récupération sans identifiants persistants, environnement virtuel
  jetable, jeux liés depuis `THESIS_DATA_DIR` (sans copie), contrôle préalable
  avant `make verify-real`.
- Nouveau : `verification/real_preflight.py` (lecture seule, 100 % de couverture),
  `verification/runner/provision_runner.sh` (simulation par défaut, aucun jeton).
- Lecture du contrôle préalable sur la machine de recherche (macOS arm64) : python,
  dépendances et hachages des trois jeux conformes au manifeste ; permissions 644
  (avertissement) ; aucun exécuteur `thesis-real`.
- Les figures publiées du manuscrit sont liées au run scellé `local-ffa02b2`. Ces
  changements touchent du code de vérification : la porte de certification
  signalera ces figures périmées. Le rescellement complet (profils, `claims
  archive`, chiffres du manuscrit) est à faire une seule fois, sur le commit à
  certifier, juste avant l'exécution REAL ; le refaire maintenant serait périmé
  à la prochaine modification.
