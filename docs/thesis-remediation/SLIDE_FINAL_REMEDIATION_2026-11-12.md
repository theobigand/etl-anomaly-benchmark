# Final remediation of the deck, 2026-11-12

Scope: the 51-slide deck in `slides/`, branch `feat/risk-tiered-mutation-policy`, checkpoint `917ada6`. No scientific
experiment, mutation campaign, train-only replay or neural rerun was run. The one computation is the regeneration of
precision-recall curves with the existing script and seed (below), which reproduces a figure that was already in the
paper. PR #117 stays a draft and nothing here changes release certification.

## What was reproduced first

Rendered inspection at 150 dpi of the checkpoint deck found, besides the known items, defects that the layout checker
had reported as clean: overlapping boxes and a box border through text (slide 38), a slide title that contradicted the
paper (slide 23), a footnote repeating that contradiction (slide 15), labels struck through by lines (9, 19), mid-tone
matrix cells with 2.9 to 4.2:1 text, and sub-14 px words. Details: `SLIDE_VISUAL_SEMANTIC_AUDIT_2026-11-12.md`, third pass.

## Slides 22 and 23

Both are native SVG now. Slide 22 draws `slides/art/data/pr_curves.json`, exported by
`slides/art/tooling/export_pr_curves.py` from `experiments/run_curves.py::scores_for` (same datasets, split, detectors,
seed 42). Slide 23 draws `verification/evidence/severity.csv`, the committed evidence of the severity run.
Choice of colour: the highest-AP method in each panel is dark and solid, the lowest-AP method is blue and dashed, the
others are grey. The choice is by rule, so no method is picked to suit the argument; the key under each panel title
names them. Nothing is redrawn by hand.

Finding: the regenerated AP matches the legend of the archived paper figure for 39 of 41 curves. PCA differs on Water
Quality (0.54 against 0.57) and on the synthetic set (0.48 against 0.56). The archived figure used ten colours for
eleven curves, so PCA shared a colour with Z-score. The slides use the regenerated values and say that AP comes from
this one run. The paper figure and its text were not edited; the PCA difference is for the author to decide.

Finding (paper, not changed): Section "Precision-recall curves and the operating point" says that on Credit Card
Fraud "Great Expectations and Isolation Forest dominate", while the AP ranking in the same figure has COPOD 0.28,
HBOS 0.26 and Great Expectations 0.23 above Isolation Forest 0.17. Slide 22 states the AP ranking instead of "dominate".

## Slide 20 and the matrices

Cell text is now black or white by computed WCAG contrast (minimum 4.68:1 over the whole cividis scale); a test fails if
a fill falls under 4.5:1. Slide 15 and 40 ordinals went from 50% to 72% opacity.

## Slides 11, 45, 50 (and 2, 42)

The empty areas were consequences of fixed positions, not pauses: the text sat at the top of its boxes and left a
band below. Slide 11 became a ledger (adaptation, then what changes) with the evidence boundary as its last row;
slide 45 and 50 were set at larger type with the two columns stacked by `flow()`; slide 2 sits lower; slide 42 was
rebuilt as two stacks because its table and note collided under wide fonts. Slides 16, 21, 29 and 48 keep generous
space on purpose: each is a statement or a pair of numbers, and the space is the pause.

## Decorative imagery

| Slide | Concept | Encodes data? | Decision |
| --- | --- | --- | --- |
| 1, 51 | raking light finds a raised pad | no | kept; the unverifiable pad count was removed from the caption |
| 13 | a regular surface shows what departs from it | no | six odd pads (could read as a legend of the six types) reduced to one raised pad |
| 24 | 152 pool tables, 100 labelled problems | the two counts only | kept; lit pads are a seeded shuffle, caption says which pads are lit is arbitrary |
| 31 | 100 pads, 6 and 39 raised | prevalence 5.8% and 39.3%, rounded | kept; caption states the rounding |
| 41, 44 | killed and surviving mutant | no | kept as metaphor; labelled |

All generated illustrations keep the label and `art/PROVENANCE.md`.

## Caption and small text policy

Minimum at 1280 by 720: nothing under 13 px; running words under 14 px are an error; body text 18 px and up. The
checker enforces it, including after a `flow()` has shrunk text. Before this pass the new rule reported 34 findings (tags,
matrix legends, chart notes); all were raised or restructured, none was shrunk to fit.

## Composition repetition

By narrative function after this pass: explanation (6, 7, 9, 15), process (6, 25, 38), dataset accounting (14, 25),
comparison (17, 18, 19, 22), experimental result (20, 26 to 28, 30, 31, 34 to 37), statistical inference (26, 32,
33), limitation (11, 12, 29, 42), mutation testing (43 to 49), summary (39, 40, 50, 51). Slides where one figure sits
on one side and a prose column on the other: 17, 19, 20, 22, 26, 27, 30, 37, 42, 45, 46, eleven in my count, each a
single figure with its reading, which is the honest form for a result with one chart. They are not repeated
consecutively.

Slides 31 to 36 were reviewed as a sequence and changed where the content allowed:

| Slide | Before | After |
| --- | --- | --- |
| 31 | two pad grids left, prose right | unchanged (diagram-led; pads are the figure) |
| 32 | interval chart left, prose and stat right | wide interval chart, then a three-part band (stat, reading, method notes) |
| 33 | ledger left, numerals right | full-width ledger, then a band of two numerals and a note |
| 34 | two bar charts over two paragraphs | unchanged (twin charts) |
| 35 | strip chart, notes below | unchanged (strip chart) |
| 36 | sorted horizontal bars left, prose right | sorted columns across the width, prose above, notes in the chart's empty corner |

## Verification pipeline

`make verify-slides` (also the `slides` job in `ci.yml`): generator and HTML agree, seven font configurations show no
layout issue, the browser regression tests pass. It fails without Chromium; it cannot skip. FAST is unchanged and
independent of any browser. New rules in the probe: `box-crosses-text`, `small-text`, `crowds-footer`, rotated-label
bounds. Regression tests cover each rule with a failing and a passing fixture, the two contrast checks, the native
data, the severity-title claim and the 100 of 152 count.

## Limits

The probe measures geometry. It does not judge contrast of free text, meaning or science; those were checked by
reading the rendered slides against the paper, and by an independent reviewer (below). The PR curves are down-sampled
(0.0025 recall bins). The PCA difference on two panels is unresolved. Only one operating system renders locally; CI
renders on Linux with Liberation and DejaVu fonts.
