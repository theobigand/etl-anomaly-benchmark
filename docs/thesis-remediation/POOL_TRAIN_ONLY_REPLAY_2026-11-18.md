# Train-only replay of the labelled pool (T062, T063) - protocol, 2026-11-18

Protocol id `pool-train-only-replay-v1`. Status: exploratory, prospective. It replaces no historical result and
does not show that the archived pool experiments were train-only.

## Question

The archived pool runs (`verification/evidence/labelled_pool/runs`) call `research.normalise.clean` on the whole table
before the split: column filtering, category encoding, de-duplication and label-conflict row removal can read
evaluation rows and labels. How much do the archived average precision (AP) values move when preparation sees
training rows only?

## Design (fixed before the full run)

- Population: the same 100 labelled problems (36 ADBench, 64 UCI), raw tables, no cleaning and no row removal.
  Label derivation for UCI problems (`uci_loader.derive_labels`, rare-class definition and anomaly-rate cap) is part of
  the problem definition, as in the archive, and is unchanged.
- Split: seeds 42, 1, 2, 3, 4; 70/15/15; identical feature rows form one group and stay in one partition (the
  frozen-partition preparation rejects duplicates across partitions); stratified on "group contains an anomaly".
  The partitions therefore differ from the archived ones, which were built on the cleaned table.
- Preparation: `research.pool_preprocessing.prepare_frozen` (fit on training rows only; labels never enter).
- Detectors: the 11 classical detectors of the archived sweep, same builders, fit caps and skip rules, contamination
  from the training prevalence. The 6 neural detectors are a separate, later step.
- Output: per problem and seed, the same metrics as the archive. Failures and skips are recorded, not dropped.
- Comparison (`research/pool_train_only_compare.py`): per detector, median over problems of the paired difference
  in seed-mean AP (replay minus archive), bootstrap 95% interval over problems (2,000 draws, seed 0), share of problems
  with |difference| > 0.05, and the detector ranking by median AP in both archives.

## Interpretation limits

- The difference measures the whole effect of moving to the train-only path together with the different partitions;
  it does not isolate leakage alone.
- The 19 sources shared by ADBench and UCI make problems non-independent; the interval is over problems and is not
  source-clustered. Seeds are not independent either.
- A small difference does not prove the archived pipeline was leakage-free. It bounds how much the reported AP depends
  on the pre-split decisions, on these problems.
- Before the full run, one ADBench problem (`cardio`) was run to test the runner; its output is not used to set any
  threshold or decision.

## Result: classical detectors (11 detectors, 100 problems, 5 seeds, 0 failed problems)

Archive: `verification/evidence/pool_train_only_replay/` (`runs/`, `comparison_classical.{json,md}`,
`provenance_classical.json`). The skip pattern is unchanged (KNN and LOF 90 problems, One-Class SVM 84).

- The paired median difference in AP is zero for every detector because 10-44% of the problems are unchanged: with no
  duplicate rows and numeric features the grouped split reduces to the archived split and the preparation to the
  archived one. The mean difference is small and negative: from -0.001 (Isolation Forest, IQR) to -0.017 (Z-score, LOF).
- Between 4% (KNN) and 11% (Isolation Forest) of the problems change AP by more than 0.05.
- The largest change is `adbench:http` for the Z-score (-0.77). The raw table has 567,498 rows against 221,898 after
  the archived de-duplication, so the replay changes the evaluated population (duplicates are kept), not only the
  fitting information. Separating the two effects would need a de-duplicate-then-split variant; it was not run.
- Median AP over problems, archive then replay: ECOD 0.240 / 0.231, HBOS 0.237 / 0.235, COPOD 0.216 / 0.199,
  Isolation Forest 0.215 / 0.197, Z-score 0.203 / 0.176. The order of the leading detectors changes (ECOD first in the
  archive, HBOS first in the replay) by margins that are small relative to the spread over problems, and the
  conclusion that no detector is clearly ahead is unchanged on these problems.

Conclusion for T062/T063: the pre-split decisions of the historical path move AP by little for most problems and by a
lot for a few, mainly through de-duplication. This is exploratory evidence on the classical detectors only. It does not
show that the archived experiments were train-only; the neural detectors are replayed separately.
