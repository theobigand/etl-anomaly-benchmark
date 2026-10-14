# Avancement des tickets

Les corrections du protocole et le rejeu des résultats sont dans la branche
courante. Les tickets restent ouverts tant que leurs critères de réception ne
sont pas tous remplis.

## Vérification du socle (#3 à #7)

- **#3** : l'état initial (76 tests), les risques et la couverture par fichier
  sont consignés. `function_matrix.md` relie maintenant les fonctions aux
  tests principaux et indique les trous encore visibles.
- **#4** : les petits jeux de test et les marqueurs FAST/REAL sont en place.
  Des fixtures indépendantes sont ajoutées. Le réseau est bloqué dans pytest
  et dans les sous-processus Python lancés par ses tests de commandes.
- **#5** : le déroulé test en échec, correction, puis régression est documenté
  dans `README.md`.
- **#6** : FAST mesure lignes et branches, y compris dans les commandes en
  sous-processus, et échoue si elles ne sont pas toutes couvertes. La
  couverture actuelle est de 1394/1394 lignes et 298/298 branches, sans
  exclusion. Les commandes locales de génération, de conversion Cardio et de
  démonstration ont des tests dédiés.
- **#7** : la campagne porte sur tous les modules calculants de
  `src/etl_benchmark` : 1661 mutants éliminés sur 1726 (96,23 %). Les 65
  survivants sont classés dans `mutation_notes.md`. Les scripts d'`experiments/`
  n'ont pas de campagne, donc le ticket reste ouvert.

## Protocole et mesures (#8 à #15)

- **#8–9** : les copies synthétiques restent dans la même partition et les
  détecteurs apprennent sur le train. Les cas temporels demandent un protocole
  distinct ; il reste des entrées limites à tester.
- **#10** : la contamination invalide est rejetée. Le benchmark réel accepte
  désormais un préréglage fixe sans labels et enregistre la politique choisie.
  Les tableaux principaux gardent le calibrage sur la prévalence du train ;
  une analyse de sensibilité avec le préréglage 0,02 sur les trois jeux réels
  est archivée séparément et présentée comme exploratoire. Un test modifie
  uniquement les labels du test et vérifie que le paramètre transmis aux
  détecteurs reste celui du train.
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
  non définis. Les trois benchmarks réels conservent maintenant les positions
  exactes des partitions après déduplication. Il reste à faire de même pour
  les essais synthétiques et à consigner les échecs de détecteur par essai.
- **#20** : quatre commandes CLI, les fichiers archivés et les quatre tableaux
  du manuscrit sont contrôlés. La relecture des légendes et des affirmations
  dans le texte reste à faire.
- **#21–23** : FAST tourne en CI, DEEP et REAL en local ; le profil est
  reconstruit à chaque FAST avec la révision courante. FAST et DEEP restent
  rouges. Les règles de protection
  distantes et l'historique des dénominateurs ne sont pas établis.
- **#22** : `make verify-faults` introduit quatorze défauts scientifiques, un
  par un, dans une copie temporaire du code et exige un échec du test prévu
  (`fault_matrix.md`). Il a révélé cinq lacunes, maintenant couvertes. Des
  règles vérifient qu'aucun skip, exclusion de couverture, erreur avalée ou
  mock des bibliothèques de calcul n'est introduit. Les défauts non injectés
  sont listés dans la matrice.
- **#24** : README, notes de données, figures et manuscrit ont été mis à jour
  après les nouveaux essais. La revue finale du mémoire reste ouverte.

## Suite du travail (#25 à #30)

- **#25** : le découpage chronologique et un suivi par fenêtre ont des tests
  sans accès au futur (`test_temporal_protocol.py`). Les entrées temporelles
  invalides et les résultats sans événement sont maintenant contrôlés. La saisonnalité, les
  métriques sur plusieurs changements et l'évaluation sur données réelles
  restent à étudier.
- **#26** : le contrat commun du registre s'applique à tout détecteur
  enregistré (`test_registry_contract.py`). Un autoencodeur CPU
  (`quality/autoencoder.py`) et des fenêtres causales (`quality/windows.py`)
  ont leurs tests de fuite, d'alignement et de reproductibilité ; le protocole
  est dans `deep_models.md`. Le modèle LSTM lui-même et tout résultat de
  tableau restent à faire (hors du périmètre de ce ticket).
- **#27** : les trois jeux réels présents ont été rejoués avec cinq graines.
  Water Quality et Cardio ont été comparés à leurs sources ; les copies locales
  sont maintenant contrôlées contre le manifeste. La révision du fichier
  Credit Card, les droits sous-jacents de Cardio et les partitions exactes
  restent à établir.
- **#28** : un essai borné sur 100, 300 et 900 lignes enregistre temps,
  allocation Python, tailles d'entrée et machine (`scaling.md`). Il manque
  une étude contrôlée plus large et la mémoire native.
- **#29** : les règles et Isolation Forest rejettent les colonnes
  d'entraînement vides, les infinis et les colonnes requises absentes ; les
  colonnes constantes ont des sorties finies. Il reste les classes extrêmes,
  les schémas changeants et les timestamps invalides dans les expériences.
- **#30** : attendre la résolution des points précédents, puis refaire les
  vérifications et les comparaisons publiées sur un état unique du dépôt.

Le ticket de coordination **#2** reste ouvert.
