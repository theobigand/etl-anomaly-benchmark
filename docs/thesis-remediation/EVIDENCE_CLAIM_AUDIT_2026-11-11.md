# Evidence-to-claim audit and T172 readiness - 2026-11-11

Scope: the claims of `paper/main.tex` and `slides/thesis_progress.html` that depend on the labelled-pool
studies, the deployment-threshold studies (T163-T171), neural reproducibility and the verification layer.
Status classes: ESTABLISHED (recomputed or independently checked from archived evidence), REPRODUCED
(under a stated environment), EXPLORATORY, DESCRIPTIVE (historical, with its limitation), UNSUPPORTED
(none found in this pass; corrected where found).

## Claim map

| Claim (location) | Evidence | Status | Limitation |
| --- | --- | --- | --- |
| 100 labelled problems, 5 seeds, 17 detectors; AP medians and ranks (paper Sec. labelled pool; slides 19-20) | archived pool runs; partition replay (`PARTITION_RECOVERY_2026-11-08.md`); source-clustered re-analysis | DESCRIPTIVE | historical `clean()` reads the whole population before the split, so train-only validity is not established (T062, T063 open); the 100 problems come from 80 sources |
| Memberships recomputed and replay-validated (T088, T089) | recovery replay reproduces all archived Z-score per-seed metrics | ESTABLISHED for the Z-score replay | the other detectors were not replayed |
| Source-clustered paired comparisons (T139-T148) | `source_clustered.py`, `SOURCE_CLUSTERED_ANALYSIS_2026-11-08.md` | EXPLORATORY | post hoc comparison choice |
| Label-free threshold lowers F1 (P1) | archived fixed-0.02 run | DESCRIPTIVE | pool dependence as above |
| Alert budgets 0.5-10%, nominal vs realized rate (T163, T164; paper Discussion; slide 25A) | `verification/evidence/alert_budgets/{classical,neural}`; 0 failed runs; invariants on 15,000 neural cells; 2% cell reproduces the archive exactly for classical, autoencoder, DIF, VAE | EXPLORATORY; REPRODUCED for the cited archive agreement | one machine; AE1SVM and LUNAR thread-dependent; no ranking claimed |
| Rules vs learned at comparable volume (T167) | `matched_alert.json` (source-clustered, Holm) | EXPLORATORY | matching uses realized alert rates; IQR matchable on 14-35 problems only |
| Fixed thresholds under prevalence shift (T169) | `prevalence_shift.json`, `contrasts` (80 sources) | EXPLORATORY | label-shift assumption; some problems have 1 held-out positive |
| Fixed thresholds under score shift (T170) | `score_shift/summary.json`, `contrasts` (78 sources) | EXPLORATORY | 5 classical detectors, synthetic shifts |
| Obsolescence criteria (T171) | same | EXPLORATORY; the 30-alert stratification is POST HOC | conventions not validated on real drift |
| Neural thread sensitivity of AE1SVM and LUNAR; autoencoder invariant; Deep SVDD ~1e-3 (paper Threats; `NEURAL_REPRODUCIBILITY_2026-11-11.md`) | `evidence/neural-repro-2026-11-11/` | REPRODUCED under the stated environment | 3 problems, 2 seeds, one CPU; source of Deep SVDD noise not isolated |
| Core mutation 97.61% (4,980/5,102), historical local run (paper Verification; slide 34; slide 1 corrected) | recorded historical run at d4304c5 | DESCRIPTIVE, not attested | not release evidence |
| First native campaign 19,248/29,811, L4 65.5%, gate FAIL | recorded campaign | ESTABLISHED as a recorded failing diagnostic | none claimed as compliance |
| LSTM diagnostic 368/377 raw 97.61%, 368/373 adjusted 98.66% (paper, slide 40) | hosted run 42985826795, validated with `accepted_equivalents` against the runtime packages | ESTABLISHED for that shard | one module; sole-author owner review; no certification |

## Corrections made in this pass

- Slide 1 said 97.45% killed; the paper and slide 34 give 97.61% (4,980 of 5,102): corrected and labelled
  as a historical local run that is not release evidence.
- The roadmap slide counted 24 tasks in four issues; replaced by the verified total (91 of 415 checked) and
  the open items.
- The inventory slide said 92 source modules; the policy lists 100.
- Added the exploratory deployment-threshold study to the paper (Discussion) and slide 25A, and the neural
  numerical caveat to the threats to validity; added the LSTM diagnostic to the verification sections.
- Rendering: all 42 slides were rendered and inspected; one overflow in the new slide (second statistic below
  the slide) was repaired and the slide rendered again. The inspection used page images of about 45-80 dpi:
  clipping and overlap were checked, small-print numbers were verified against the sources rather than the
  images.

## T172 readiness: NOT READY (task stays open)

T172 asks for oracle and label-free results in the main tables. The evidence is missing in these places:

1. Protocol consistency: the oracle protocol (training-prevalence contamination) and the label-free one are
   both archived, but the label-free alert-budget grid was produced by a new run with a constant build
   contamination, not by the original archived protocol; a main table would mix protocols unless labelled.
2. Preprocessing validity: the historical preparation reads the whole population (T062, T063 open), so every
   pool number is descriptive; promoting them as confirmatory would contradict the manuscript's own limitation.
3. Reproducibility: AE1SVM and LUNAR results depend on the thread configuration; confirmatory neural numbers
   need the proposed single-thread configuration and a rerun, which has not been done.
4. Source-clustered uncertainty: available for T167, T169 and T170, not for every proposed main-table cell
   (per-detector alert-budget medians have no intervals).
5. Stability coverage: score shift covers five classical detectors; neural detectors have no shift study.
6. Single machine and environment: no second environment has reproduced the new runs.
7. Post hoc elements: T171 stratification and the T167 matching tolerance are conventions fixed in code but
   not pre-registered.

A negative decision is the outcome: promotion requires (a) the train-only replay or an explicit
disclosure that tables are descriptive, (b) a single-thread neural rerun, (c) intervals on the table cells,
and (d) a pre-registered protocol note for the matched and monitoring conventions.
