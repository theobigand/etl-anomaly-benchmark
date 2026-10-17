# Suivi de la remédiation post-audit (issues #38 à #49)

Ce fichier est le point de reprise de la remédiation. Une issue n'est fermée
qu'après exécution des contrôles listés ici, sur le commit indiqué.

| Issue | État | Commit | Preuves |
| --- | --- | --- | --- |
| #38 reproduction : niveau demandé NOT_RUN | code terminé, en attente de CI | voir `git log` (`#38`) | RED : 6 tests de `tests/test_reproduce.py` en échec (pas de champ `outcome`, plantage sans rapport) ; GREEN : 20 tests ; FAST 783 passed ; verify-tools 100 % |
