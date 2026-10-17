# Reproductibilité

`python -m verification.reproduce --levels archive same_environment
locked_environment version_sensitivity` relance le benchmark `cardio`
(5 graines, 1 800 lignes, environ six secondes) et compare le tableau obtenu à
une référence. Quatre notions sont séparées :

- numérique : toutes les mesures sont identiques bit à bit ;
- statistique : les mesures diffèrent, mais chaque moyenne reste à moins d'un
  écart type de la référence ;
- artefact : l'archive des partitions (`split_ids_cardio.json.gz`) est
  identique octet pour octet ;
- durée : les colonnes `detect_s` sont comparées seulement comme écart
  relatif et ne décident d'aucun statut (elles varient d'une exécution à
  l'autre, de quelques dizaines de pour cent à plusieurs fois la valeur).

## Politique de sortie

Les trois premiers niveaux (`archive`, `same_environment`, `locked_environment`)
sont obligatoires. Si l'un d'eux est demandé, tout état autre que `PASS`
(`FAIL`, `NOT_RUN`, plantage du benchmark) donne un code de sortie 1 et un
champ `outcome` valant `FAIL` ou `INCOMPLETE` dans `reproducibility.json`, avec
la liste des raisons. Le niveau `version_sensitivity` reste une mesure
(`MEASURED` ou `NOT_RUN`) : il ne change jamais le résultat, mais une commande
qui ne demande aucun niveau obligatoire est `INCOMPLETE`. Le rapport est écrit
dans tous ces cas.

## Résultats du 16 octobre 2026

Exécutés sur cette machine (macOS arm64, Python 3.11.17), code au dépôt
`verify/m10-reproducibility`, jeu `cardio` seulement :

| Niveau | Statut | Détail |
| --- | --- | --- |
| Archive de `evidence/` contre un nouvel essai | PASS, numérique | écart maximal 0,0 ; partitions identiques |
| Deux essais, même source, même environnement, mêmes graines | PASS, numérique | écart maximal 0,0 ; partitions identiques |
| Environnement reconstruit depuis le verrou (`conda create --file`, puis `pip install --no-deps -r`) | PASS, numérique | mêmes versions (numpy 2.4.6, pandas 3.0.6, scikit-learn 1.9.1, pyod 3.6.7, great-expectations 1.24.0) ; écart 0,0 |
| Sensibilité : scikit-learn 1.8.0 au lieu de 1.9.1 | mesuré, numérique | écart 0,0 ; version vérifiée dans l'environnement modifié |

Le niveau « sensibilité » décrit une mesure, il ne valide ni n'invalide rien.
Un écart nul pour une version de scikit-learn sur un jeu ne dit rien des
autres paquets ni des autres jeux.

## Ce qui n'a pas été exécuté

- Le rejeu complet du 16 octobre 2026 (voir `report.md`) n'a pas été refait dans
  un second environnement : seul Cardio l'a été (tableau ci-dessus).
- Un autre système d'exploitation ou une autre architecture : le verrou
  `conda-darwin-arm64.explicit.txt` est propre à macOS arm64. La reconstruction
  a besoin d'un accès réseau aux index conda-forge et PyPI ; sans réseau le
  niveau est `NOT_RUN`, jamais `PASS`.
- Le verrou pip n'épingle pas de sommes de contrôle.
- Les archives du 15 octobre avaient été produites sur un arbre de travail
  modifié (révision `841c3aa4`, `worktree_dirty: true`) ; elles ont été
  remplacées par un rejeu depuis le commit propre `93b6fe8` (voir `report.md`).
  Les anciens enregistrements restent dans l'historique git au commit d'ancrage.

## Autres jeux et environnement Linux

`--dataset` choisit `cardio` (défaut), `water_quality`, `credit_card` ou
`synthetic`. Chaque rejeu reprend les graines (et, pour le synthétique, le
nombre de lignes) de l'exécution archivée `run_*.json`, écrit dans un dossier
temporaire (la figure du manuscrit n'est jamais réécrite) et se compare au
tableau archivé ; les partitions sont comparées octet pour octet quand
l'archive en contient (`synthetic` n'en archive pas : `artifact_identical`
vaut alors `null`). Le rapport (`experiments/results/reproducibility*.json`)
consigne le jeu, les graines, la révision et l'empreinte du jeu de l'exécution
archivée, les empreintes des partitions, les tolérances, la plateforme, les
versions exactes et le verrou utilisé. Un jeu absent de la machine, ou dont
l'empreinte diffère de celle de l'exécution archivée, met chaque niveau
demandé à `NOT_RUN` et la commande sort en erreur : rien n'est alors déclaré
reproduit. Les jeux `water_quality` et `credit_card` ne quittent jamais la
machine du chercheur ; ils ne sont pas rejoués en CI.

Budgets observés sur un portable (macOS arm64) pour le niveau `archive` :
cardio environ 6 s, water_quality quelques dizaines de secondes, synthétique et
credit_card quelques minutes.

Rejeux du 17 octobre 2026 (macOS arm64, Python 3.11.17, empreinte scientifique
`44faa1f9`, arbre de travail modifié après `14fc288` : seuls des fichiers de
vérification avaient changé), niveau `archive` seul :

| Jeu | Statut | Détail |
| --- | --- | --- |
| cardio | PASS, numérique | écart 0,0 ; partitions identiques (niveau `same_environment` aussi) |
| water_quality | PASS, numérique | écart 0,0 ; partitions identiques |
| credit_card | PASS, numérique | écart 0,0 ; partitions identiques |
| synthetic | PASS, numérique | écart 0,0 ; pas de partitions archivées |

Les niveaux `locked_environment` de ces trois jeux n'ont pas été exécutés
(l'environnement reconstruit a seulement été testé avec cardio, voir plus haut) ;
ils restent en attente.

### Verrou Linux

Le verrou conda ne couvre que osx-arm64. Pour Linux x86_64 (CPython 3.11), la
stratégie unique est un fichier pip avec empreintes,
`verification/environment/linux-x86_64-py311.lock.txt`, produit par
`python -m verification.lock_environment --linux` : pip résout les exigences du
projet (dépendances et extras) pour les roues manylinux cp311 sans les
installer (`--platform`, `--abi`, `--only-binary=:all:`), avec numpy, pandas,
scikit-learn et pyod fixés aux versions du verrou macOS, et chaque roue est
épinglée par version et sha256. `reproduce.build_environment` le reconstruit
sur Linux avec `python -m venv` puis `pip install --require-hashes --no-deps -r`.
Le fichier n'a pas été produit sur une machine Linux : sa validité sur un
exécuteur propre est établie par le job `reproduce` du workflow
`verify-release` (voir `remediation.md` pour le run).
