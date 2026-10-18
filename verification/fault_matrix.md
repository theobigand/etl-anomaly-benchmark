# Défauts introduits volontairement

`make verify-faults` copie le code dans un répertoire temporaire, y introduit
un défaut scientifique à la fois et lance les tests ciblés dans un
sous-processus. Le défaut est détecté si au moins un test prévu échoue sur la
copie modifiée alors que les mêmes tests passent sur une copie intacte. Le
dépôt n'est jamais modifié et les résultats archivés ne sont pas touchés.
Ces essais durent environ une minute ; ils ne font pas partie de FAST.

| Défaut introduit | Test attendu | Résultat |
| --- | --- | --- |
| Le détecteur est ajusté sur les lignes évaluées au lieu du jeu d'entraînement. (`fit_ignores_training_frame`) | `test_held_out_values_do_not_affect_fitted_rule_statistics` | détecté ; 2 test(s) en échec |
| Le scaler et l'imputeur ML sont réajustés sur le lot évalué. (`fit_on_evaluation_data`) | `test_a_rows_score_does_not_depend_on_the_rest_of_the_evaluated_batch` | détecté ; 2 test(s) en échec |
| La colonne de vérité terrain est donnée au détecteur comme variable. (`label_as_feature`) | `test_detect_excludes_label_from_features` | détecté ; 2 test(s) en échec |
| Le seuil des détecteurs est calculé avec les labels du test. (`test_labels_set_contamination`) | `test_calibration_uses_train_only_and_ignores_fit_sample`, `test_test_labels_cannot_change_detector_calibration` | détecté ; 2 test(s) en échec |
| Le banc synthétique règle la contamination avec la partition de test. (`synthetic_calibration_on_test`) | `test_synthetic_calibration_ignores_held_out_labels` | détecté ; 1 test(s) en échec |
| Cinq lignes d'entraînement sont recopiées dans la partition de test. (`train_test_overlap`) | `test_split_is_a_partition`, `test_split_sizes_match_ratios` | détecté ; 3 test(s) en échec |
| Le banc synthétique découpe ligne par ligne : la copie d'un client peut se trouver des deux côtés. (`customer_copies_cross_partitions`) | `test_synthetic_groups_never_cross_partitions` | détecté ; 1 test(s) en échec |
| Le drapeau d'anomalie marque tout sauf la classe positive déclarée. (`wrong_positive_class`) | `test_features_drops_label_and_anomaly_columns` | détecté ; 2 test(s) en échec |
| Les métriques de classement reçoivent les drapeaux 0/1 à la place des scores. (`binary_flags_as_scores`) | `test_detect_keeps_the_graded_scores_of_the_detector` | détecté ; 3 test(s) en échec |
| Le PR-AUC est calculé à partir des drapeaux booléens. (`flags_as_pr_auc_input`) | `test_golden_metrics_use_continuous_scores` | détecté ; 1 test(s) en échec |
| Le z-score donne les valeurs fortes aux lignes normales. (`inverted_score_orientation`) | `test_zscore_uses_a_standard_deviation_of_exactly_one` | détecté ; 1 test(s) en échec |
| La précision par type compte les autres types d'anomalie comme négatifs. (`per_type_denominator`) | `test_per_type_golden_denominators` | détecté ; 1 test(s) en échec |
| L'agrégat sur les graines renvoie la première graine au lieu de la moyenne. (`first_seed_only`) | `test_two_seed_mean_and_sample_standard_deviation` | détecté ; 1 test(s) en échec |
| Un détecteur disparaît silencieusement du tableau de résultats. (`dropped_detector_run`) | `test_every_requested_detector_appears_in_the_results` | détecté ; 3 test(s) en échec |

## Défauts ajoutés ensuite

Neuf défauts complètent les quatorze premiers ; chacun est détecté par un
test nommé, la copie intacte passant les mêmes tests :

