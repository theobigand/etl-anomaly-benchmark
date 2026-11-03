# Thesis remediation backlog — Volume 8: Hybrid Pipelines and Detector Ablations

**Scope:** T234–T264. **Priority:** P1. **Milestone:** Thesis 04.

Do not claim that hybrid pipelines are superior before comparative measurements. Document all modifications to upstream detector behavior and keep the original baseline intact.

## 15. Hybrid rules-plus-model ETL pipelines (P1; Thesis 04)

- [ ] T234 Build a format-rule → cleaning → statistical-detector pipeline.
- [ ] T235 Build a domain-rule → ML-detector pipeline.
- [ ] T236 Test combinations with ECOD, HBOS, or Isolation Forest.
- [ ] T237 Optionally test DIF or an autoencoder in a hybrid.
- [ ] T238 Compare sequential and parallel hybrid architectures.
- [ ] T239 Test alternative alert-combination policies.
- [ ] T240 Measure incremental recall from the second stage.
- [ ] T241 Measure additional false positives.
- [ ] T242 Measure total operational cost.
- [ ] T243 Compare each hybrid against all its individual components.
- [ ] T244 Check gains across multiple datasets.
- [ ] T245 Report quality-versus-cost trade-offs.
- [ ] T246 Revise hybrid architecture recommendations only after testing.

## 16. PyOD inductive ablations and equal-budget tuning (P1; Thesis 04)

- [ ] T247 Compare original and adapted ECOD.
- [ ] T248 Compare original and adapted COPOD.
- [ ] T249 Compare original and adapted DIF.
- [ ] T250 Compare original and adapted VAE.
- [ ] T251 Test batch-composition invariance by adding/removing other test rows.
- [ ] T252 Measure score and ranking differences.
- [ ] T253 Measure detection-performance differences.
- [ ] T254 Measure time and memory differences.
- [x] T255 Document whether adaptations fix problematic behavior or change the reference algorithm.
- [ ] T256 Add an ablation table to the appendix.
- [ ] T257 Retain out-of-the-box experiments as the main baseline.
- [ ] T258 Run a representative equal-budget tuning study.
- [ ] T259 Select hyperparameters on validation data only.
- [ ] T260 Never select configurations using test labels.
- [ ] T261 Set comparable tuning budgets across families.
- [ ] T262 Measure tuning gains and their computational cost.
- [ ] T263 Reassess neural-model conclusions after tuning.
- [ ] T264 Mark non-preregistered follow-up experiments as exploratory.

Evidence for T255: [pinned-source adaptation classification](INDUCTIVE_DETECTORS_2026-11-03.md).
This documentation does not complete the performance, ranking or cost ablations.
