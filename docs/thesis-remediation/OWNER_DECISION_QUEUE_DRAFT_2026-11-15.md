# Preliminary consolidated owner decision queue

**Incomplete draft; no approval is recorded.** This queue consolidates historical survivors from the two existing packets and the new conditional proposals. It is not a fresh campaign, a recommendation to approve, or certification. Individual investigation remains incomplete, and owner decisions require current complete measurements and the official validator. The four already accepted and five previously inconclusive LSTM records retain their existing verdicts and are not re-proposed.

All arithmetic below uses only the historical mixed-environment ledger. Focused kills are not added. “All proposed” is hypothetical and assumes every listed proposal for that unit is approved; it is not an authorized score. A failing unit marked no remains below threshold even under that hypothetical and needs further investigation or remediation. Current source SHA-256 and generated catalog identities matched the listed historical digests in the local checks; this does not validate mutant outcomes.

| Historically failing unit | Historical raw | Proposals | Hypothetical if all approved | Crosses threshold? |
| --- | --- | ---: | --- | --- |
| `experiments/run_severity.py` | 320/329 | 5 | 320/324 (98.77%) | yes |
| `research/injection.py` | 325/336 | 4 | 325/332 (97.89%) | no |
| `research/lstm_detector.py` | 368/377 | 0 | 368/377 (97.61%) | no |
| `research/multi_schema.py` | 1057/1093 | 16 | 1057/1077 (98.14%) | yes |
| `research/normalise.py` | 191/197 | 6 | 191/191 (100.00%) | yes |
| `research/pool_chrono.py` | 300/316 | 6 | 300/310 (96.77%) | no |
| `research/pool_preprocessing.py` | 241/248 | 4 | 241/244 (98.77%) | yes |
| `research/temporal_decision.py` | 810/836 | 9 | 810/827 (97.94%) | no |
| `research/typed_benchmark.py` | 175/180 | 3 | 175/177 (98.87%) | yes |
| `research/uci_loader.py` | 180/186 | 1 | 180/185 (97.30%) | no |
| `src/etl_benchmark/load.py` | 13/14 | 1 | 13/13 (100.00%) | yes |
| `src/etl_benchmark/quality/_torch_models.py` | 58/65 | 3 | 58/62 (93.55%) | no |
| `src/etl_benchmark/quality/autoencoder.py` | 112/117 | 2 | 112/115 (97.39%) | no |
| `src/etl_benchmark/quality/base.py` | 30/31 | 1 | 30/30 (100.00%) | yes |
| `src/etl_benchmark/quality/deep.py` | 60/62 | 2 | 60/60 (100.00%) | yes |
| `src/etl_benchmark/quality/drift.py` | 119/129 | 2 | 119/127 (93.70%) | no |
| `src/etl_benchmark/quality/gx.py` | 87/98 | 6 | 87/92 (94.57%) | no |
| `src/etl_benchmark/quality/ml.py` | 239/259 | 6 | 239/253 (94.47%) | no |
| `src/etl_benchmark/quality/rules.py` | 112/119 | 2 | 112/117 (95.73%) | no |
| `src/etl_benchmark/quality/window_drift.py` | 225/233 | 2 | 225/231 (97.40%) | no |
| `src/etl_benchmark/quality/windows.py` | 54/57 | 3 | 54/54 (100.00%) | yes |
| `verification/mutation_scope.py` | 240/246 | 6 | 240/240 (100.00%) | yes |

The LSTM row excludes no owner records in this table. A later scoped Linux run validated the four existing owner records on db27f56 and measured 368/373 (98.66%); see DIAGNOSTIC_43718624552.md. That result is specific to that tested commit and shard and is not a complete campaign or a new owner decision.

## Individual proposed identities

The source and catalog SHA-256 shown for each unit are historical values checked against the current source and locally generated catalog, not fresh verdicts. “Alone” means hypothetically excluding only that candidate from the historical denominator; “already pass” means the raw historical unit was already at threshold. Evidence links lead to the preserved detailed packet or probe; the prior packet categories remain historical assessments and have not been independently refreshed.

### `experiments/run_severity.py`

