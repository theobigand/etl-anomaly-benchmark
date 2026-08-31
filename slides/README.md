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
