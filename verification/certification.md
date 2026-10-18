# Contrat de certification

`make verify-release` (`python -m verification.release`) applique la politique
versionnée `verification/release_policy.json` (version 1) aux preuves du
dépôt à l'état courant. Le verdict est `CERTIFIED`, `INCOMPLETE` ou
`REJECTED` ; il est écrit dans `experiments/results/evidence/release.json`
avec la politique appliquée.

## Preuves exigées

| Preuve | Statut dans la politique | Ce qu'elle établit |
| --- | --- | --- |
| `fast` | exigée | Tests réussis, couverture de lignes et de branches de 100 % sur `src/etl_benchmark` et `experiments`, chiffres et affirmations du manuscrit (`tests/test_manuscript_claims.py`). |
| `deep` | exigée | Au moins 95 % des mutants tués sur l'ensemble des fichiers éligibles (relevé indépendant dans `mutation_scope.json`), liste des fichiers réellement mutés. |
| `faults` | exigée | Chacun des défauts scientifiques délibérés est détecté et le témoin passe. |
| `real` | exigée | Les trois jeux complets existent, correspondent aux empreintes de référence et passent leurs contrôles. |
| `tools` | exigée | Couverture de 100 % des lignes et des branches du code de vérification (`verification/`). |
| `types` | exigée | Aucun nouvel écart de typage ni entrée de base de référence périmée, avec mypy 2.4.0 et pandas-stubs 3.0.5.260914. |
| `reproduction` | exigée | Cardio reproduit contre l'archive, entre deux essais et dans un environnement reconstruit depuis le verrou. |
| performance | facultative | Les mesures de coût sont liées à l'empreinte de la méthode de mesure ; périmées, elles bloquent la certification, absentes ou héritées (`LEGACY`) elles ne la bloquent pas. |
| `manuscript_claims` | sans objet | Vérifié dans `fast`. |
| `independent_attestation` | différée | Aucun tiers n'atteste les preuves. |
| `linux_environment_lock` | différée | Le verrou d'environnement ne couvre que osx-arm64 (issue 45). |

Chaque preuve est une enveloppe validée par `verification/evidence_schema.py` :
statut recalculé à partir du résultat (jamais lu tel quel), hachages des
artefacts, révision du dépôt, empreinte scientifique et environnement. Une
preuve absente ou inachevée donne `INCOMPLETE` ; une preuve invalide, échouée,
altérée, d'une autre révision, produite depuis un arbre modifié, ou issue d'un
environnement incompatible donne `REJECTED`.

## Environnements

Les versions de numpy, pandas, scikit-learn et pyod doivent figurer dans chaque
preuve qui exécute le code scientifique et être identiques d'une preuve à
l'autre, de même que la version mineure de Python. Le système d'exploitation
peut différer : le rapport indique alors `cross-platform` ; il indique
`exact-environment` lorsqu'une seule plateforme a produit toutes les preuves
avec les versions du verrou. Des versions cohérentes mais différentes du verrou
donnent `INCOMPLETE`.

## Ce que CERTIFIED prouve

Pour une révision propre et une empreinte scientifique donnée, toutes les
preuves exigées existent, sont intègres, concordent entre elles et passent
leurs critères.

## Ce que CERTIFIED ne prouve pas

- Qu'une personne ou un système indépendant a attesté ces preuves. Le champ
  `attestation` vaut `local-unattested` hors CI et `ci-run:<id> (not
  independently attested)` en CI.
- Qu'un score de mutation de 95 % élimine tout défaut : les mutants survivants
  restent comptés et décrits dans `mutation_notes.md`.
- La validité scientifique des conclusions au-delà des jeux et des graines
  testés, ni le coût d'une exécution ETL complète : les durées mesurent la
  seule étape de détection.
- La reproductibilité sur d'autres jeux que cardio, ni sur d'autres systèmes
  que ceux du verrou.
- Que les preuves distantes (CI) valent preuve locale pour `real`, dont les
  jeux de données ne quittent pas la machine du chercheur.
