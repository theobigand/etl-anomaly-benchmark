# Source-clustered re-analysis of the labelled pool — 2026-11-08

Status: post-hoc and exploratory. It re-analyses archived per-seed average precision; the
six comparisons were chosen from those the manuscript already reports, after the results
were known. No hypothesis, protocol or archived number is changed.

## Method

- `source_id`: an ADBench problem whose file derives from a UCI table takes that UCI source
  (35 of 36; `fraud` has none); other problems are their own source. The 100 problems fall into
  **80 unique sources**, and 17 ADBench problems share a source with a labelled UCI problem.
- The five seeds are averaged within a problem (seeds are not independent datasets).
- Paired differences are taken over the problems where both detectors ran.
- Percentile intervals (95%, 10,000 draws, seed 2026) from a problem-level bootstrap and from a
  bootstrap that resamples whole sources with their problems; a source-level bootstrap excluding
  the overlapping ADBench problems; Holm adjustment of the six source-level two-sided bootstrap p-values.

## Result

| Comparison | Problems | Mean AP difference, source bootstrap | Holm p |
| --- | --- | --- | --- |
| ECOD - Isolation Forest | 100 | -0.009 [-0.036, +0.020] | 1.000 |
| COPOD - Isolation Forest | 100 | -0.004 [-0.028, +0.018] | 1.000 |
| One-Class SVM - Isolation Forest | 84 | -0.015 [-0.033, +0.004] | 0.655 |
| DIF - ECOD | 100 | -0.021 [-0.062, +0.017] | 1.000 |
| Z-score - Isolation Forest | 100 | -0.018 [-0.050, +0.020] | 1.000 |
| Great Expectations - Isolation Forest | 100 | -0.162 [-0.208, -0.116] | 0.000 |

Source resampling widens the problem-level intervals by at most 22% and changes no sign. Excluding the
overlapping ADBench problems (17) leaves the qualitative conclusions unchanged: the ECOD and COPOD point
differences change sign but stay within 0.006 of zero, and every interval still contains zero except Great
Expectations (the full table is in the JSON).
Only the Great Expectations bounds are clearly below Isolation Forest. For every other comparison the
interval contains zero: the data neither separate the detectors nor show them equivalent. No equivalence
margin was prespecified, and none is claimed (T130-T132).

## Limits

The detectors were run with default settings on one split per seed. The percentile bootstrap over 80
sources has limited accuracy for small effects. The analysis does not model the correlation between
detectors within a problem beyond pairing. It re-uses archived results whose preprocessing is historical
(see the partition recovery note) and does not validate them.
