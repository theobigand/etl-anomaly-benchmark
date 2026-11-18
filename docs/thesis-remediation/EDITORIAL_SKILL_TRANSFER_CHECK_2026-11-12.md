# Editorial skill v6.4 against v6.3: bounded cross-theme check, 2026-11-12

Verdict: **no improvement demonstrated.** In this small test v6.3 was preferred in two themes and tied in
the third. The result is weak evidence either way (one generation per cell, one model family, one blind
reviewer from the same family), but it does not support the claim that v6.4 transfers better. The skill was
not changed in response, because the sample cannot separate a real regression from noise.

## Method

- Frozen skills: v6.3 (`c457ad5^`) and v6.4 (`c457ad5`) exported from the dotfiles repository, 7 files differ.
- Three briefs with fictional data (`briefs/`): technical (blade inspection results), creative (ceramics
  collection launch), business (quarterly operating review with three decisions).
- Six isolated agents, one per theme and version, same common instructions: six 1280x720 slides in one
  HTML file, no raster images, at most two revision passes, render and inspect. Each agent read only its
  skill folder and brief.
- Blind review: an agent that was not told the versions compared labelled pairs X and Y per theme from
  contact sheets (`blind-*.jpg`; the mapping is in `blind-mapping.json`, hidden from the reviewer).
- Objective check: dominant hex colours and first font family in each `deck.html`.

## Results (blind review, then unblinded)

| Theme | X / Y | Reviewer verdict | Which version won |
| --- | --- | --- | --- |
| Technical | X = v6.3, Y = v6.4 | X stronger: 240-cell evidence grid, cost bars, protocol diagram; Y flatter from slide 4 | v6.3 |
| Creative | X = v6.4, Y = v6.3 | Y stronger: more specific, tactile vessel illustration, tide-curve timeline | v6.3 |
| Business | X = v6.3, Y = v6.4 | tie, leaning X (working charts, framing slides) | v6.3 or tie |

Convergence across themes: the reviewer judged the Y set more template-like (cream ground, serif headlines,
hairlines, large figures). Y contained v6.4 technical and business and v6.3 creative, X contained v6.3
technical and business and v6.4 creative, so this comparison mixes versions and says little about either.
Objective check: v6.4 technical (`#f2f1ec` paper, `#c4531f` ember, Georgia) and v6.4 business (`#f6f0e3`
paper, `#a2332a`, Georgia) share a warm paper, terracotta and a serif; v6.3 technical used a cool grey-green
field (`#f1f3f0`, teal and orange-red) and Iowan Old Style. So on this sample v6.4 converged slightly more,
not less.

Imagery: no agent in either version used or generated photographs (not allowed here), and all six argued
against photography with a content reason. The photography-consideration change could therefore not be
exercised by this design. Light and shadow appeared only in the v6.4 creative deck (raking light stated).

## What this does and does not show

- It shows that the v6.4 wording did not, under these conditions, change the visible outcome for the better.
- It does not show a regression: n = 1 per cell, no repetitions, and v6.3 had already derived palettes and
  rejected decorative imagery with reasons in its notes.
- The test could not exercise image generation, so the main v6.4 change (considering imagery for technical
  work) is untested. A fair test needs image tooling and several repetitions per cell.

## Follow-up (not done)

Repeat with three generations per cell, allow image generation, add a fourth theme with a strongly physical
subject, and have two reviewers from different model families. Until then v6.4 stays as committed
(`c457ad5`), with this negative result recorded.
