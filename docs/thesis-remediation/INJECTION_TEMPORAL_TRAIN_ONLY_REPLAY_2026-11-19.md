# Train-only replay of the injection and chronological studies (T062, T063) - protocol, 2026-11-19

Protocol ids `typed-train-only-v1` and `chrono-train-only-v1`. Status: exploratory, prospective. They replace no
historical result and restamp nothing; archived values are only compared.

## Question

T062 asks whether all preprocessing is fitted on training data only; T063 whether test statistics ever influence
preprocessing or fitting. The labelled pool was replayed on 2026-11-18 ([pool replay](POOL_TRAIN_ONLY_REPLAY_2026-11-18.md)).
Two families of studies remained: the typed-injection study and the chronological studies. For each, which decisions
read rows of the evaluation partitions, and how much do the reported numbers move when those decisions read training
rows only?

## Audit of the decisions (code read, before any run)

Typed injection (`research/typed_run.py`, `research/injection.py`, `research/typed_benchmark.py`):

| Decision | Reads | Replay treatment |
| --- | --- | --- |
| Detector fitting, contamination, capping | training partition only | unchanged |
| Mean, standard deviation, most-correlated pair, 3%/97% quantiles and column signs that set the size of the injected faults | the whole carrier, including rows that end in the validation and test partitions | recomputed from the unmodified rows of the training partition |
| Carrier definition: continuous columns (at least 10 distinct values), complete rows, exact de-duplication, 20,000-row seeded subsample, normal class only for labelled tables | the whole table | unchanged: it defines the pre-registered population, not a fitted statistic (the group split needs de-duplicated rows) |

Chronological studies (`research/pool_chrono.py`, `research/temporal_decision.py`):

| Decision | Reads | Replay treatment |
| --- | --- | --- |
| Time order, 70/15/15 partitions, detector fitting, thresholds P0/P1/P2 | past rows only (P0 training scores, P1 validation, P2 a trailing window) | unchanged |
| Constant-column removal, the 25-level category cap, the one-hot vocabulary (`pool_chrono.to_features`, `temporal_decision.bank_marketing`) | the whole table | fitted on the oldest 70% of the rows, applied unchanged to later rows; an unseen level is an all-zero indicator |
| Exact de-duplication of Credit Card (`transform.clean`) | the whole table, so a test row could be dropped because of an earlier or later twin | no de-duplication: raw rows are kept |
| Label derivation for the UCI problems, readable-time filter | per row / problem definition | unchanged (problem definition, as in the pool replay) |

The stratified control inside the chronological study is a deliberately non-chronological comparison and is not part of
the replay question; it is recomputed on the same features and reported with the rest.

## Design (fixed before the full runs)

- Injection: for each carrier and seed the injection is laid out once (group identities, anomaly types, hence the
  partitions), the statistics are recomputed from the unmodified training rows of that layout, and the faults are injected
  again with them (`injection.inject(..., reference=...)`). Group identities, types and partitions do not depend on those
  statistics; the run asserts that they are identical to the archived layout. The 42 UCI carriers, 5 seeds (42, 1, 2, 3, 4),
  13 methods of the classical registry sweep and the same metrics as the archive. The neural typed sweep is not replayed:
  it draws on the same injection code and a different archive layout (`deep_typed`), and is left as a limitation.
- Chronology: the five datasets of the archived study (Credit Card, Bank Marketing, Occupancy Detection, Online Shoppers,
  Room Occupancy), all 17 detectors, the archived eligibility rule (at least 20 test anomalies) and caps.
- Comparison: paired replay minus archive. Injection: per method and type, median over carriers of the difference in mean
  recall with a bootstrap interval over carriers (2,000 draws, seed 0), and the share of carriers moving by more than 0.1.
  Chronology: per dataset and detector, the difference in chronological and stratified AP and ROC-AUC, rank agreement of
  the detectors, and whether the partitions are equal.
