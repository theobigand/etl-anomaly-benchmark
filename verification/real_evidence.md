# Preuve REAL à distance

Les trois jeux complets (credit_card, water_quality, cardio) ne sont pas dans
le dépôt et ne doivent jamais être envoyés à GitHub. La preuve `real` reste
obligatoire pour une certification complète ; sans elle, `verify-release` rend
`INCOMPLETE` (`real evidence is missing`). Aucun exécuteur hébergé par GitHub
ne peut la produire.

## Chemin autorisé : un exécuteur auto-hébergé dédié

Le propriétaire du dépôt enregistre l'exécuteur ; ce travail n'en enregistre
aucun. État relevé en lecture le 17 octobre 2026 :
`gh api repos/theobigand/etl-anomaly-benchmark/actions/runners` répond
`total_count: 0`. Aucun exécuteur n'existe.

### Où l'installer

- Recommandé : une machine virtuelle Linux x86_64 dédiée, Python 3.11, qui ne
  contient que l'exécuteur et les trois CSV. C'est la plateforme du verrou
  `environment/linux-x86_64-py311.lock.txt` ; la correspondance avec l'archive
  y est statistique, et l'exécution est reproductible d'un lancement à l'autre.
- Possible : la machine de recherche (macOS arm64, celle de l'archive). Les
  résultats y sont numériquement identiques, mais l'exécution n'apporte alors
  aucune indépendance : la preuve est étiquetée `ci-run:<id> (not independently
  attested)`, comme pour toute exécution auto-hébergée, jamais « attestée ».
- Dans tous les cas : un compte système dédié sans droit d'administration, des
  fichiers lisibles par ce seul compte, un exécuteur éphémère (une tâche, puis
  désenregistrement), aucun secret du dépôt ni identifiant personnel sur la
  machine.

### Provisionnement (Linux)

`verification/runner/provision_runner.sh` prépare le compte et les fichiers.
Sans `--apply` il n'affiche que ce qu'il ferait. Il ne contient ni jeton ni
identifiant : le jeton d'enregistrement est éphémère, il vient de la page
Settings > Actions > Runners > New self-hosted runner, et se tape à la main.

```
RUNNER_ARCHIVE=... RUNNER_SHA256=... DATA_SOURCE=... \
  bash verification/runner/provision_runner.sh            # simulation
sudo env RUNNER_ARCHIVE=... RUNNER_SHA256=... DATA_SOURCE=... \
  bash verification/runner/provision_runner.sh --apply
```

Puis, en tant que `thesis-runner`, dans `~/actions-runner` :
`./config.sh --url https://github.com/theobigand/etl-anomaly-benchmark
--labels thesis-real --no-default-labels --ephemeral --token <jeton>` et
`./run.sh`. L'étiquette `thesis-real` n'est portée par aucun exécuteur hébergé.
Le fichier `.env` de l'exécuteur définit `THESIS_DATA_DIR=/srv/thesis-data`
(répertoire en mode 0700, fichiers en 0400).

### Contrôle préalable (lecture seule)

`python -m verification.real_preflight --expect-sha <sha> --check-registration thesis-real`
n'exécute pas le benchmark, n'écrit rien et n'affiche aucun contenu de jeu. Il
vérifie : le système et la version mineure de Python, les versions de numpy,
pandas, scikit-learn et pyod face au verrou, la présence des trois fichiers,
leur SHA-256 face à `verification/evidence/manifest.json`, leurs permissions
(écriture au-delà du propriétaire : échec ; lecture au-delà : avertissement),
le disque (5 Gio), les processeurs (2) et la mémoire (8 Gio), la révision
approuvée et l'arbre propre, la liste blanche du paquet REAL (deux rapports
JSON), les chemins téléversés par le job `real` (le seul `evidence-real.tgz`),
`RUNNER_ENVIRONMENT` et, si l'API le permet, l'enregistrement de l'exécuteur
(une lecture refusée est « inconnu », pas « absent »). Le workflow l'exécute
avant `make verify-real`.

### Garde-fous du job `real`

- il ne démarre que si `real_runner` est renseigné **et** que la référence
  lancée est la branche par défaut (le code qui voit les données privées est du
  code relu et fusionné) ; l'événement `pull_request` ne le lance jamais ;
- le commit lancé doit être égal à l'entrée `approved_sha` (SHA complet que le
  propriétaire a relu), sinon le job s'arrête avant de récupérer le code ;
- `RUNNER_ENVIRONMENT` doit valoir `self-hosted` ;
- le code est récupéré sans identifiants persistants, installé dans un
  environnement virtuel jetable ; les CSV sont liés par `ln -s` depuis
  `THESIS_DATA_DIR`, jamais copiés ;
- seuls `real_verification.json` et `evidence/real.json` sont emballés
  (`verification.bundles`, liste blanche, 5 Mio par membre) et téléversés.

### Procédure du propriétaire

1. Fusionner la PR avec son accord (le déclenchement manuel doit exister sur la
   branche par défaut) ; relire le commit de `main` à certifier.
2. Provisionner et enregistrer l'exécuteur, puis lancer le contrôle préalable
   localement sur cette machine.
3. `gh workflow run verify-release.yml --ref main -f real_runner=thesis-real -f approved_sha=<sha complet de main>`.
4. Le job `release-real` exécute `make verify-real` ; le job `release-gate`
   déballe les paquets (liste blanche) et rend le verdict.
5. Archiver l'identifiant du run, les condensés des artefacts
   (`gh api repos/.../actions/runs/<id>/artifacts`) et `release.json` sous
   `verification/evidence/ci/<id>/`, puis consigner le résultat dans
   `verification/remediation.md`.
6. Seulement si `release-gate` rend CERTIFIED avec l'étiquette
   `ci-run:<id> (not independently attested)` : clore les issues 44 et 49. Les
   preuves FAST, DEEP, FAULTS et la reproduction du même run doivent porter le
   même commit ; sinon relancer sur ce commit.

Rien de tout cela n'a été exécuté : aucun exécuteur n'est enregistré, REAL n'a
tourné qu'en local.

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

Aucun exécuteur auto-hébergé n'est enregistré (lecture API du 17 octobre
2026) : la preuve REAL n'a pas été produite à distance. L'issue 44 reste ouverte tant qu'un exécuteur autorisé
n'a pas exécuté le workflow.
