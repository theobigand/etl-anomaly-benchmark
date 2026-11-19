"""Vector versions of the two heatmap figures of the manuscript, regenerated from the archived runs.

Figure 1 (synthetic detection rate by type) and Figure 3 (median detection rate over the real
tables) come from ``research/full_registry_summary.py``: this script runs that same ``build`` on the
archived evidence and only changes the output format, a PDF whose fonts are embedded as TrueType
(``pdf.fonttype = 42``, accepted by IEEE PDF eXpress), so the cell annotations are the values of the
generated tables and of nothing else.

    python paper/make_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "research"), str(ROOT / "src"), str(ROOT / "experiments")]

import full_registry_summary as frs  # noqa: E402

FIGURES = Path(__file__).resolve().parent / "figures"


def _vector(frame, title: str, name: str) -> None:
    """The heatmap of ``frs.tf._draw``, drawn at the width of an IEEE column (3.45 in) so that
    its text keeps its size in print: tick labels 6.5 pt, cell values 5.5 pt, title 7 pt."""
    labels = [frs.tf.LABELS.get(c, c) for c in frame.columns]
    fig, ax = plt.subplots(figsize=(3.45, 0.17 * len(frame) + 0.95))
    ax.imshow(frame.to_numpy(dtype=float), cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(frame.shape[1]), labels, rotation=35, ha="right", fontsize=6.5)
    ax.set_yticks(range(frame.shape[0]), list(frame.index), fontsize=6.5)
    ax.set_title(title, fontsize=7)
    for i in range(frame.shape[0]):
        for j in range(frame.shape[1]):
            v = frame.iloc[i, j]
            ax.text(
                j,
                i,
                f"{v:.2f}",
                ha="center",
                va="center",
                fontsize=5.5,
                color="white" if v > 0.6 else "black",
            )
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGURES / f"{name}.pdf")
    plt.close(fig)


def main() -> int:
    matplotlib.rcParams["pdf.fonttype"] = 42
    evidence = frs.EVIDENCE
    out = evidence / "full_registry"
    # Figure 3: the 42 UCI tables of the typed-injection study (the 16 ADBench carriers of the
    # pool extension are reported separately in the manuscript)
    typed = frs.merged_typed(evidence / "typed_injection" / "runs", out / "typed_deep" / "runs")
    _vector(
        frs.ordered(frs.ts.pooled(typed)["median"]),
        f"Median detection rate, {len(typed)} real tables",
        "typed_pooled",
    )
    # Figure 1: the synthetic customer table, five seeds
    _vector(
        frs.synthetic_matrix(evidence, out),
        "Mean detection rate, synthetic, 5 seeds",
        "heatmap_full",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