- Before the full runs, one carrier (Predict Students' Dropout, 697) and two chronological datasets (three detectors) were
  run to test the runners; their output was not used to set any decision. The archived injection result of the same carrier
  was reproduced exactly (maximum absolute difference 0.0) by the current code, so a replay difference cannot come from
  the environment.

## Interpretation limits

- The difference is the whole effect of moving the listed decisions to training rows; it does not show the archived
  experiments were train-only.
- The carriers are not independent (19 UCI sources are shared with ADBench, and the UCI tables share labelling rules); the
  intervals are over carriers and are not source-clustered. Seeds are not independent either.
- A zero difference where the replay changes nothing (for example datasets whose schema is the same when fitted on
  training rows) is a verification that the decision did not matter there, not evidence of an effect of zero in general.

## Result: typed injection (42 carriers, 5 seeds, 13 methods, no failed carrier)

Archive: `verification/evidence/typed_train_only/` (`runs/`, `comparison_classical.json`, `summary/`, `provenance.json`),
paired with `verification/evidence/typed_injection/runs`.

- Replacing the statistics of the whole carrier by those of the training partition changes the mean recall of a method on
  a type by at most 0.034 (PCA, multivariate outliers). Only 2 of the 78 method-by-type cells move by more than 0.01 in
  the mean (PCA multivariate -0.034, IQR multivariate +0.012); nine cells are exactly unchanged. The largest median
  difference over carriers is 0.003, and every bootstrap interval of a median difference lies within [-0.04, +0.04].
- The share of carriers whose recall changes by more than 0.1 is at most 17% in any cell (PCA on drift) and 14% for PCA on
  multivariate outliers; it is 0 for missing values and duplicates, the types a rule or a count decides.
- Pre-registered hypotheses (`verification/typed_injection.md`, evaluated with the archived `typed_summary.py`): H1, H2, H3
  and H5 keep their verdicts (H1 to H3 not supported, H5 supported, rho -0.962 against -0.961). **H4 changes verdict**:
  supported in the archive (hardest-type rank stability 0.6536 for multivariate outliers against 0.6598 for the weakest
  structural type, duplicates), not supported in the replay (0.6576 against 0.6573). The margin was 0.006 and is -0.0003;
  the overall stability is 0.802 against 0.802. The verdict is a strict inequality between two values that differ in the
  third decimal, so it is not robust to this preprocessing choice, and the manuscript says so; the archived verdict is
  unchanged.
- The archived study is therefore not an artefact of reading the carrier statistics before the split on these tables, to
  within the stated tolerance, apart from the knife-edge H4. This does not cover the neural typed sweep, which was not
  replayed.

## Result: typed injection on the 16 ADBench carriers (added after the UCI run, same protocol)

Archive: `verification/evidence/typed_train_only_adbench/`, paired with `pool_extension/typed/reference_classical`. The
UCI replay above covered the 42 UCI carriers of the archived typed study; the 16 ADBench carriers of the pool extension
were added so that all 58 eligible tables are replayed (classical sweep).

- Largest mean change in a method-by-type cell: 0.022 (PCA, multivariate outliers); 5 of 78 cells move by more than 0.01
  (four PCA cells and IQR on multivariate outliers); largest median change 0.005; every bootstrap bound
  within [-0.04, +0.04]; at most 25% of carriers move by more than 0.1 in a cell (PCA, multivariate outliers).
- Same picture as on the UCI tables: whole-carrier statistics are not what drives the typed results, PCA being the
  detector most sensitive to them. The pre-registered hypotheses were stated on the 42 UCI tables only and are not
  re-evaluated here.

## Result: chronological studies (5 datasets, all detectors of the archived study)

Archive: `verification/evidence/chrono_train_only/runs/` (`comparison.json`, `provenance.json`), paired with
`pool_extension/chrono`.

- Room Occupancy stays excluded (0 test anomalies), as in the archive. For Bank Marketing, Occupancy Detection and Online
  Shoppers the partitions are identical to the archive's. For the two pool datasets the feature matrix is also identical
  (the constant-column and category decisions fitted on the oldest 70% give the same schema): rule and classical detectors
  are unchanged to the last digit and the neural ones move by at most -0.008 (Occupancy) and -0.013 (Online Shoppers) in
  chronological AP. Bank Marketing moves by up to 0.008 for the non-neural detectors and by up to -0.063 for the neural ones
  (VAE 0.514 to 0.450), because the one-hot vocabulary now comes from the oldest rows. Rank correlation of the detectors by
  chronological AP between archive and replay: 0.97 (Bank), 0.99 (Occupancy), 0.99 (Online Shoppers).
- Credit Card, where the replay keeps duplicate rows instead of de-duplicating the whole file, has different partitions
  (test 42,722 rows against 42,559, 52 frauds in both): chronological AP changes by -0.003 in the median and by up to
  -0.112 (autoencoder, 0.163 to 0.052; Deep SVDD 0.359 to 0.251), rank correlation 0.89, over the 14 detectors present in both
  archives. The stratified control moves by up to 0.21 (PCA), which is the random split on a different population, not a
  property of the chronological arm. The effect is the whole change of preparation (population and scaling), not
  de-duplication alone.
- The dependence of the neural detectors on the preprocessing is the largest visible effect; the conclusions of the
  chronological study (large train-to-test prevalence shift, thresholds fixed on the past failing in both directions) rest on
  the decision-policy results, which this replay does not change in kind.

## Conclusion for T062 and T063

Every study of the thesis that reads an external table now has a train-only counterpart: the labelled pool (100
problems, 17 detectors), the typed injection (58 tables, classical sweep) and the chronological studies (5 datasets, 17
detectors). Differences are small for most detectors and datasets, and larger for specific cases that are named above
(`http` through de-duplication, PCA under injection, neural detectors on Credit Card and Bank Marketing). They bound the
dependence of the archived numbers on pre-split decisions; they do not show the archived runs were train-only, and no
archived value was changed.

Remaining, documented limits: the neural typed sweep and the synthetic generators were not replayed (the generated data have no
external table to prepare); the carrier definition of the typed study (continuous columns, complete rows, de-duplication, row
cap) is a population definition kept pre-split on purpose; the intervals are over tables, not source-clustered; the hypothesis H4
of the typed study is knife-edge (above).

## Software evidence

New modules `research/typed_train_only.py` and `research/chrono_train_only.py` are classified L3 in
`verification/mutation_risk_policy.json` by the implementer (open to owner reclassification). Local focused measurements
(not the controller campaign, not attested; record in `evidence/focused-train-only-replays-2026-11-19/measurement.json`):
643 of 654 mutants killed for the typed replay (98.3%) and 535 of 556 for the chronological replay (96.2%), against a threshold
of 95%. No survivor is declared equivalent. `research/injection.py` (L4) gained the optional `reference` argument; its default
behaviour is unchanged (existing golden tests pass, plus three tests for the argument) and its authoritative measurement is the
next controller campaign. Release certification of the final commit is separate.
