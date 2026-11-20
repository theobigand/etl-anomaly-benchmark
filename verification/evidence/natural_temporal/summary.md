# Naturally labelled chronological study: results

Series evaluated: 20 of 81; independent source groups: 10 (nab_adexchange, nab_ambient, nab_asg, nab_aws, nab_latency, nab_machine, nab_taxi, nab_traffic, nab_tweets, skab).

- N1: chronological PR-AUC below stratified for 16.8% of 340 (series, detector) pairs; share rule not met; detectors whose group-level median difference interval is below zero: 0 of 17.
- N1 on the lift over prevalence (exploratory, prevalence-adjusted): chronological lower for 34.1% of pairs; detectors with an interval below zero: 0 of 17.
- N2: median Spearman between arms 0.49 (not supported).
- N3: matching closes at least half of the gap in 12 of 20 series.
- N4: Friedman over 10 source groups, p = 0.000847.

| Detector | Mean rank | 95 % interval | Median chronological - stratified | 95 % interval |
|---|---|---|---|---|
| lunar | 4.20 | 2.20 to 7.30 | +0.318 | +0.147 to +0.488 |
| knn | 5.40 | 2.80 to 8.50 | +0.226 | +0.076 to +0.473 |
| dif | 6.70 | 3.60 to 10.30 | +0.215 | +0.018 to +0.480 |
| lof | 7.20 | 5.00 to 9.70 | +0.293 | +0.117 to +0.624 |
| ocsvm | 7.50 | 6.00 to 9.30 | +0.239 | +0.109 to +0.468 |
| pca | 7.80 | 4.00 to 11.60 | +0.174 | +0.114 to +0.430 |
| vae | 8.10 | 6.70 to 9.70 | +0.208 | +0.084 to +0.490 |
| ae1svm | 8.50 | 6.70 to 10.10 | +0.240 | +0.099 to +0.502 |
| zscore | 8.50 | 5.60 to 11.40 | +0.214 | +0.101 to +0.463 |
| isolation_forest | 9.40 | 7.20 to 11.60 | +0.192 | +0.093 to +0.431 |
| autoencoder | 9.70 | 7.80 to 11.70 | +0.207 | +0.101 to +0.491 |
| copod | 10.20 | 8.20 to 12.20 | +0.222 | +0.103 to +0.521 |
| hbos | 10.80 | 7.30 to 14.20 | +0.171 | +0.084 to +0.371 |
| iqr | 10.90 | 8.00 to 13.50 | +0.200 | +0.100 to +0.411 |
| ecod | 12.10 | 10.80 to 13.10 | +0.217 | +0.076 to +0.442 |
| deep_svdd | 12.20 | 8.90 to 15.10 | +0.161 | +0.045 to +0.420 |
| great_expectations | 13.80 | 10.20 to 16.70 | +0.142 | +0.075 to +0.542 |

| Families | Median difference | 95 % interval | p (Holm) | Probability of superiority |
|---|---|---|---|---|
| classical - neural | -0.001 | -0.027 to +0.014 | 0.557 | 0.50 |
| classical - rule | +0.041 | +0.008 to +0.114 | 0.316 | 0.80 |
| neural - rule | +0.043 | -0.005 to +0.138 | 0.320 | 0.80 |

Not evaluated:

