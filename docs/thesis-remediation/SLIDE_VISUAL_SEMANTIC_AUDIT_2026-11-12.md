# Visual and semantic audit of the 51-slide deck, 2026-11-12

Every non-text visual, what it is meant to show, whether it is data or illustration, and the verdict after
this pass. "Data" means values copied from `paper/main.tex` or `verification/`; "illustration" means drawn
to explain a concept and labelled as such on the slide. Layout correctness is checked by
`slides/check_layout.py` (see `slides/README.md`); semantics are checked by reading the slide against the paper.

## Defects found and fixed in this pass

| Slide | Defect | Cause | Fix |
| --- | --- | --- | --- |
| 1 | Headline ran into the paragraph when Avenir Next Condensed was missing (reproduced with fallback fonts) | title and paragraph were separate absolutely positioned boxes at fixed heights | one stacked flow container that fits itself; fallback font stack |
| 2, 51 | same collision risk in the statement slides | same | same |
| 5 | six anomaly types drawn as nearly identical 3x3 pad grids | one pictogram parametrised by a defect position | six different diagrams: table with an empty cell, two identical rows, number line with an outlier, 2-D scatter with an unusual pair, distributions moving along time, a form with three rule violations |
| 15 | same pad glyphs again for the six injection formulas | reuse of the same pictogram | numbered typographic list, no pictogram |
| 31 | right column text collided under fallback fonts | fixed positions | stacked flow container |
| 5, 9, 30 | labels outside their svg box | label coordinates | corrected, and now detected by the checker |

Root causes in the generator: every slide was a set of absolutely positioned boxes with hard-coded `top`
values, so any text longer than expected pushed into the next box; nothing measured the rendered result; and one
pictogram function served several unrelated concepts.

## Inventory of visuals

| Slide | Visual | Concept | Kind | Verdict |
| --- | --- | --- | --- | --- |
| 1 | generated still life, one raised pad among 312 | an anomaly shows under raking light | illustration (labelled) | metaphor, not evidence; keep |
| 3 | filled and empty circles per paper and property | what each cited work reports | data (literature scan) | accurate to the slide text |
| 5 | six diagrams | the six injected anomaly types | illustration (labelled) | distinct and each labelled; rebuilt |
| 6 | pipeline boxes and code | extract, transform, detect, load | schematic | matches the paper's pipeline |
| 8 | four lanes of detectors | family taxonomy from the paper | schematic | accurate |
| 9 | normal curve with shaded tails | tails beyond 3 sigma and the IQR fences | illustration with data (0.27%, 0.70%) | tails drawn to scale, so thin; labelled "flagged tails" |
| 13 | plate of pads with six defective pads | decorative opener | decoration (labelled) | not a type legend; caption says so |
| 14 | log axis of anomaly share | four datasets | data | accurate |
| 17, 18 | bar charts | AP, F1, precision per detector | data, axis from 0 | accurate |
| 19 | precision-recall scatter with F1 curves | ten of seventeen detectors | data | accurate, subset stated |
| 20, 27, 28 | matrices on cividis | recall or AP per detector and type | data | accurate; 28 parsed from `verification/evidence/full_registry/summary.md` |
| 22, 23 | archived matplotlib figures | PR curves, severity curves | data | accurate, off-palette, small legends (open) |
| 24 | plate of 152 pads, 100 with a lit edge | decorative opener | decoration (labelled) | counts are encoded but not readable as data; caption says so |
| 25 | funnel boxes | dataset accounting | data | 47 to 36, 689 to 133 to 116, 36 + 116 = 152, 36 + 64 = 100 |
| 26, 32 | interval dot plots | median with 95% interval | data | accurate |
| 30 | slope chart | AP stratified against chronological | data | accurate |
| 31 | two grids of 100 pads | 5.8% and 39.3% prevalence | illustration (labelled, rounded to 6 and 39) | accurate within rounding |
| 33 | verdict tags | six hypotheses | data | holds or not supported with a symbol and a word |
| 34, 36, 37 | bars, log bars | LSTM AP, multivariate recall, detection time | data | accurate; 37 uses a log axis, stated |
| 35 | strip plot | three schemas | data | accurate |
| 38 | routing diagram | type to stage and method | schematic | matches the paper's recommendation |
| 41, 44 | generated still life, raised and cracked pad | killed and survived mutant | metaphor (labelled) | see ambiguity below |
| 43 | code diff and test trace | what a mutant changes | illustration with real code from `alert_budget.py` | accurate |
| 45 | n > 0 against n >= 1 table | an equivalent mutant | illustration | correct for integers |
| 46 | threshold bars | L1 to L4 | data | bars from zero; thresholds not changed |
| 47 | dumbbell chart | raw focused score per module | data | axis starts at 40%, stated |
| 49 | segmented bar | 26, 31, 25 of 82 modules | data | modules, not mutants, stated |

## Repeated motif audit

The pad appears on the cover, slides 13, 24, 31, 41, 44 and 51. Its meaning is consistent as "what light
reveals": an anomaly (1, 31, 51) or a mutant that a test sees (44). Slides 31 and 44 give the pad two referents
(an anomalous row, a killed mutant), and each states its mapping in a caption. The six anomaly types are
deliberately not drawn with pads any more.

## Not verified here

Fonts other than Avenir Next Condensed were tested only through one fallback (Arial). Small chart labels on
slides 22 and 23 (archived figures) remain below the legibility floor. The cividis scale is perceptually
uniform and colour-blind safe, but the yellow end resembles amber; every amber mark also has a word.
