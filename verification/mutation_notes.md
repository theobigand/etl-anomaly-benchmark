# Mutations des métriques

La campagne actuelle porte seulement sur `src/etl_benchmark/metrics.py`, avec
mutmut 3.8.0 et `tests/test_metric_contract.py`. Après les nouveaux cas sur
les formes et longueurs invalides et l'absence d'avertissement pour une
précision sans prédiction positive, 86 des 97 mutants sont éliminés. Le gate
reste en échec à 88,66 %, et aucune mesure n'existe encore pour les autres
modules.

Les onze survivants se répartissent ainsi :

| Mutants | Ce qui change | Suite à donner |
| --- | --- | --- |
| 16, 25, 33, 34, 40, 46 | Préfixe ou casse de messages d'erreur ; la même entrée reste rejetée. | Ne pas ajouter des assertions sur la typographie uniquement pour augmenter le score. Vérifier le sens des erreurs si elles entrent dans un contrat public. |
| 44 | `scores.astype(float)` devient `scores.astype(None)`. | Préciser si les scores numériques encodés en chaînes sont acceptés ; tester ce contrat avant de classer ce mutant. |
| 66, 67, 76, 77 | `zero_division` change pour rappel ou $F_1$. | Les labels contenant nécessairement les deux classes, ces paramètres n'affectent pas le résultat dans le domaine admis. Confirmer sur la version installée de scikit-learn avant toute exclusion formelle. |

Cette classification décrit les survivants ; elle ne retranche aucun mutant
du dénominateur actuel. La prochaine campagne devra couvrir aussi le
découpage, les injecteurs, les détecteurs et les scripts d'expérience, avec
une mesure distincte de la portée totale.