Historical raw: 320/329; L4 threshold 98%. Source SHA-256: `7bda7511594ba6313e9579805a0726fd04ce06382f10d2fcb6c06e4d90f0a3fd`. Catalog SHA-256: `f41e59f70fb61d7df4d44bd4d2bde8ca593ef8d1972345b3e1a06fddafb51f93`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `experiments.run_severity.x_main__mutmut_87` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `experiments.run_severity.x_render__mutmut_24` | new probe: conditional; see individual evidence | insufficient | [record](SEVERITY_ZIP_EQUIVALENCE_PROBE_2026-11-15.md) |
| `experiments.run_severity.x_render__mutmut_27` | new probe: conditional; see individual evidence | insufficient | [record](SEVERITY_ZIP_EQUIVALENCE_PROBE_2026-11-15.md) |
| `experiments.run_severity.x_render__mutmut_28` | new probe: conditional; see individual evidence | insufficient | [record](SEVERITY_ZIP_EQUIVALENCE_PROBE_2026-11-15.md) |
| `experiments.run_severity.x_run__mutmut_31` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `research/alert_budget.py`

Historical raw: 777/780; L4 threshold 98%. Source SHA-256: `0da6a79ece4e6cbd8066eb2474f653ba69eb2247caeeb0f77e3cf9b48be5a7e9`. Catalog SHA-256: `915d24939fd557d28c76bc48d060bab0edc0af26309281c6bbfb5b3b375a6d8d`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.alert_budget.x__counts__mutmut_50` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.alert_budget.x_run_method__mutmut_23` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.alert_budget.x_run_method__mutmut_54` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/build_pool.py`

Historical raw: 169/172; L4 threshold 98%. Source SHA-256: `eefa0438f61e44b0bd0c7ed9a8acf7477a181477c4c8c90dc51803fa6391b3f6`. Catalog SHA-256: `8376de93b7f33099e83dea80a0bdf12328a907743b11c7f2941b397e7a0bde2c`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.build_pool.x_main__mutmut_27` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.build_pool.x_main__mutmut_30` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.build_pool.x_pool_row__mutmut_38` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/injection.py`

Historical raw: 325/336; L4 threshold 98%. Source SHA-256: `cdfc81d98e3470ccdf5f7930d7e987b1bdad3545e060552f3a3bb1d170d8cb39`. Catalog SHA-256: `011af65d555b37c695f69c7dc6c29dd46147cfd2d5f31a34cafc67f9be06d836`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.injection.x__pair__mutmut_9` | new probe: conditional; see individual evidence | insufficient | [record](INJECTION_UNIT_PROBE_2026-11-15.md) |
| `research.injection.x_continuous_columns__mutmut_5` | new probe: conditional; see individual evidence | insufficient | [record](INJECTION_UNIT_PROBE_2026-11-15.md) |
| `research.injection.x_inject__mutmut_163` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.injection.x_inject__mutmut_78` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `research/lstm_detector.py`

Historical raw: 368/377; L4 threshold 98%. Source SHA-256: `277375e66d1edc6ed94c5ffc4b1074c113e86c6095c7dc2b20d3058cb006da18`. Catalog SHA-256: `aef20963dc44e0ca61b2c9e9744bdf76a552d33490a96ed8e51b592a9cacfbc2`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |

### `research/matched_alert.py`

