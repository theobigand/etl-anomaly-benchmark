# Editorial benchmark synthesis, 2026-11-12

Purpose: evidence for the v6.4 revision of the global editorial skill and for the redesign of the thesis deck.
"Observed" means seen in a file or render I opened in this session. "Hypothesis" is my own reading.

## What was actually inspected

Opened and looked at (renders):

- `cross-theme-creative/comparisons/06-lighting-and-shadow.jpg` (VEILLE, RIVAGE, ATELIER BRUT photographs)
- `cross-theme-creative/comparisons/04-presentations.jpg` (the three creative decks)
- `technical-cross-domain/comparisons/11-opticbench-photographic-lighting-set.png` (ten OpticBench frames)
- `technical-cross-domain/comparisons/07-decks-six-slides.jpg` (FleetOps, SignalLab, OpticBench decks)
- `claude-photo-direction-test/evidence/final/home-desktop-fold.png` (ORÉE home)

Read (reports): `technical-cross-domain/BENCHMARK_REPORT.md`, `VISUAL_TRANSFER_REVIEW.md` (matrix and structural comparison),
`cross-theme-creative/CROSS_THEME_REVIEW.md`, `controlled-v6-v61/VISUAL_CONVERGENCE_DIAGNOSIS.md`,
`reference-ablation/ABLATION_REVEAL_AND_ROOT_CAUSE.md`, `IMAGE_DIRECTION_FINAL_REVIEW.md`, the ORÉE and OpticBench prompt files and the image generation script.

Not inspected (so no claim is made about them): the FleetOps and SignalLab websites and Excel files, the ORÉE rejected image and
its other pages, the nightshift comparisons, the v6 versus v6.1 renders themselves, the raw blind reviews, `composition-gate`
screenshots, and the Word documents.

## Observed findings

1. **Light was the content in the strongest work.** VEILLE: streets lit only by their own equipment; darkness means absence.
   ATELIER BRUT: raking sun makes the cast shadow a second drawing of the volume. RIVAGE: overcast light, caustics, refraction.
   OpticBench: the lighting condition is the test variable, and the shadow length orders with source elevation.
2. **Photography that carried evidence integrated best.** OpticBench frames are keyed to measured conditions; the same
   report rates the six-frame slide as the weakest (gallery-like at projection size).
3. **Prediction before generation worked.** OpticBench rejected a frame whose light was on the wrong side for any shadow to form.
4. **Type sat where the image left calm surface** (ORÉE plaster, VEILLE unlit facade, ATELIER BRUT wall) and kept both intact.
5. **Recurring tells in generated sets:** the same wet ground (8 of 11 VEILLE frames), spotless glass, evenly lit floors,
   a doubled specular spot, objects slightly off proportion.
6. **Convergence is real and structural.** Three isolated agents produced the same web opener, the same pale cool-grey field,
   the same Office type trio and the same slide shell. Only a coordinator comparison caught it.
7. **The convergence diagnosis points at the process, not one model default.** Narrow references plus concrete presets
   gave similar starting points; there was no rendered comparison of alternatives before commitment; later review was mostly repair.
   Both v6 runs used the identical `#f4f0e7` paper and `#a64b34` accent, which matches the preset text.
8. **Data-led work was never given an image alternative.** FleetOps named a power and storage schematic as the reason to skip
   photography and then did not draw it. SignalLab's strength (one aligned time axis) came entirely from the data.
9. **The deck shell repeated** across technical subjects: point title top-left over evidence. FleetOps and OpticBench shared title
   position and weight; SignalLab put the claim column beside the figure.
10. **Creative decks varied more** (bleed, chart, evidence, detail, bleed, letterbox) and were rated Good for rhythm, still with
    repeated text-left, image-right rows.

## Weakest recurring patterns (observed)

Title-over-photograph openers; wordmark-and-links header with a boxed theme button; photograph beside a control list; cool or
warm pale field by default; serif display with sans body; the same hero object repeated across adjacent slides; six thumbnails in one grid.

## Skill instructions that plausibly feed convergence (hypothesis, tied to the text)

- `SKILL.md` step 1 and `ART_DIRECTION.md` said technical and scientific subjects "need no imagery" and photography "rarely helps".
  This made absence the default for exactly the subjects where the benchmark did not test an image.
- Concrete palettes and font stacks (paper `#A64B34`, ivory `#FAF8F2`, serif plus sans) sat in the reference material and
  reappeared in outputs.
- Sequence rhythm was asked for in prose but had no inventory step, so repetition passed per-slide review.
- Anti-convergence existed only for several identities in one task, not against earlier outputs or one's own earlier version.

## Lessons by topic

- **Image direction:** an image needs a job (evidence, context, metaphor the audience can decode); predict physical consequences first;
  lock a reference, then edit; label illustrations; never replace a chart.
- **Light and shadow:** one stated source, shadows that follow geometry; light that carries meaning beats light that decorates;
  graphic depth only for real layers.
- **Composition and rhythm:** role decides structure; build an inventory and read it as a sequence; pauses are part of rhythm.
- **Colour:** derive from material, light and semantics; test candidates in rendered compositions, not swatches.

## Changes made to the skill (v6.4, `dotfiles` commit c457ad5)

`SKILL.md`, `ART_DIRECTION.md` (imagery consideration, light as a resource, shadow and depth justification, palette derivation,
composition planning, anti-convergence review), `IMAGE_DIRECTION.md` (benchmark lessons), `PRESENTATION_RULES.md` (sequence
inventory), `REVIEW_LOOP.md`, `QUALITY_GATES.md` (Gate 15), `README.md`. No preset was added. The existing docs generator tests still
pass (79) and the output voice check passes.

## Limits

Independent re-evaluation of the revised skill on other themes is in `EDITORIAL_SKILL_TRANSFER_CHECK_2026-11-12.md` where it exists.
Self-assigned scores are not evidence of improvement.
