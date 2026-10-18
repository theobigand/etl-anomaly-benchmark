# Sécurité de l'exécuteur REAL

Les trois jeux complets sont des fichiers de recherche qui ne doivent pas quitter
la machine qui les détient. Cette note dit ce que le dépôt impose, ce qu'il ne
peut pas imposer, et ce que l'opérateur doit faire. Elle ne prétend pas que les
liens symboliques protègent les données : le code exécuté sur l'exécuteur lit les
fichiers avec les droits du compte, liens ou non, et peut les envoyer partout où
le réseau le permet.

## Ce que le dépôt impose (testé dans `tests/test_workflows.py`)

| Risque | Mesure | Limite |
| --- | --- | --- |
| Un exécuteur hébergé prend le job | `runs-on: [self-hosted, <étiquette>]` et garde `RUNNER_ENVIRONMENT = self-hosted` | aucune |
| Code non relu face aux données | le job exige la branche par défaut, aucun déclenchement `pull_request`, aucun `pull_request_target` ni `workflow_run` | quiconque peut pousser sur la branche par défaut peut changer le workflow : d'où la protection de `main` (issue 46) |
| Mauvaise révision | `approved_sha` obligatoire, égal au commit lancé, vérifié avant la récupération du code | le propriétaire doit relire ce commit |
| Autre workflow sur l'exécuteur | aucun autre fichier de workflow ne cite `self-hosted` ni l'étiquette (test) | un exécuteur de dépôt accepte tout workflow qui demande ses étiquettes : une branche qui ajoute un workflow le ferait. Seul le contrôle des écritures sur le dépôt l'empêche |
| Dépendances non fixées | installation depuis le verrou à empreintes, `--no-deps`, roues seules | pip, setuptools et wheel viennent du `venv` standard |
| Fuite par artefact | paquet à liste blanche (deux JSON, 5 Mio), un seul `upload-artifact` | un code malveillant pourrait ignorer le paquet ; c'est la relecture du commit qui protège |
| Jeton du dépôt | `permissions: contents: read`, `persist-credentials: false` | le jeton existe le temps du job |
| Jeu modifié | SHA-256 contre le manifeste avant `make verify-real` | |

## Ce que l'opérateur doit faire

- **Isolement** : exécuteur éphémère (`--ephemeral`, un job puis désenregistrement),
  dans une VM dédiée sans autre donnée, sans clé SSH, sans identifiants de
  nuage, sans accès au réseau local. Détruire ou restaurer la VM après le run.
- **Droits** : compte `thesis-runner` sans administrateur ; répertoire des jeux en
  0700 et fichiers en 0400 (le script de provisionnement les applique) ; rien
  d'autre ne lui est lisible.
- **Réseau** : le dépôt ne filtre pas la sortie. Limiter, côté VM ou pare-feu,
  les destinations à GitHub (`github.com`, `api.github.com`,
  `*.actions.githubusercontent.com`, le stockage des artefacts) et au dépôt de
  paquets (`pypi.org`, `files.pythonhosted.org`) pendant l'installation, puis
  couper PyPI avant `make verify-real`. Sans ce filtre, la seule protection
  contre l'exfiltration est que le commit lancé a été relu.
- **Accès au dépôt** : tant que le propriétaire est le seul collaborateur avec
  droit d'écriture, nul autre ne peut pousser un workflow qui cible l'exécuteur.
  Ajouter un collaborateur ou activer les forks change cette hypothèse. Un
  groupe d'exécuteurs restreint à un workflow n'existe que pour une
  organisation ; sur un dépôt personnel, il n'y a pas d'équivalent.
- **Déclenchement** : `gh workflow run verify-release.yml --ref main -f
  real_runner=thesis-real -f approved_sha=<sha>`, après relecture de ce sha.
- **Jetons** : le jeton d'enregistrement est éphémère et tapé à la main ; il
  n'est jamais écrit dans un fichier du dépôt ni passé au script.

## Classification de la preuve

Une exécution REAL sur la VM dédiée est une exécution distante du propriétaire :
`ci-run:<id> (not independently attested)`. Elle prouve que les trois fichiers
ont les empreintes du manifeste et passent les contrôles, avec un environnement
verrouillé et un code relu. Elle ne prouve pas qu'une autre personne a rejoué le
travail.

## Dépôt public (constat du 18 octobre 2026)

Passer le dépôt en public déplace la frontière de sécurité.

- Sondage de l'historique (toutes les branches) : aucun jeton, clé privée ni
  fichier `.env` ; la seule correspondance du motif `ghp_` est la chaîne de test
  qui vérifie son absence. Aucun CSV de données brutes n'a jamais été validé
  (`data/` est ignoré) ; les archives de partitions contiennent des positions de
  lignes, pas de valeurs. Les fichiers de plus de 1 Mio de l'historique sont ces
  archives.
- Chemins absolus : les enregistrements `evidence/run_*.json` contiennent le
  chemin du poste de recherche (`/Users/theo/Developer/...`), ainsi que
  `HANDOFF.md` et `milestones.json`. C'est une fuite mineure (nom de compte et
  arborescence). Elle n'est pas corrigée : les réécrire modifierait la
  provenance historique et, pour les enregistrements, l'historique git la
  conserve de toute façon. Les prochains rejeux pourraient écrire des chemins
  relatifs ; ce changement toucherait `experiments/` et imposerait un rejeu.
- Réglages du dépôt (propriétaire) : la recherche de secrets est
  désactivée (`secret_scanning: disabled`) ; l'approbation des workflows de
  contributeurs extérieurs est « premiers contributeurs » seulement. Je
  recommande `gh api -X PUT repos/theobigand/etl-anomaly-benchmark/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors`
  et l'activation de la recherche de secrets. Rien n'a été modifié.
- Jeton par défaut en lecture seule, aucun secret utilisé par les workflows, un
  seul collaborateur. Les pull requests de forks s'exécutent sans secret avec un
  jeton en lecture ; seul `ci.yml` s'exécute sur toute pull request, et
  `verify-release.yml` seulement quand elle modifie ce fichier.
- Exécuteur auto-hébergé : GitHub déconseille d'en lier un à un dépôt public,
  car un workflow écrit dans une branche ou une pull request approuvée s'exécute
  dessus. Un SHA approuvé dans une entrée de `workflow_dispatch` ne protège que
  le job `real`, pas un autre workflow qu'un tiers ferait approuver. D'où le
  choix de l'option A.
