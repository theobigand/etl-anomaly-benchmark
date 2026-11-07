# Audit de convergence des détecteurs neuronaux — 2026-11-07

## Objet et méthode

Cet audit clôt T055 en séparant une exécution sans exception enregistrée d'une
preuve de convergence. Il a inspecté les signatures installées de PyOD 3.6.7,
les adaptateurs du dépôt, les protocoles et les archives déjà versionnées. Il
ne modifie ni les partitions historiques ni les résultats numériques.

## Budgets et diagnostics disponibles

| détecteur | origine et budget de l'implémentation évaluée | arrêt / diagnostic conservé |
| --- | --- | --- |
| `autoencoder` | `MLPRegressor`, au plus 300 itérations | `settings()` conserve `max_iter`, `n_iter` et `converged`; les cinq fichiers `verification/evidence/deep_typed/seed_*.json` ont `converged: true`. |
| `vae` | PyOD 3.6.7, `epoch_num=30` par défaut | budget fixe; les archives du registre ne conservent ni courbe de perte ni indicateur d'arrêt. |
| `deep_svdd` | PyOD 3.6.7, `epochs=100` par défaut | `validation_size=0.1` est un argument du modèle; aucun diagnostic de convergence n'est exporté dans les archives du registre. |
| `dif` | PyOD 3.6.7, représentations aléatoires et forêts; pas de paramètre d'époque | la convergence par descente de gradient ne s'applique pas; aucune mesure de stabilité des représentations n'est archivée. |
| `ae1svm` | PyOD 3.6.7, `epochs=50` par défaut | budget fixe; aucun historique de perte ni état de convergence n'est exporté. |
| `lunar` | PyOD 3.6.7, `n_epochs=200` par défaut | `val_size=0.1` est un argument du modèle; aucun diagnostic de convergence n'est exporté dans les archives du registre. |

Les adaptations de score ECOD/COPOD, VAE, DIF et AE1SVM sont décrites dans
`INDUCTIVE_DETECTORS_2026-11-03.md`; elles ne constituent pas des contrôles de
convergence.

## Échecs numériques archivés

Les 100 enveloppes de `verification/evidence/full_registry/pool_deep/runs/`
ont chacune un champ `errors` vide. Les 100 enveloppes de
`verification/evidence/pool_extension/pool_full_deep/runs/` ont aussi un champ
`errors` vide; elles contiennent 500 exécutions par détecteur, soit 3 000
exécutions des six détecteurs sans exception enregistrée. Les sauts de modèles
coûteux restent des sauts de protocole distincts.

Ces champs attestent seulement qu'aucune exception n'a été conservée par les
scripts. Les archives du registre ne conservent pas leurs réglages effectifs,
leurs pertes, leurs itérations réalisées ni les avertissements numériques.
Elles ne peuvent donc pas établir qu'un entraînement PyOD a convergé, qu'il n'a
pas divergé silencieusement, ou que le budget était suffisant.

## Conséquence pour les résultats et la suite

La formulation du mémoire est limitée à l'absence d'exception enregistrée; elle
ne présente plus ce constat comme une preuve de convergence. La convergence
effective est documentée seulement pour le cas séparé de l'autoencodeur du
benchmark typé. Le pilote LSTM est hors du registre et conserve son propre
résultat négatif: ses cinq entraînements Credit Card ont atteint le budget de
20 époques sans convergence.

Toute nouvelle campagne du registre doit conserver, par graine et détecteur,
les arguments effectifs, le nombre d'époques ou itérations réalisées, une
raison d'arrêt, les pertes ou un diagnostic approprié, les avertissements et
les exceptions. Une telle campagne serait prospective et ne réécrit pas les
conclusions historiques.
