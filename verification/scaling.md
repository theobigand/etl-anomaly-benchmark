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

Sur l'essai local du 16 octobre 2026, les médianes de `detect_s` pour
100/300/900 lignes sont respectivement 0,376/0,384/0,392 s pour Isolation
Forest, 0,008/0,010/0,020 s pour LOF et 0,006/0,011/0,049 s pour One-Class
SVM. La machine exécutait alors d'autres tâches, ce qui a pu allonger ces
temps par rapport à l'essai précédent. Les pics
d'allocations Python à 900 lignes sont d'environ 0,65 Mo, 1,07 Mo et 0,32 Mo
dans le même ordre. Les 27 exécutions ont réussi.

Ces petites tailles ne permettent pas d'extrapoler aux 284 000 lignes du jeu
de fraude. Les durées ont aussi varié lors des rejeux du benchmark principal.
Il faut une machine réservée, davantage de tailles et une mesure de mémoire
native avant de publier un classement de coût ou un seuil de régression.

## Empreinte de la méthode de mesure

Les tableaux de détection sont liés à l'empreinte scientifique (recette 2).
Les mesures de coût ont leur propre empreinte, `measurement_fingerprint`
(recette 1 de mesure, `experiments/provenance.py`) : elle couvre
`verification/scaling.py` et le code de chronométrage de `pipeline.detect`
(`DetectionResult` et `detect`), et rien d'autre. Modifier la méthode de mesure
rend l'empreinte des nouvelles mesures différente et fait passer
`scaling.json` à l'état `STALE` dans `verification.release` (la certification
reste alors `INCOMPLETE`) ; modifier une porte de vérification ne change ni
l'une ni l'autre empreinte. Un nouveau script qui mesure du temps ou de la
mémoire doit être ajouté à `MEASUREMENT_FILES` : un test cherche dans l'arbre
les primitives de chronométrage et échoue sur un fichier non enregistré.

`scaling.json` archivé date d'avant cette empreinte. Il n'a pas été
réécrit : il est `LEGACY` (signalé, sans conséquence sur la certification, la
mesure de coût n'étant pas obligatoire). Les prochaines exécutions de
`make verify-scale` et les prochains enregistrements `run_*.json` portent
`measurement_recipe` et `measurement_fingerprint`.
