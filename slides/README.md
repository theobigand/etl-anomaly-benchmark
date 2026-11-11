# Slides

`thesis_progress.html` is the source. It is a self-contained editorial deck
(keyboard / dot / swipe navigation, one slide per viewport) with a
`@media print` block that lays each slide out as one 1280x720 page.

`thesis_progress.pdf` is rendered from it and committed. To regenerate:

```bash
make slides CHROME=/path/to/chrome        # or chromium, or chrome-headless-shell
```

Any Chromium-family binary with `--print-to-pdf` works. The figures are
pulled from `../paper/figures/`, so run `make heatmap`, `make curves` and
`make severity` first if those changed.

## Rendering used for review (2026-11-11)

The regular Chrome binary can hang; the Playwright headless shell is reliable:

```bash
CH=~/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell
$CH --no-sandbox --headless --no-pdf-header-footer \
  --print-to-pdf=slides/thesis_progress.pdf "file://$PWD/slides/thesis_progress.html"
pdftoppm -r 150 -png slides/thesis_progress.pdf /tmp/slides   # review at 150 dpi, not 45-80
```

## Visual provenance

The deck contains no photographs and no generated images. The cover matrix is drawn in SVG from
the mean recall values of the synthetic customer table (paper, Appendix C, Table
`m-customer`); each cell carries its value in a tooltip. The mutation chart is drawn in SVG from
`docs/thesis-remediation/MUTATION_FOCUSED_DIAGNOSTICS_2026-11-11.md`. Both stay editable in the
HTML source. The remaining figures are the archived PNGs of `paper/figures/`.
