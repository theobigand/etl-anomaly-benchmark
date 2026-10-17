# Preuve REAL à distance

Les trois jeux complets (credit_card, water_quality, cardio) ne sont pas dans
le dépôt et ne doivent jamais être envoyés à GitHub. La preuve `real` reste
obligatoire pour une certification complète ; sans elle, `verify-release` rend
`INCOMPLETE` (`real evidence is missing`). Aucun exécuteur hébergé par GitHub
ne peut la produire.

## Chemin autorisé : un exécuteur auto-hébergé

1. Enregistrer sur la machine qui contient `data/` un exécuteur GitHub
   Actions auto-hébergé, avec une étiquette propre (par exemple
   `thesis-real`). C'est le propriétaire du dépôt qui l'autorise ; ce travail
   n'enregistre aucun exécuteur.
2. Lancer le workflow `verify-release` avec l'entrée `real_runner` valant cette
   étiquette. Le job `real` refuse de démarrer si `RUNNER_ENVIRONMENT` n'est pas
   `self-hosted`, exécute `make verify-real` (trois tests `real` puis
   `experiments/verify_real.py`), emballe les deux seuls rapports JSON avec
   `python -m verification.bundles pack real` (liste blanche, 5 Mio par fichier,
   rien d'autre) et les téléverse.
3. Le job `release` déballe chaque archive avec
   `python -m verification.bundles unpack` : un membre hors liste (un CSV, un
   chemin hors de l'arbre, un lien) refuse l'archive entière avant toute
   extraction.

## Ce que `verify-release` contrôle sur la preuve REAL

- le statut est recalculé à partir des résultats (jamais lu tel quel) ;
- les hachages des artefacts, la révision du dépôt et l'empreinte scientifique
  sont ceux des autres profils, l'arbre est propre ;
- les empreintes des trois jeux sont comparées au manifeste de référence
  (`verification/evidence/manifest.json`) ;
- l'enveloppe indique où elle a été produite (`execution`). Une preuve REAL
  produite en CI sur un exécuteur hébergé est rejetée ; une preuve produite sur
  un exécuteur auto-hébergé est acceptée et reste étiquetée `ci-run:<id> (not
  independently attested)` ; une preuve produite localement reste
  `local-unattested` ;
- les versions de numpy, pandas, scikit-learn et pyod et la version mineure de
  Python sont celles des autres profils.

## Passage de relais sans exécuteur

Faute d'exécuteur, `make verify-real` sur la machine du chercheur produit
`experiments/results/evidence/real.json`. Cette preuve vaut pour
`make verify-release` local (`local-unattested`) ; elle ne remplace pas une
exécution distante et n'est jamais présentée comme telle.

## État

Aucun exécuteur auto-hébergé n'est enregistré : la preuve REAL n'a pas été
produite à distance. L'issue 44 reste ouverte tant qu'un exécuteur autorisé
n'a pas exécuté le workflow.
