# Repository rules

## Living thesis presentation

The repository keeps one presentation, `slides/thesis_progress.html`
(rendered to `slides/thesis_progress.pdf` with `make slides`). It is built
with the `personal-editorial-skill` from the `main` branch of the dotfiles
repository (`~/dotfiles/ai/skills/shared/personal-editorial-skill`). Read that
skill before touching the deck, and keep its visual identity.

The deck is a living document with two jobs:

- at any moment it shows where the thesis stands: what is done, what is
  running, what is next;
- at the end of the thesis it is the finished presentation of the whole work.

Rules:

- Every change that moves the thesis forward updates the deck in the same
  branch: a new result, figure or table, a merged issue, a changed claim, a
  new section of the paper. Do not leave it for later.
- Keep it truthful. Numbers and figures come from the archived runs and
  `paper/`, never retyped from memory. When a result is replaced, the slide
  changes with it.
- Show status honestly: separate finished work, work in progress and planned
  work, and mark anything not yet validated.
- Regenerate and commit the PDF with the HTML (`make slides`). Run
  `make heatmap`, `make curves` and `make severity` first if figures changed.
- Keep the deck compact. Add slides for new substance, and merge or drop
  slides that are no longer worth their space, so it stays presentable at the
  end without a rewrite.
- A pull request that changes results, the paper or the roadmap and leaves
  the deck untouched must say why in its description.

## Paper voice

The paper has a single author. Write in the first person singular ("I report",
"my pipeline") or impersonally, never "we" or "our".