Historical raw: 320/322; L4 threshold 98%. Source SHA-256: `dac27eab8804462e153242158a3cea09c965809de189a9f398e4ee33a27657b3`. Catalog SHA-256: `c9283ec7191fcbd76aa0c4e2684ab77b25b989ff5317a5ba27f8621388d1f2b5`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.matched_alert.x_analyse__mutmut_20` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.matched_alert.x_compare__mutmut_43` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/multi_schema.py`

Historical raw: 1057/1093; L4 threshold 98%. Source SHA-256: `1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`. Catalog SHA-256: `918fe1d065502424f49fc3619516bd519c04c951dfc6f9efda87df4bf789b624`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.multi_schema.x__dates__mutmut_31` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x__dates__mutmut_34` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x__dates__mutmut_35` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x__split__mutmut_5` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.multi_schema.x_evaluate__mutmut_68` | new probe: conditional; see individual evidence | insufficient | [record](TYPED_INDEX_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_evaluate__mutmut_70` | new probe: conditional; see individual evidence | insufficient | [record](TYPED_INDEX_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_106` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.multi_schema.x_main__mutmut_23` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_27` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_35` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_36` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_70` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_73` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_74` | new probe: conditional; see individual evidence | insufficient | [record](MULTISCHEMA_DATES_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.multi_schema.x_main__mutmut_99` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.multi_schema.x_make__mutmut_111` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `research/normalise.py`

Historical raw: 191/197; L4 threshold 98%. Source SHA-256: `5ba131d186d79c792fb64691089939fffb3a085e1f376c6b9dcd1c12bcf5155a`. Catalog SHA-256: `fc5f5c3a0445d43054017cca9eb565f9765360e1590f5b7433cbc817ab36804c`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.normalise.x_clean__mutmut_34` | first packet: Strong equivalence evidence | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.normalise.x_clean__mutmut_35` | first packet: Additional verification required | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.normalise.x_clean__mutmut_45` | first packet: Strong equivalence evidence | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.normalise.x_clean__mutmut_48` | first packet: Strong equivalence evidence | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.normalise.x_clean__mutmut_51` | first packet: Strong equivalence evidence | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.normalise.x_clean__mutmut_64` | first packet: Additional verification required | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/pool_check.py`

Historical raw: 178/180; L4 threshold 98%. Source SHA-256: `5981ee3fea87f589524072ba00084682547a2435ea816bf62b92da414f776c96`. Catalog SHA-256: `51febc8d6bdafe700609429ec61428d80f9f5008eea7b190d2ec2a12732504fd`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.pool_check.x_main__mutmut_27` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.pool_check.x_main__mutmut_30` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/pool_chrono.py`

Historical raw: 300/316; L4 threshold 98%. Source SHA-256: `cd8b6eff471b942804223040ca94f119f2ab710479c341dfd3d2668342eff035`. Catalog SHA-256: `206639c66988bdbe63db29b095048244379c35633f8e24080ec259c6e1b2568a`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.pool_chrono.x_eligible__mutmut_12` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.pool_chrono.x_read_times__mutmut_18` | new probe: conditional; see individual evidence | insufficient | [record](POOL_CHRONO_UPPERCASE_PROBE_2026-11-15.md) |
| `research.pool_chrono.x_read_times__mutmut_21` | new probe: conditional; see individual evidence | insufficient | [record](POOL_CHRONO_UPPERCASE_PROBE_2026-11-15.md) |
| `research.pool_chrono.x_read_times__mutmut_25` | new probe: conditional; see individual evidence | insufficient | [record](POOL_CHRONO_UPPERCASE_PROBE_2026-11-15.md) |
| `research.pool_chrono.x_read_times__mutmut_31` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.pool_chrono.x_read_times__mutmut_37` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `research/pool_preprocessing.py`

Historical raw: 241/248; L4 threshold 98%. Source SHA-256: `edf8ac28b2824c76840c8e4cad47fe3fee1f1ac84a5b38ad341e968dee9e8dc0`. Catalog SHA-256: `453ee4bae71c1a333674fdcc286423b3d8ec1d129cb5e9f502e9babef1c7c959`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.pool_preprocessing.x__numeric__mutmut_9` | new probe: conditional; see individual evidence | insufficient | [record](POOL_NUMERIC_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.pool_preprocessing.x_prepare_frozen__mutmut_16` | new probe: conditional; see individual evidence | insufficient | [record](POOL_NUMERIC_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.pool_preprocessing.x_prepare_frozen__mutmut_18` | new probe: conditional; see individual evidence | insufficient | [record](POOL_NUMERIC_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.pool_preprocessing.x_prepare_frozen__mutmut_23` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `research/pool_typed.py`

Historical raw: 521/525; L4 threshold 98%. Source SHA-256: `0b477c1c51fc616596b5ed3b09841a0374f1bc26603f22a2bc7c7ee638a8bbad`. Catalog SHA-256: `eaca1600c7831c2cd9e392d7b11f17facb0b34efbb907563181d17efee170623`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.pool_typed.x_load_carrier__mutmut_29` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.pool_typed.x_run_reference__mutmut_33` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.pool_typed.x_run_reference__mutmut_45` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.pool_typed.x_run_severity__mutmut_28` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/prevalence_shift.py`

Historical raw: 366/369; L4 threshold 98%. Source SHA-256: `d89afbf352b0ca891de4dfbd1a6507b20e48f55745752d0e6f715ee3943567b3`. Catalog SHA-256: `61b828c5c6044a1711dc3686b43952467fcd16a4fed09a8e5c3bca9c1834e734`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.prevalence_shift.x_contrasts__mutmut_59` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.prevalence_shift.x_contrasts__mutmut_62` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.prevalence_shift.x_contrasts__mutmut_63` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/score_shift.py`

Historical raw: 800/806; L4 threshold 98%. Source SHA-256: `a96e39bb1b80cbaacd00d31f8986a3f2cda350564d316be002dc589c9d801ef6`. Catalog SHA-256: `05a61a82954d6dc47534f6c49b48f613289103a591aeae75e53a0f1455774852`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.score_shift.x_monitor_table__mutmut_39` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.score_shift.x_monitor_table__mutmut_48` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.score_shift.x_run_method__mutmut_23` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.score_shift.x_run_method__mutmut_25` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.score_shift.x_run_method__mutmut_39` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.score_shift.x_run_method__mutmut_41` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/source_clustered.py`

Historical raw: 336/337; L4 threshold 98%. Source SHA-256: `a9bf13c575ea6e33c6055a9da5f23ee5f9c71ff1e0329815343a821008764352`. Catalog SHA-256: `01a659dc95eb8fb1b996b8453229f9d186132d5da6c781ddf32faca74ce850da`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.source_clustered.x_source_id__mutmut_3` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/temporal_decision.py`

Historical raw: 810/836; L4 threshold 98%. Source SHA-256: `f402ba92cdbd8a143608f9ce9d1ab98f68cad5b6c881318f504ab8c0380742d8`. Catalog SHA-256: `c68abc303f77fdba2712116081978338289ce8e457758a0f5c7556a99186b466`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.temporal_decision.x_bank_marketing__mutmut_48` | new probe: conditional; see individual evidence | insufficient | [record](BANK_TIMESTAMP_CASE_PROBE_2026-11-15.md) |
| `research.temporal_decision.x_bank_marketing__mutmut_50` | new probe: conditional; see individual evidence | insufficient | [record](BANK_TIMESTAMP_CASE_PROBE_2026-11-15.md) |
| `research.temporal_decision.x_bank_marketing__mutmut_54` | new probe: conditional; see individual evidence | insufficient | [record](BANK_TIMESTAMP_CASE_PROBE_2026-11-15.md) |
| `research.temporal_decision.x_bank_marketing__mutmut_57` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.temporal_decision.x_bank_marketing__mutmut_63` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.temporal_decision.x_credit_card__mutmut_11` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.temporal_decision.x_match_prevalence__mutmut_27` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.temporal_decision.x_match_prevalence__mutmut_51` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `research.temporal_decision.x_run_frame__mutmut_20` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `research/temporal_pilot.py`

Historical raw: 580/589; L4 threshold 98%. Source SHA-256: `03e63b2961126c3192fec7fbf374b434e0ab81c54a1317c3cfa99ecb732b0982`. Catalog SHA-256: `cc22ccb0d5ce93621a446a2041a971e3971144d1f710ada7002d7b198b0fe32e`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.temporal_pilot.x_block_bootstrap_ci__mutmut_38` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_main__mutmut_18` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_monitor_control__mutmut_101` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_monitor_control__mutmut_104` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_monitor_control__mutmut_56` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_monitor_control__mutmut_58` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_monitor_control__mutmut_61` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_monitor_control__mutmut_99` | first packet: Strong equivalence evidence | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.temporal_pilot.x_to_timestamps__mutmut_11` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/typed_benchmark.py`

Historical raw: 175/180; L4 threshold 98%. Source SHA-256: `abdd10e4a1965e99bd5db8ad1a61b0b9e37caed20f35d09c32bcb1a9a3bae9d2`. Catalog SHA-256: `2b7aff2c3664116170e04eeb7a6d3f22dceaf94bd48fa0e67e5b4846865de3fb`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.typed_benchmark.x_evaluate__mutmut_53` | new probe: conditional; see individual evidence | insufficient | [record](TYPED_INDEX_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.typed_benchmark.x_evaluate__mutmut_55` | new probe: conditional; see individual evidence | insufficient | [record](TYPED_INDEX_EQUIVALENCE_PROBE_2026-11-15.md) |
| `research.typed_benchmark.x_split__mutmut_5` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `research/typed_run.py`

Historical raw: 349/351; L4 threshold 98%. Source SHA-256: `8589c4634fd7ffff31536e85772f2a84b6edc2f3a59c6860e8ff916abb76beb0`. Catalog SHA-256: `e3bae5fa8f6aa1c58ea06c4939ffdcc849f86461e0818291f8334b524cd93fa9`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.typed_run.x_run_one__mutmut_48` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |
| `research.typed_run.x_run_one__mutmut_55` | first packet: Additional verification required | already pass | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `research/uci_loader.py`

Historical raw: 180/186; L4 threshold 98%. Source SHA-256: `a1176cd61bd8454c9fa51da682194444feb24529dc401916e8bb94fd212ab691`. Catalog SHA-256: `6631cb8a4619d97b501bccd946c81c1006b962b6040613ea6dd8f35453c601ac`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `research.uci_loader.x_derive_labels__mutmut_73` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `src/etl_benchmark/load.py`

Historical raw: 13/14; L4 threshold 98%. Source SHA-256: `bc450a2553f333662bb447de1c7cd9aabb274b2f608b8e57ad80e48321b9c98e`. Catalog SHA-256: `cc261ce7827925bd34d67f62212c84c83724a60a6d486133bda58616d471f706`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.load.x_write_csv__mutmut_11` | first packet: Additional verification required | crosses | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `src/etl_benchmark/quality/_torch_models.py`

Historical raw: 58/65; L4 threshold 98%. Source SHA-256: `77a1b57ff69e580cad700bb4ee41f069e3ac0c8489bdd714651c753c4bbdd09d`. Catalog SHA-256: `b324cbcab5f51653633917045d5aa8a4f2ee2a7e12a8be31042bd7b481ee8a7b`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality._torch_models.xǁFitScalerDIFǁ_deep_representation__mutmut_5` | new probe: conditional; see individual evidence | insufficient | [record](DIF_LOADER_DEFAULTS_PROBE_2026-11-15.md) |
| `etl_benchmark.quality._torch_models.xǁFitScalerDIFǁ_deep_representation__mutmut_8` | new probe: conditional; see individual evidence | insufficient | [record](DIF_LOADER_DEFAULTS_PROBE_2026-11-15.md) |
| `etl_benchmark.quality._torch_models.xǁFitScalerDIFǁ_deep_representation__mutmut_9` | new probe: conditional; see individual evidence | insufficient | [record](DIF_LOADER_DEFAULTS_PROBE_2026-11-15.md) |

### `src/etl_benchmark/quality/autoencoder.py`

Historical raw: 112/117; L4 threshold 98%. Source SHA-256: `52ac93bd1898db05567278d773295458fc81847366de74b0c63770c662cbaa4d`. Catalog SHA-256: `1fc31435087cff28de27c15aa9e3989daf7c5295af2c17f4c1d0fe4943360262`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.autoencoder.xǁAutoencoderDetectorǁsettings__mutmut_28` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `etl_benchmark.quality.autoencoder.xǁAutoencoderDetectorǁsettings__mutmut_33` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `src/etl_benchmark/quality/base.py`

Historical raw: 30/31; L4 threshold 98%. Source SHA-256: `9efc8a6a410b92d81f4ee09f9d001f8adad62a779250b3b552db9878f9de28ff`. Catalog SHA-256: `fa09c2c86ed2f77bf715f144b9d29023ff9fb101061b5bf7aea7e0c05f8fe55f`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.base.xǁDetectorǁscore__mutmut_1` | first packet: Additional verification required | crosses | [record](OWNER_EQUIVALENCE_REVIEW_2026-11-12.md) |

### `src/etl_benchmark/quality/deep.py`

Historical raw: 60/62; L4 threshold 98%. Source SHA-256: `77364cfdf0850b107c316ffae0389e1bb552445d76188dab388dff76e8e22632`. Catalog SHA-256: `718d9fa22e977bf984b2e1a008dc7117a7146265a6b3c5bd1c6c1daf6047588b`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.deep.xǁTorchDetectorǁsettings__mutmut_19` | second packet: pattern proposal; individual verification pending | crosses | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `etl_benchmark.quality.deep.xǁTorchDetectorǁsettings__mutmut_24` | second packet: pattern proposal; individual verification pending | crosses | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

### `src/etl_benchmark/quality/drift.py`

Historical raw: 119/129; L4 threshold 98%. Source SHA-256: `95380ca0f8f87a24c512ac7055357225472342065e0da676c0be46dd115fa09b`. Catalog SHA-256: `6cb454d92e0c732b4bc49a59f97c3091592bccb5169d47afa34c78ca4ac5a5bc`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ_row_score__mutmut_33` | new probe: conditional; see individual evidence | insufficient | [record](DRIFT_BOUNDARY_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.drift.xǁTemporalDriftDetectorǁ_row_score__mutmut_43` | new probe: conditional; see individual evidence | insufficient | [record](DRIFT_GROSS_NULL_PROBE_2026-11-15.md) |

### `src/etl_benchmark/quality/gx.py`

Historical raw: 87/98; L4 threshold 98%. Source SHA-256: `11be59dbe975d05547395263b763d37716cd9f916b284ce4147cfd87c61e3416`. Catalog SHA-256: `ddd89891c20d1b4e84f3919f603b7f4977112dbe7ad4ce179914c846ffa53b34`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_17` | new probe: conditional; see individual evidence | insufficient | [record](GX_NAME_EQUIVALENCE_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_18` | new probe: conditional; see individual evidence | insufficient | [record](GX_NAME_EQUIVALENCE_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_19` | new probe: conditional; see individual evidence | insufficient | [record](GX_NAME_EQUIVALENCE_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_20` | new probe: conditional; see individual evidence | insufficient | [record](GX_NAME_EQUIVALENCE_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_21` | new probe: conditional; see individual evidence | insufficient | [record](GX_NAME_EQUIVALENCE_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.gx.xǁGreatExpectationsDetectorǁ_failures_per_row__mutmut_22` | new probe: conditional; see individual evidence | insufficient | [record](GX_NAME_EQUIVALENCE_PROBE_2026-11-15.md) |

### `src/etl_benchmark/quality/ml.py`

Historical raw: 239/259; L4 threshold 98%. Source SHA-256: `4b1c2db9f3a65721f08e92962413c90b134b0d0af1901cef7652cc4e431084b0`. Catalog SHA-256: `38467af6141e58f9b103b94e980082662d5e9710529b6a3c1dbe75fd6c31f200`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.ml.xǁPCAReconstructionǁ__init____mutmut_12` | new probe: conditional; see individual evidence | insufficient | [record](ML_DEFAULTS_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.ml.xǁPyODDetectorǁ_matrix__mutmut_11` | new probe: conditional; see individual evidence | insufficient | [record](RULES_EQUIVALENCE_PROBES_2026-11-15.md) |
| `etl_benchmark.quality.ml.xǁTailProbabilityModelǁ__init____mutmut_13` | new probe: conditional; see individual evidence | insufficient | [record](ML_DEFAULTS_PROBE_2026-11-15.md) |
| `etl_benchmark.quality.ml.xǁTailProbabilityModelǁdecision_function__mutmut_26` | new probe: conditional; see individual evidence | insufficient | [record](RULES_EQUIVALENCE_PROBES_2026-11-15.md) |
| `etl_benchmark.quality.ml.xǁTailProbabilityModelǁdecision_function__mutmut_48` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `etl_benchmark.quality.ml.xǁTailProbabilityModelǁfit__mutmut_13` | new probe: conditional; see individual evidence | insufficient | [record](ML_DEFAULTS_PROBE_2026-11-15.md) |

### `src/etl_benchmark/quality/rules.py`

Historical raw: 112/119; L4 threshold 98%. Source SHA-256: `bbd2e146be1d55382a12137cdfacefa85223d535c8b9eeaf816d17e6acd49737`. Catalog SHA-256: `dd0c412f18b7a2ca32f0408af6a09e820dda7ed2f820a92216a558e665f0c0b5`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.rules.xǁIQRDetectorǁ_exceedance__mutmut_9` | new probe: conditional; see individual evidence | insufficient | [record](RULES_EQUIVALENCE_PROBES_2026-11-15.md) |
| `etl_benchmark.quality.rules.xǁZScoreDetectorǁ_zscores__mutmut_8` | new probe: conditional; see individual evidence | insufficient | [record](RULES_EQUIVALENCE_PROBES_2026-11-15.md) |

### `src/etl_benchmark/quality/window_drift.py`

Historical raw: 225/233; L4 threshold 98%. Source SHA-256: `7369796bac2ada0ee25c125b383752c8d40d7f683e287767dfb6b373108ea8d7`. Catalog SHA-256: `75668e96d48177014b765721302e383a9446fb7d1cb0c28f924cb12535787aca`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.window_drift.x_event_metrics__mutmut_25` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `etl_benchmark.quality.window_drift.x_event_metrics__mutmut_29` | new probe: conditional; see individual evidence | insufficient | [record](WINDOW_UTC_CASE_PROBE_2026-11-15.md) |

### `src/etl_benchmark/quality/windows.py`

Historical raw: 54/57; L4 threshold 98%. Source SHA-256: `5a4fdd8739edcc33dd786b2b241cf5c3c92ec3e63f6e669ef571d1cb9699c864`. Catalog SHA-256: `d1eb4229b9e0fe174ba43d53240069fbd234b8c73dac68e9601a1595097ee52d`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `etl_benchmark.quality.windows.x_causal_windows__mutmut_26` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `etl_benchmark.quality.windows.x_scores_to_events__mutmut_7` | new probe: conditional; see individual evidence | insufficient | [record](WINDOWS_EQUIVALENCE_PROBES_2026-11-15.md) |
| `etl_benchmark.quality.windows.x_scores_to_events__mutmut_9` | new probe: conditional; see individual evidence | insufficient | [record](WINDOWS_EQUIVALENCE_PROBES_2026-11-15.md) |

### `verification/mutation_scope.py`

Historical raw: 240/246; L4 threshold 98%. Source SHA-256: `622f62cf9104148fb33c7cf80595ffdf32ade43f5decd3d7cc3e8db06aa13b0a`. Catalog SHA-256: `fb44249a6a7d20064117a56fd6acffb3d355a923f6b52160230bdda5b57eded4`.

| Mutant identity | Origin and evidence strength | Alone | Evidence |
| --- | --- | --- | --- |
| `verification.mutation_scope.x__walk__mutmut_11` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `verification.mutation_scope.x__walk__mutmut_16` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `verification.mutation_scope.x__walk__mutmut_19` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `verification.mutation_scope.x__walk__mutmut_22` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `verification.mutation_scope.x__walk__mutmut_25` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |
| `verification.mutation_scope.x__walk__mutmut_6` | second packet: pattern proposal; individual verification pending | insufficient | [record](OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md) |

## Still unresolved

The 162-record triage currently contains 76 inconclusive identities, 37 focused kills and 49 new proposals. These numbers are not a full campaign, and any pending behavioral differences or infrastructure problems remain in the triage artifact. No proposal is an approval.

Reproduce from the repository root with the locally generated mutation catalog present: `PYTHONPATH=. python docs/thesis-remediation/evidence/build-owner-queue-2026-11-15.py.txt`. The script checks identities and historical catalog digests; it does not execute mutants.
