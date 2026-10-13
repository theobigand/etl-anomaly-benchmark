# Coût des détecteurs

`make verify-scale` exécute Isolation Forest, LOF et One-Class SVM sur des
matrices numériques générées en mémoire. L'essai local utilise 100, 300 puis
900 lignes, 8 colonnes et 3 répétitions par méthode et taille. Par défaut,
chaque méthode apprend sur toutes les lignes et évalue ces mêmes lignes :
il s'agit d'une mesure de coût, pas d'une mesure de qualité prédictive.
`--fit-cap` permet d'indiquer un plafonnement explicite de l'apprentissage.

Les temps `fit_s`, `predict_s` et `score_s` entourent les trois appels dans
`pipeline.detect` ; `detect_s` est leur somme. La génération des données, la
lecture de CSV et la déduplication sont hors mesure. La mémoire correspond au
pic vu par `tracemalloc` pendant la détection : les allocations natives des
bibliothèques ne sont pas incluses. `scaling.json` conserve la machine, les
versions, les réglages et les échecs éventuels ; `scaling.csv` conserve chaque
répétition. Une méthode qui échoue reçoit une ligne `FAIL` avec sa raison.

Sur l'essai local du 13 octobre 2026, les médianes de `detect_s` pour
100/300/900 lignes sont respectivement 0,371/0,381/0,388 s pour Isolation
Forest, 0,007/0,010/0,021 s pour LOF et 0,007/0,011/0,050 s pour One-Class
SVM. Les pics d'allocations Python à 900 lignes sont d'environ 0,66 Mo,
1,07 Mo et 0,32 Mo dans le même ordre. Les 27 exécutions ont réussi.

Ces petites tailles ne permettent pas d'extrapoler aux 284 000 lignes du jeu
de fraude. Les durées ont aussi varié lors des rejeux du benchmark principal.
Il faut une machine réservée, davantage de tailles et une mesure de mémoire
native avant de publier un classement de coût ou un seuil de régression.
