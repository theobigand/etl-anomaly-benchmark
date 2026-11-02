# Thesis remediation backlog — Volume 4: Statistical Validity

**Scope:** T126–T158. **Status:** open until individually verified. P0 = required; P1 = important.

Statistical inference must respect repeated seeds, paired datasets, and shared source lineage. Equivalence requires a justified margin and a suitable inferential procedure.

## 10. Paired inference and clustered uncertainty (P0; Thesis 02)

- [ ] T126 Recompute comparisons using matched datasets and partitions.
- [ ] T127 Compare paired AP differences, not just marginal confidence intervals.
- [ ] T128 Report effect sizes for primary comparisons.
- [ ] T129 Compute uncertainty intervals for paired differences.
- [ ] T130 Do not interpret a non-significant result as equivalence.
- [ ] T131 Define a region of practical equivalence if equivalence is claimed.
- [ ] T132 Verify whether a plus/minus 0.02 AP margin is justified and prespecified.
- [ ] T133 Optionally estimate posterior superiority and practical-equivalence probabilities.
- [ ] T134 Do not attribute Bayesian probabilities to Wilcoxon signed-rank tests.
- [ ] T135 Check baycomp assumptions against source dependence and repeated seeds.
- [ ] T136 Compare ECOD vs Isolation Forest, DIF vs ECOD, and cross-family representatives.
- [ ] T137 Define primary comparisons before inspecting new outcomes.
- [ ] T138 Apply appropriate multiple-comparison correction.
- [ ] T139 Add source_id to result records.
- [ ] T140 Group derived problems by original data source.
- [ ] T141 Bootstrap source clusters instead of individual problem rows.
- [ ] T142 Keep observations from each source together when resampling.
- [ ] T143 Aggregate five seeds correctly within each problem.
- [ ] T144 Do not treat repeated seeds as independent datasets.
- [ ] T145 Recompute 95% cluster-aware uncertainty intervals.
- [ ] T146 Compare cluster-aware and original intervals.
- [ ] T147 Count actual unique sources rather than assuming 81 clusters.
- [ ] T148 Run sensitivity analyses excluding overlapping ADBench/UCI sources.
- [ ] T149 Revise Table III and statistical conclusions from corrected analyses.

## 11. Operational and fault-specific metrics (P1; Thesis 02)

- [ ] T150 Add precision, recall, and F1 where operationally relevant.
- [ ] T151 Add false-positive rate.
- [ ] T152 Add false alerts per 1,000 rows.
- [ ] T153 Add precision at a fixed alert budget.
- [ ] T154 Measure recall across several alert budgets.
- [ ] T155 Compare methods under equivalent operating constraints when possible.
- [ ] T156 Define duplicate detection at row, pair, or group level.
- [ ] T157 Measure incorrect row removals during deduplication.
- [ ] T158 Keep row-level metrics distinct from batch/window-level drift metrics.
