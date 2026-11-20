# Coverage extension: what the new evidence changes

Evidence: `verification/evidence/coverage/` (matrix, inventory) and
`verification/evidence/pool_extension_v2/` (ETL repair, mixed-schema typed injection, chronological
study with controlled injection). The earlier archives are untouched. Protocols were written before
the runs: `verification/typed_mixed.md`, `verification/chrono_injected.md`.

## Coverage

| Quantity | Before | After |
|---|---|---|
| Catalog entries / active | 152 / 152 | 152 / 151 |
| Independent sources | 128 | 128 (127 with a detector-quality measurement) |
| Tables with a detector-quality measurement | 120 | 151 |
| Tables measured only by the pipeline timing run | 32 | 1 (retired) |
| Pipeline runs that succeed | 290 of 304 | 304 of 304 |
| Real time variable, any evaluation | 4 labelled | 4 labelled and 7 unlabelled with injected faults |

Decisions: 115 retained, 30 adapted (measured through the mixed-schema protocol), 6 repaired (ETL
readers), 1 retired (Student Academics Performance: 131 rows after cleaning, no labels). No dataset
was replaced and none was added: after repair and adaptation, one table lacked a valid
detector-quality experiment, and no candidate replacement was verified for licence, checksum and
independence in this round (SKAB, GPL-3.0, and NAB are the shortlisted time-series candidates, not
integrated).

## Hypotheses of the new protocols

- M1 holds: the per-type detector ranking on numeric-only mixed tables agrees with the numeric
  protocol (mean rank correlation 0.84).
- M2 holds in direction, with a caveat: rule detectors find categorical faults less often than
  distance and density detectors, but they read the encoded columns, so they are not blind to
  categories as the protocol assumed.
- M3 holds: no detector differs between the two size tiers after Holm correction.
- C1 holds weakly: the median detector false-positive rate is higher after fitting on the past
  (classical +0.015, neural +0.059); distance-based kNN and LOF and the neural LUNAR and Deep SVDD
  have intervals that exclude zero.
- C2 holds: recall changes less than the false-positive rate.
- C3 holds for the classical detectors (rank correlation 0.97) and less for the neural ones (0.88).

## Earlier conclusions

- The 100 labelled problems, their rankings, the H4 ranking-stability sensitivity and the
  archive-versus-replay differences are unchanged: no labelled problem was added.
- P5 (chronological AP lower for two thirds of the pairs) is unchanged on its five labelled tables;
  the new study measures a different quantity, the false-positive cost of temporal change, on
  unlabelled series.
- The numeric typed protocol (58 tables) is unchanged and is never pooled with the mixed protocol.

## Limits

Injected faults are artificial; labels are minority-class proxies. The encoder (one-hot up to
twenty levels, frequency beyond) is one choice. Eight tables have fewer than 200 rows and carry no
typed experiment. Seven time series are a small corpus, and the two new studies are exploratory.
The seven new research modules are classified in the mutation policy (four L4, two L3 and the
coverage generator at L3) and were measured locally: 98.6% to 100% on the L4 modules and 95.7% to
100% on the L3 ones (`evidence/focused-coverage-extensions-2026-11-20/measurement.json`). This is a
local development measurement on macOS, not the controller campaign and not attested; the
authoritative figures are those of the next Linux campaign.
