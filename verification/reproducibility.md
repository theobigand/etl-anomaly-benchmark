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
