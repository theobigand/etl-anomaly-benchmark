# Thesis remediation backlog — Volume 6: Fair Baselines and Feature Representations

**Scope:** T174–T198. **Priority:** P1. **Milestone:** Thesis 03.

The comparison must distinguish detector capacity from information available to each method. Domain-informed rules are not an information-matched baseline against unsupervised models.

## 13. Fair rule-versus-model factorial comparison (P1; Thesis 03)

- [ ] T174 Retain GE-Generic with the current limited rule suite.
- [ ] T175 Add GE-Domain-Oracle with explicit domain constraints.
- [ ] T176 Retain ML-Numeric-Only with the original preprocessing.
- [ ] T177 Add ML-Encoded with categorical features and format indicators.
- [ ] T178 Use identical datasets, partitions, and injections across the four conditions.
- [ ] T179 Compare all six fault types separately.
- [ ] T180 Measure false positives and costs for all four conditions.
- [ ] T181 Document the domain knowledge available to each condition.
- [ ] T182 Do not claim equal information when domain-informed rules have additional knowledge.
- [ ] T183 Do not assume perfect invalid-format detection before measuring it.

## 13b. Domain-informed Great Expectations suite (P1; Thesis 03)

- [ ] T184 Add format validation for emails and identifiers.
- [ ] T185 Add allowed-value domains.
- [ ] T186 Add fixed business-range constraints.
- [ ] T187 Add uniqueness constraints.
- [ ] T188 Add cross-column consistency constraints.
- [ ] T189 Add schema and type constraints.
- [ ] T190 Add key constraints where data permits.
- [ ] T191 Document the human cost of defining and maintaining rules.

## 13c. Richer ML representations (P1; Thesis 03)

- [ ] T192 Test categorical encodings appropriate for the models.
- [ ] T193 Handle unseen test-time categories.
- [ ] T194 Test missingness indicators.
- [ ] T195 Test format-validity indicators.
- [ ] T196 Preserve textual error signals rather than discarding them.
- [ ] T197 Measure dimensionality effects after encoding.
- [ ] T198 Isolate preprocessing gains from detector gains.
