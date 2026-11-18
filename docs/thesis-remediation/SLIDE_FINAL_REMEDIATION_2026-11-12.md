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
Choice of colour: the highest-AP method in each panel is dark and solid, the lowest-AP method is dashed grey, the
others are light grey. The choice is by rule, so no method is picked to suit the argument; the key under each panel title
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

## Independent review (two fresh reviewers, after the correction pass)

Two reviewers that had not touched the deck worked from the rendered 150 dpi images, the manuscript and the audit
documents: one on typography, layout, diagrams, colour and rhythm (all 51 slides opened), one on every number and claim
against `paper/main.tex` and the committed evidence. Their reports are not copied here; each finding was checked
against the source before acting, and one claim of the visual reviewer was wrong (below).

Scientific review: 4 blocking, 8 major, 14 minor. All four blocking and the verifiable majors were corrected.

| Slide | Finding (verified against) | Action |
| --- | --- | --- |
| 47 | "Nine of 82 L4 modules": the campaign evidence (`risk-native-campaign-2026-11-07.json`) lists only `pool_check`, `normalise` and `paired_bootstrap` among the nine, so six are not in it; MUTATION_FOCUSED_DIAGNOSTICS line 13 says five, which omits `source_clustered` (added the same day, commit be43503). The note and the evidence disagree; the slide follows the evidence | caption says six are not in the campaign |
| 29 | 0.83 is the correlation with the first eight rows; with seventeen detectors the paper gives 0.80, lowest for drift at 0.63 (paper, typed injection); "0.70 for drift" had no source | corrected |
| 14, 17, 39 | "neither scales", "do not survive": the paper says LOF and One-Class SVM were expected to be too costly and not measured; slide 37 shows LOF finishing 300,000 rows | reworded to "not run, expected too costly, not measured" |
| 4 | "every study", "pre-registered": paper lines 888, 1157 and 2365 describe post-hoc and already-known results | reworded |
| 14, 17, 40 | 0.01 to 0.20 mixed a one-seed baseline with a five-seed mean; paper: 0.01 to 0.28 on the table's seed, 0.20 over five seeds | both stated |
| 23 | "saturated at severity 0.5" is false for LOF (0.67) and Great Expectations (0.15) in the CSV | names the detectors that are |
| 22 | scope of "highest AP" (neural models not drawn), PCA difference, "0.41" (about 0.4) | stated on the slide |
| 27, 33, 26 | missing "historical, needs train-only replay" tag; post-hoc analysis not labelled; "all 152 datasets" over-claims | tags added, title scoped |
| 38 | routing recommendation shown as general | states that it does not transfer to the real tables |
| 3, 18, 30, 40, 42, 50 and 51 | AUC-only wording, IQR F1 0.33, "only dataset with a clock", range 0.00 to 0.28, "verified", IMRaD contradiction | corrected |

Round 2 (the same two reviewers, changed slides only): no blocking finding; the scientific reviewer found slide 47 still
wrong (six, not five, see above), KNN missing from the not-run list (slides 14, 17, 39), the P3 wording (slide 33),
the slide 4 sentence cut by an edit, and a title (slide 15) that over-generalised; the visual reviewer found slide 36
text colour, slide 37 caption ("bars"), the slide 41 line break and the raw table label on slide 19. All were fixed.
Left as minor: label matching on slide 23, empty areas on slides 30, 42, 48 and 51, baseline alignment in the slide 15
ledger, slide 44's faint crack.

Not adopted: slide 8 "20 neighbours" (the PyOD default, kept); the paper's own inconsistencies (19 sources, the six or
seven modules at 98%, "dominate" on credit card) are reported, not edited here.

Visual review: no blocking finding; 11 major, 17 minor. Corrected: tails and fences on slide 9; leader lines on slide
19; scrims under the captions of the pad openers (13, 24, 41, 51) and the title of slide 41 moved off the raised pad;
slide 43 colour (a killed mutant is steel, not amber); slide 22 dashed series no longer uses steel for "lowest";
slide 23 labels the series the text names; slide 30 and 34 headlines now say what their charts show; slide 37 draws
dots on the log axis instead of bars that start at an arbitrary 0.01 s; slide 36 no longer uses steel for a family;
slide 35 staggers identical markers; slide 31 scatters the raised pads (position is arbitrary); slide 15 became a
ledger so that it no longer repeats the numeral grid of slide 40; slides 26 and 32 name their axes; slide 48 sizes the
two numerals alike.

Not changed, with reasons: slide 44 (the survivor is a faint crack by design, the metaphor is "nothing noticed it";
regenerating the image was not attempted); slide 20 contrast (computed minimum 4.68:1, the reviewer's "about 4:1"
was an estimate by eye); slide 23 axis (it is linear in severity, ticks at 0.5, 1, 2, 3, 5 are not evenly spaced);
slide 25 (adding a 116 to 64 step would need a source I did not verify); the remaining minor spacing items (28, 29, 42,
the dark text-only run of 10 to 12) are left.

## What the Linux render showed (found after the reviews)

The `slides` job uploads a 60 dpi render made on Linux, where Avenir is absent. Reading it showed what the macOS-only
checks had missed, although the probe reported zero issues there: headlines of slides 3, 4, 5, 15, 18, 45 wrapped to a
second line, on slide 5 behind the diagram panels (text hidden by a later shape, which text-against-text overlap cannot
see) and on slide 45 against the first heading. Causes and changes: headlines were sized for a condensed face with
fixed positions below them; they now shrink to one line (`fit1`); the probe reports text occluded by a later shape and
judges line-box overlap more strictly (display numerals and lines of one heading excepted); the openers 13 and 24, the
RQ rows of slide 4 and the right column of slide 19 became stacks; the condensed font stack gained Liberation Sans
Narrow and DejaVu Sans Condensed. A latent defect surfaced on the way: `fitFlow` reset its transform on slides that are
hidden at `beforeprint`, so shrunk stacks would have printed unshrunk; hidden slides are now skipped. Verified in
Chromium with the stylesheet forced to Verdana and printed to PDF, and by the CI job (Linux, DejaVu Sans and Liberation
fonts). The macOS-rendered PDF in the repository uses the intended fonts.

## Editorial skill

Not changed. The defects that the checker missed (a box border through text, a title contradicting the data after a
chart was rebuilt, label text on busy imagery) are covered by existing Gate 16 (rendered inspection, collision
detection, diagram-to-concept consistency); what failed was execution, and the probe rules above are specific to this
deck. One possible transferable rule, "when a visual is rebuilt from data, re-derive the headline and every statistic
beside it from the same data", rests on a single incident here and was not added. No claim is made that v6.4 improves
on v6.3; the earlier comparison did not show it.

## Limits

The probe measures geometry. It does not judge contrast of free text, meaning or science; those were checked by
reading the rendered slides against the paper, and by an independent reviewer (below). The PR curves are down-sampled
(0.0025 recall bins). The PCA difference on two panels is unresolved. Only one operating system renders locally; CI
renders on Linux with Liberation and DejaVu fonts.
