# Relecture factuelle du manuscrit

Le 14 octobre 2026, les affirmations de `paper/main.tex` sur le code, les
protocoles et les résultats ont été comparées au code de `src/` et
`experiments/`, aux CSV archivés et à des recalculs ponctuels. Environ 150
affirmations ont été examinées : seuils et paramètres, définition des scores,
préparation des détecteurs, composition des jeux de données, protocole, chaque
chiffre du texte courant, les huit lignes du tableau de contamination, les
types d'anomalies, la sévérité et la discussion. Les six tableaux sont aussi
comparés automatiquement par `tests/test_publication_tables.py`.

## Corrections

| Affirmation | Constat | Correction |
| --- | --- | --- |
| Great Expectations « le plus sélectif » sur la fraude | Isolation Forest signale 0,2 % des lignes. | « le plus sélectif des règles ». |
| LOF et One-Class SVM « ne passent pas à l'échelle » à 284 000 lignes | Jamais mesuré ; l'étude de croissance ne s'étend pas à cette taille. | Présenté comme un coût attendu, non mesuré. |
| LOF et One-Class SVM exécutés sur Water Quality et le synthétique | Ils le sont aussi sur Cardio. | Cardio ajouté. |
| Écart type de F1 de 0,14 à 0,17 pour les trois détecteurs ML sur Cardio | LOF : 0,05. | Limité à Isolation Forest (0,14) et One-Class SVM (0,17). |
| PR-AUC de Water Quality « au niveau ou juste au-dessus » du taux de base | Cinq sur six sont en dessous. | « à moins de 0,04 du taux de base ». |
| Précision d'environ 0,24 sur les anomalies multivariées | 0,23 et 0,22 ; 0,24 est la valeur des anomalies univariées. | « environ 0,22 ». |
| Décalage de fenêtre du détecteur de dérive « environ un dixième d'écart type » | 0,04 à 0,11 sur les cinq découpages de test. | Valeurs données. |
| Précision de la fraude de 0,01 à 0,20 en passant de 0,10 à la prévalence | 0,20 est une moyenne sur cinq graines, 0,01 vient d'une graine. | 0,01 à 0,28 pour la graine du tableau, 0,20 en moyenne. |
| Rappel multivarié d'environ 0,4 avec une contamination de 0,10 | 0,33 en moyenne sur cinq graines. | « environ 0,3 ». |
| Contrôles « avant un essai réel » sur colonnes attendues et prévalence | C'est une commande séparée qui compare empreinte, nombres de lignes, anomalies et classe positive. | Description réécrite. |
| « Quatre tableaux » comparés aux archives | Cinq l'étaient, le tableau de contamination ne l'était pas. | Test ajouté ; six tableaux. |

## Non vérifiables ici

- Les affirmations sur des sources externes (ADBench : 30 algorithmes et 57
  jeux ; AUC de 0,51 chez Sokkula et Vuppala ; coût de 12,9 M$ par an).
- Les droits sous-jacents de Cardio et la révision du fichier Credit Card.
- La note du code et de l'enregistrement des essais selon laquelle LOF et
  One-Class SVM « ne passent pas à l'échelle » à cette taille : elle n'est pas
  mesurée, comme le manuscrit le dit désormais. Le texte du code n'a pas été
  modifié pour ne pas invalider les archives.
- Les phrases de « Related Work » (section à rédiger).