| Défaut | Test attendu |
| --- | --- |
| Découpage chronologique inversé : l'entraînement voit les événements récents (`temporal_future_in_training`) | `test_chronological_split_orders_instants_across_utc_offsets` |
| Les lignes de validation sont aussi dans l'entraînement (`validation_leaks_into_train`) | `test_split_is_a_partition` |
| Précision sans alerte rapportée comme 1 (`undefined_precision_as_perfect`) | `test_precision_with_no_flags_is_zero` |
| Scores ML d'orientation inversée (`ml_score_orientation_inverted`) | `test_ml_detector_score_ranks_outliers_highest` |
| Scores réordonnés avant la comparaison aux labels (`scores_misaligned_with_labels`) | `test_isolation_forest_separates_the_planted_positives` |
| Contamination lue sur les labels d'entraînement et de test (`calibration_includes_test_labels`) | `test_test_labels_cannot_change_detector_calibration` |
| Une seule graine évaluée, les autres disparaissent (`seeds_silently_truncated`) | `test_run_returns_mean_and_std_over_seeds` |
| REAL réussit sans contrôler les trois jeux (`empty_real_registry_passes`) | `test_real_verification_fails_on_an_empty_registry` |
| Campagne de mutation interrompue acceptée (`interrupted_mutation_run_accepted`) | `test_mutation_gate_rejects_an_unreliable_campaign_despite_a_high_score` |

## Défauts différés

Un défaut est différé tant que sa condition d'activation n'est pas remplie :

- altération d'un CSV réel (valeur de label, ligne supprimée) : exige REAL, donc
  les trois fichiers locaux ; activable avec `make verify-real` dans un
  environnement qui les contient ;
- écart de version d'une dépendance numérique : exige l'environnement
  alternatif du jalon de reproductibilité ;
- durée d'exécution déformée : aucune borne de durée n'est contrôlée, il n'y a
  donc rien à détecter.

## Lacunes que cette matrice a révélées

Au premier essai de la matrice, quatre défauts passaient tous les tests
existants et un cinquième n'était vu que par un test ajouté pendant la
campagne de mutation :

- un scaler ou un imputeur réajusté sur le lot évalué : les tests lisaient les
  attributs appris, pas le score d'une ligne ;
- des scores graduels remplacés par les drapeaux binaires dans le pipeline ;
- un détecteur qui disparaît du tableau de résultats ;
- le seuil du banc synthétique fixé à partir du test (le banc réel était
  contrôlé, pas le synthétique) ;
- un z-score d'orientation inversée, que seul
  `test_zscore_uses_a_standard_deviation_of_exactly_one` détecte.

Chacun a maintenant un test dédié.

## Garde-fous de politique

`tests/test_verification_policy.py` échoue si un test est ignoré ou attendu en
échec hors des tests marqués `real`, si le code de production avale une
erreur (`except: pass`, `suppress`), si la couverture reçoit une exclusion ou
un `pragma`, si un test remplace une bibliothèque de calcul (sklearn, pyod,
numpy, pandas, scipy) ou `compute_metrics`, ou si un module de tests
obligatoires disparaît. Chaque règle est d'abord essayée sur un extrait fautif.

## Défauts non couverts

Ces cas ne sont pas encore injectés, soit parce que le code n'existe pas, soit
parce qu'aucun test n'a été écrit pour eux :

- règle d'arrêt anticipé ou réglage d'hyperparamètres sur le test (aucun
  modèle entraîné par descente de gradient n'existe encore, voir #26) ;
- choix du seuil de la courbe précision-rappel à partir du test ;
- imputation par la médiane du jeu complet dans une analyse hors pipeline ;
- erreurs d'arrondi dans les tableaux du manuscrit (couvertes seulement par la
  comparaison aux CSV archivés) ;
- fuite par la validation : la partition de validation n'est utilisée par
  aucun détecteur, donc aucun défaut ne peut encore la faire apparaître.