- nab/realAWSCloudwatch/ec2_cpu_utilization_53ea38 (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_cpu_utilization_5f5533 (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_cpu_utilization_77c1ca (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_cpu_utilization_825cc2 (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_cpu_utilization_c6585a (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_cpu_utilization_fe7f93 (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_disk_write_bytes_1ef3de (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_disk_write_bytes_c0d644 (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_network_in_257a54 (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/ec2_network_in_5abac7 (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/grok_asg_anomaly (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/iio_us-east-1_i-a2eb1cd9_NetworkIn (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAWSCloudwatch/rds_cpu_utilization_e47b3b (nab_aws): 0 anomalies in the test partition (at least 20)
- nab/realAdExchange/exchange-2_cpc_results (nab_adexchange): 0 anomalies in the test partition (at least 20)
- nab/realAdExchange/exchange-2_cpm_results (nab_adexchange): 0 anomalies in the test partition (at least 20)
- nab/realAdExchange/exchange-3_cpc_results (nab_adexchange): 0 anomalies in the test partition (at least 20)
- nab/realAdExchange/exchange-3_cpm_results (nab_adexchange): 0 anomalies in the test partition (at least 20)
- nab/realAdExchange/exchange-4_cpc_results (nab_adexchange): 0 anomalies in the test partition (at least 20)
- nab/realKnownCause/rogue_agent_key_hold (nab_rogue): 0 anomalies in the test partition (at least 20)
- nab/realKnownCause/rogue_agent_key_updown (nab_rogue): 0 anomalies in the test partition (at least 20)
- nab/realTraffic/TravelTime_387 (nab_traffic): 0 anomalies in the test partition (at least 20)
- nab/realTraffic/TravelTime_451 (nab_traffic): 0 anomalies in the test partition (at least 20)
- nab/realTraffic/occupancy_6005 (nab_traffic): 0 anomalies in the test partition (at least 20)
- nab/realTraffic/speed_7578 (nab_traffic): 13 anomalies in the test partition (at least 20)
- nab/realTweets/Twitter_volume_AAPL (nab_tweets): 0 anomalies in the test partition (at least 20)
- nab/realTweets/Twitter_volume_AMZN (nab_tweets): 0 anomalies in the test partition (at least 20)
- nab/realTweets/Twitter_volume_CRM (nab_tweets): 0 anomalies in the test partition (at least 20)
- nab/realTweets/Twitter_volume_FB (nab_tweets): 0 anomalies in the test partition (at least 20)
- nab/realTweets/Twitter_volume_GOOG (nab_tweets): 0 anomalies in the test partition (at least 20)
- nab/realTweets/Twitter_volume_PFE (nab_tweets): 0 anomalies in the test partition (at least 20)
- nab/realTweets/Twitter_volume_UPS (nab_tweets): 0 anomalies in the test partition (at least 20)
- skab/other/1 (skab): 0 normal rows in the test partition (at least 20)
- skab/other/11 (skab): 10 anomalies in the test partition (at least 20)
- skab/other/12 (skab): 0 anomalies in the test partition (at least 20)
- skab/other/13 (skab): 0 anomalies in the test partition (at least 20)
- skab/other/2 (skab): 0 anomalies in the test partition (at least 20)
- skab/other/3 (skab): 0 anomalies in the test partition (at least 20)
- skab/other/4 (skab): 0 normal rows in the test partition (at least 20)
- skab/other/5 (skab): 1 anomalies in the test partition (at least 20)
- skab/other/6 (skab): 1 anomalies in the test partition (at least 20)
- skab/other/7 (skab): 0 anomalies in the test partition (at least 20)
- skab/other/8 (skab): 1 anomalies in the test partition (at least 20)
- skab/other/9 (skab): 1 anomalies in the test partition (at least 20)
- skab/valve1/0 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/1 (skab): 1 anomalies in the test partition (at least 20)
- skab/valve1/10 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/11 (skab): 2 anomalies in the test partition (at least 20)
- skab/valve1/12 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/13 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/14 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/15 (skab): 1 anomalies in the test partition (at least 20)
- skab/valve1/2 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/3 (skab): 2 anomalies in the test partition (at least 20)
- skab/valve1/4 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/5 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/6 (skab): 1 anomalies in the test partition (at least 20)
- skab/valve1/8 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve1/9 (skab): 1 anomalies in the test partition (at least 20)
- skab/valve2/0 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve2/1 (skab): 0 anomalies in the test partition (at least 20)
- skab/valve2/2 (skab): 1 anomalies in the test partition (at least 20)
