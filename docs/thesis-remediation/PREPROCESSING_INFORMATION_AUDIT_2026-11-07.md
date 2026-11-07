# Audit de préparation et d'information — 2026-11-07

## Deux protocoles, deux statuts

Les archives historiques de `research.normalise.clean` filtrent les colonnes
constantes, majoritairement manquantes et catégorielles de haute cardinalité,
encodent les catégories restantes, puis retirent des doublons avant le split.
Ces décisions lisent la population complète; les résultats restent donc
descriptifs. Le rapport produit liste les colonnes supprimées, encodées et les
lignes retirées, mais ne répare pas cet accès historique à l'évaluation.

Le chemin prospectif `research.pool_train_only` conserve dans chaque sortie le
rapport `preprocessing` de `prepare_frozen`: colonnes retenues, omises,
encodées, médianes et échelle apprises sur le train. Il encode une catégorie
inconnue du test dans un bloc nul sans modifier le vocabulaire. C'est le seul
chemin qui permet une comparaison train-only avec des partitions gelées.

## Information reçue par les familles

| contexte | variables effectivement disponibles | conséquence déclarée |
| --- | --- | --- |
| registre comparable | colonnes numériques; les colonnes texte et catégorielles sont ignorées | les modèles et règles numériques ne peuvent pas détecter directement formats, domaines catégoriels ou sémantique textuelle |
| Great Expectations | toutes les colonnes pour le contrôle non-null; bornes numériques seulement | sa couverture de nullité est plus large, mais il ne représente pas des règles métier de format ou de cohérence |
| porteurs à fautes injectées | quatre colonnes continues ou plus, puis six fautes numériques construites | ce n'est pas une comparaison de détection catégorielle ou textuelle |
| `pool_train_only` prospectif | numérique et catégories à vocabulaire de train; texte libre et haute cardinalité omis | cette représentation diffère du registre historique et ses résultats ne peuvent pas remplacer celui-ci sans campagne séparée |

Pour les modèles appris, l'imputation médiane est ajustée sur le train avant
la standardisation. Une valeur manquante au test devient donc une valeur
numérique imputée et peut ne plus être visible comme faute; le contrôle
Great Expectations conserve au contraire une attente de non-null explicite.
La standardisation emploie moyenne et écart-type du train seulement. Les
règles emploient leurs propres statistiques de train (moyenne/écart-type,
quartiles ou bornes percentiles), sans imputer une entrée avant leur score.

## Orientation et limite de comparaison

Le contrat `Detector.score` et les tests de registre imposent des scores finis,
indexés comme l'entrée, où une valeur plus grande signifie une anomalie plus
forte. Les adaptateurs PyOD retournent `decision_function`; les règles et les
adaptateurs personnalisés suivent la même orientation. Les seuils binaires
restent distincts des métriques de rang.

Les familles ne reçoivent donc pas exactement la même information dans tous
les parcours: les règles de nullité voient les colonnes nullables, les modèles
comparables ne voient que le numérique, et le parcours prospectif peut encoder
des catégories. Cette asymétrie est une limite méthodologique explicite, pas
une preuve qu'une famille est intrinsèquement supérieure.
