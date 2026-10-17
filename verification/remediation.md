# Suivi de la remédiation post-audit (issues #38 à #49)

Ce fichier est le point de reprise de la remédiation. Une issue n'est fermée
qu'après exécution des contrôles listés ici, sur le commit indiqué.

| Issue | État | Commit | Preuves |
| --- | --- | --- | --- |
| #38 reproduction : niveau demandé NOT_RUN | code terminé, en attente de CI | voir `git log` (`#38`) | RED : 6 tests de `tests/test_reproduce.py` en échec (pas de champ `outcome`, plantage sans rapport) ; GREEN : 20 tests ; FAST 783 passed ; verify-tools 100 % |
| #40 environnements scientifiques | code terminé, en attente de CI | voir `git log` (`#40`) | RED : 15 tests en échec (`assess()` sans argument `locked`, aucune vérification d'environnement) ; GREEN : `tests/test_release_gate.py` 30 passed ; verify-tools 100 % |
| #41 périmètre de mutation | code terminé, en attente de CI | voir `git log` (`#41`) | RED : `tests/test_mutation_scope.py` en erreur de collecte (module absent), puis 5 tests de release/evidence en échec ; GREEN : 14 + 36 tests ; verify-tools 100 % ; relevé réel : 28 fichiers dans le périmètre, 27 mués (+1 déclaré sans mutant) |
| #43 provenance de la mesure | code terminé, en attente de CI | voir `git log` (`#43`) | RED : 21 tests de `tests/test_measurement_fingerprint.py` et 3 de release/outils en échec (fonctions absentes) ; GREEN : 24 + 58 tests ; l'empreinte scientifique reste `44faa1f9` ; `scaling.json` archivé inchangé (LEGACY) |
