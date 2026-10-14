# Fonctions, tests et risques

Cet inventaire couvre les fonctions définies dans `src/etl_benchmark` et
`experiments` au 14 octobre 2026. Un test indiqué signifie qu'il exécute ou
contrôle le comportement concerné ; ce n'est pas une preuve de couverture
complète de toutes ses branches. Les nombres exacts sont dans le rapport de
couverture produit par `make verify-fast`.

| Surface et fonctions | Tests principaux | Point encore ouvert |
| --- | --- | --- |
| `datasets`: `load`, `features` | `test_datasets.py`, `test_dataset_contract.py`, `test_real_verification.py` | Source et droits des CSV (#12, #27). |
| `extract.read_csv`, `transform.clean`, `load.write_csv` | `test_pipeline_integration.py`, `test_pipeline.py` | Pannes de lecture ou d'écriture (#16). |
| `metrics.compute_metrics` | `test_metric_contract.py` | Mutants survivants (#7). |
| `pipeline`: `DetectionResult.detect_s`, `_features`, `detect`, `run_pipeline` | `test_pipeline.py`, `test_detector_protocol.py`, `test_pipeline_integration.py`, `test_scaling_study.py` | Panne partielle d'écriture (#16). |
| `quality.base`: `numeric_features`, `Detector.fit`, `predict`, `score`, `fit_predict` | `test_detector_protocol.py`, `test_adverse_schemas.py` | Les méthodes abstraites ne sont pas des détecteurs utilisables directement. |
| `quality.rules`: `ZScoreDetector.__init__`, `fit`, `_zscores`, `predict`, `score`; `IQRDetector.__init__`, `fit`, `_exceedance`, `predict`, `score` | `test_zscore.py`, `test_iqr.py`, `test_adverse_schemas.py` | Schémas défavorables supplémentaires (#29). |
| `quality.gx`: `GreatExpectationsDetector.__init__`, `fit`, `_failures_per_row`, `predict`, `score` | `test_gx.py`, `test_synthetic_benchmark.py` | Branche d'erreur externe et coût sur grands jeux (#28). |
| `quality.ml`: `PyODDetector.__init__`, `_build_estimator`, `_numeric_columns`, `_matrix`, `_fitted_model`, `fit`, `predict`, `score` | `test_ml.py`, `test_detector_protocol.py`, `test_adverse_schemas.py` | Calibration sans labels et perturbations de schéma (#10, #29). |
| `quality.drift`: `TemporalDriftDetector.__init__`, `fit`, `_guard`, `_z`, `_is_recent`, `_row_score`, `predict`, `score` | `test_drift.py` | Ce score par ligne ne mesure pas la qualité des alertes par fenêtre (#25). |
| `quality.window_drift`: `_times`, `_numeric`, `WindowDriftMonitor.__init__`, `fit`, `evaluate`, `event_metrics` | `test_temporal_protocol.py` | Saison et plusieurs changements (#25). |
| `registry`: `clip_contamination`, `calibrate_contamination`, `get_detector`, `all_detectors` | `test_registry.py`, `test_scientific_contracts.py` | Ajout d'une nouvelle famille (#26). |
| `split`: `stratified_split`, `chronological_split` | `test_split.py`, `test_properties.py`, `test_temporal_protocol.py` | Partitions exactes des essais synthétiques (#18). |
| `synthetic`: `_clean_population`, `_inject_missing_value`, `_inject_univariate_outlier`, `_inject_multivariate_outlier`, `_inject_temporal_drift`, `_inject_invalid_format`, `make_synthetic` | `test_synthetic.py`, `test_properties.py`, `test_scientific_contracts.py` | Champs non modifiés et sévérités limites (#11). |
| `__main__.main`, `logging_setup.setup_logging` | `test_cli_smoke.py`, `test_pipeline_integration.py` | La commande de démonstration passe sur de petits CSV. |
| `config` et initialisations de paquet | Import dans les tests et commandes | Configuration statique ; contrôler l'installation (#21). |
| `run_benchmark`: `evaluate`, `run`, `to_markdown`, `main` | `test_run_benchmark.py`, `test_cli_smoke.py`, `test_publication_tables.py` | Essais individuels et échecs de détecteur (#18, #19). |
| `run_synthetic_benchmark`: `_split_synthetic`, `_per_type`, `_dedup_flags_for`, `evaluate`, `run`, `render_heatmap`, `_combined_md`, `main` | `test_scientific_contracts.py`, `test_synthetic_benchmark.py`, `test_cli_smoke.py` | Méthodes/types ajoutés et erreur de figure (#20, #29). |
| `run_curves`: `_split_real`, `_split_synth`, `scores_for`, `render_pr`, `contamination_sweep`, `main` | `test_curves_protocol.py`, `test_cli_smoke.py` | Jeu réel miniature et absence de données contrôlés ; sensibilité sur plusieurs graines à étendre. |
| `run_severity`: `run`, `render`, `main` | `test_cli_smoke.py` | Coût des essais étendus à mesurer (#28). |
| `generate_synthetic.main`, `fetch_cardio.main` | `test_cli_smoke.py` | Conversion Cardio testée avec une archive locale ; droits de la source à établir (#27). |
| `provenance`: `_hash_file`, `_source_fingerprint`, `write_record` | `test_provenance.py`, `test_artifact_lineage.py` | Lier les identifiants de partition et les échecs (#18). |
| `verification_report`: `_metric`, `build_report`, `main`; `check_mutation`: `classify`, `main` | `test_verification_report.py`, `test_mutation_gate.py` | Tester les commandes et les rapports absents ou malformés (#22, #23). |
| `verify_real`: `inspect_dataset`, `main` | `test_real_verification.py`, `make verify-real` | Conditions d'usage et intégrité de la source (#27). |

La couverture actuelle atteint toutes les lignes et branches instrumentées ;
elle ne mesure pas la capacité des assertions à détecter une erreur. Le risque
prioritaire reste une erreur qui changerait un résultat publié :
découpage, colonnes apprises, choix du seuil, définition des métriques et
production des figures. Les tests de protocole et de filiation les contrôlent
en partie. La mutation et les contre-exemples restent nécessaires pour
évaluer la force de ces contrôles.
