# Avancement des tickets

Les corrections du protocole et le rejeu des résultats sont dans la branche
courante. Les tickets restent ouverts tant que leurs critères de réception ne
sont pas tous remplis.

## Vérification du socle (#3 à #7)

- **#3** : l'état initial (76 tests), les risques et la couverture par fichier
  sont consignés. Il manque l'inventaire complet des fonctions et de leurs tests.
- **#4** : les petits jeux de test et les marqueurs FAST/REAL sont en place.
  Les fixtures partagées et l'interdiction explicite du réseau restent à faire.
- **#5** : le déroulé test en échec, correction, puis régression est documenté
  dans `README.md`.
- **#6** : FAST mesure lignes et branches et échoue si elles ne sont pas toutes
  couvertes. La couverture actuelle est de 962/1324 lignes et 173/262 branches.
- **#7** : le premier essai de mutation porte sur `metrics.py` ; 23 mutants
  survivent. La campagne sur le reste du code n'a pas été lancée.

## Protocole et mesures (#8 à #15)

- **#8–9** : les copies synthétiques restent dans la même partition et les
  détecteurs apprennent sur le train. Les cas temporels demandent un protocole
  distinct ; il reste des entrées limites à tester.
- **#10** : la contamination invalide est rejetée. Un calibrage sans labels
  d'entraînement reste à comparer au calibrage actuel.
- **#11** : taille de population, taux nul et types injectés ont des tests.
  Il manque des contrôles fins des champs non modifiés et des sévérités.
- **#12** : labels, valeurs manquantes et tailles des trois CSV locaux sont
  contrôlés. La provenance et les conditions d'usage restent à confirmer.
- **#13–14** : métriques binaires, classement, dénominateurs par type et types
  absents ont des cas calculés à la main. Les égalités de scores et les jeux
  de détecteurs variables méritent encore des tests.
- **#15** : ordre des colonnes, index, valeurs finies et apprentissage sont
  vérifiés. Le contrat commun doit être appliqué à tout nouveau détecteur.

## Exécution et résultats (#16 à #24)

- **#16–17** : un aller-retour CSV et des propriétés bornées du découpage et
  du générateur passent. Il manque les pannes d'écriture et les cas extrêmes.
- **#18–19** : les quatre commandes d'expérience enregistrent graines,
  paramètres et fichiers produits ; les écarts types à une seule graine sont
  non définis. Il reste à conserver les identifiants de partition et les
  échecs de détecteur dans chaque essai.
- **#20** : quatre commandes CLI, les fichiers archivés et les quatre tableaux
  du manuscrit sont contrôlés. La relecture des légendes et des affirmations
  dans le texte reste à faire.
- **#21–23** : FAST tourne en CI, DEEP et REAL en local ; le profil est
  reconstruit à chaque FAST avec la révision courante. FAST et DEEP restent
  rouges. Les règles de protection
  distantes et l'historique des dénominateurs ne sont pas établis.
- **#22** : les contre-exemples de fuite et de métrique ont été ajoutés aux
  tests. La matrice complète des défauts introduits volontairement manque.
- **#24** : README, notes de données, figures et manuscrit ont été mis à jour
  après les nouveaux essais. La revue finale du mémoire reste ouverte.

## Suite du travail (#25 à #30)

- **#25** : le découpage chronologique et un suivi par fenêtre ont des tests
  sans accès au futur (`test_temporal_protocol.py`). La saisonnalité, les
  métriques sur plusieurs changements et l'évaluation sur données réelles
  restent à étudier.
- **#26** : définir et tester les contrats CPU des autoencodeurs et des
  séquences avant d'ajouter leurs résultats aux comparaisons.
- **#27** : les trois jeux réels présents ont été rejoués avec cinq graines.
  Les recettes d'acquisition, les droits d'usage et les partitions exactes
  manquent à l'archive.
- **#28** : mener des mesures de croissance en temps et en mémoire, avec des
  tailles d'entrée et une machine documentées.
- **#29** : les règles et Isolation Forest rejettent les colonnes
  d'entraînement vides, les infinis et les colonnes requises absentes ; les
  colonnes constantes ont des sorties finies. Il reste les classes extrêmes,
  les schémas changeants et les timestamps invalides dans les expériences.
- **#30** : attendre la résolution des points précédents, puis refaire les
  vérifications et les comparaisons publiées sur un état unique du dépôt.

Le ticket de coordination **#2** reste ouvert.
