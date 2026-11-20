# Statistical validity of the labelled-pool rankings: protocol (issue #83)

Written and archived before any result of this study exists. The archived five-seed runs of the
labelled pool and the archived source-clustered analysis are not changed; this study adds new runs
and new analyses next to them.

## Question

Which detector leads on the labelled pool depends on how the labels were made (rarest class,
downsampled to 10 %), on the twin sources (19 sources appear twice), on five seeds and on the lack
of a formal test. How much of the ranking survives a change of rule, source-level inference, ten
seeds and a corrected paired test?

## Part A: ten seeds

The 100 labelled problems are rerun for the 17 detectors with seeds 5, 6, 7, 8 and 9
(`labelled_benchmark.py --seeds`, classical and neural sets, same fit-size cap and skips). With the
archived seeds 42, 1, 2, 3, 4 this gives ten seeds per problem and detector. The seed fixes the
stratified 70/15/15 partition and the initialisation of the neural detectors. No procedure is
exempt from repetition: even the deterministic detectors see a different partition per seed.

## Part B: label rules

On the 64 UCI problems, six rules (the first is archived, the others are new runs with seeds 42, 1, 2):

- R0 (baseline): rarest class, downsampled to 10 % when more frequent;
- R1: rarest class, downsampled to 2 %;
- R2: rarest class, downsampled to 5 %;
- R3: rarest class, natural rate, no downsampling;
- R4: second rarest class (needs three classes), rarest class removed, downsampled to 10 %;
- R5: every class but the most frequent (three classes), downsampled to 10 %.

All downsampling uses seed 0 as in the baseline. A problem without a valid anomaly set under a rule
(fewer than 20 anomalies, too few classes) is listed as not applicable. The rule changes what
"anomaly" means; it does not make a minority class a data-quality fault, and none of these labels
is read as one.

## Part C: inference

Unit of analysis: the source group (`source_clustered.source_id`). The twin problems of one source
are averaged first, after averaging the seeds. Every interval and test resamples or ranks source
groups, never problems or seeds. Dataset-level results (100 problems) are reported next to them,
and so is the effective number of independent sources.

- Metric: average precision (PR-AUC) on the test partition, mean over seeds. Detectors that were
  skipped (fit size) are handled by using the sources where both detectors of a pair ran.
- Omnibus: Friedman test over the sources where all detectors that ran on at least 90 % of the
  sources are present.
- Pairwise: for every pair of detectors, a two-sided Wilcoxon signed-rank test over sources, Holm
  correction over all pairs, with the effect size alongside: median paired difference with a 95 %
  bootstrap interval over sources, and the probability of superiority.
- Families: classical against neural, on the per-source mean of each family, with the same test.
- Rank statistic: mean rank per detector over sources, 95 % bootstrap interval over sources.

## Hypotheses

- V1 (rule robustness): the rank correlation (Kendall tau) between the mean-rank vector of R0 and
  that of each alternative rule is at least 0.7.
- V2 (leader): the detector with the best mean rank under R0 stays in the best three under every
  rule.
- V3 (no clear leader, restated): after Holm correction the best detector of R0 is not
  significantly better than the second best, with ten seeds and source-level inference. Failure to
  reject is not read as equivalence: the effect size and its interval are reported.
- V4 (seeds): the mean-rank vector from five seeds and from ten seeds agree (Kendall tau at least
  0.9).
- V5 (twin sources): collapsing twin sources changes no pairwise conclusion of the earlier
  source-clustered analysis.

Results that contradict a hypothesis are reported as they are. The paper's claims about winners
are restated from these results.
