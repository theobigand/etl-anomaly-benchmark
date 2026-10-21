"""Heatmaps of the typed-injection results: pooled median and six panels chosen by UCI id."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LABELS = {
    "missing_value": "missing",
    "duplicate": "duplicate",
    "univariate_outlier": "univariate",
    "multivariate_outlier": "multivariate",
    "temporal_drift": "drift",
    "invalid_format": "invalid",
}


def _draw(ax, frame: pd.DataFrame, title: str, annotate: bool = True) -> None:
    ax.imshow(frame.to_numpy(dtype=float), cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(
        range(frame.shape[1]), [LABELS.get(c, c) for c in frame.columns], rotation=35, ha="right"
    )
    ax.set_yticks(range(frame.shape[0]), list(frame.index))
    ax.set_title(title, fontsize=9)
    if annotate:
        for i in range(frame.shape[0]):
            for j in range(frame.shape[1]):
                v = frame.iloc[i, j]
                ax.text(
                    j,
                    i,
                    f"{v:.2f}",
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color="white" if v > 0.6 else "black",
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--panels", type=int, default=6)
    args = parser.parse_args(argv)
    runs = sorted(
        (json.loads(p.read_text()) for p in args.runs.glob("*.json")), key=lambda r: r["uci_id"]
    )
    frames = {
        r["name"]: pd.DataFrame(
            r["recall_mean"]["data"],
            index=r["recall_mean"]["index"],
            columns=r["recall_mean"]["columns"],
        )
        for r in runs
    }
    args.output.mkdir(parents=True, exist_ok=True)
    median = pd.DataFrame(
        np.nanmedian(np.stack([f.to_numpy(dtype=float) for f in frames.values()]), axis=0),
        index=next(iter(frames.values())).index,
        columns=next(iter(frames.values())).columns,
    )
    fig, ax = plt.subplots(figsize=(7, 5))
    _draw(ax, median, f"Median detection rate over {len(frames)} real datasets (typed injection)")
    fig.tight_layout()
    fig.savefig(args.output / "typed_pooled.png", dpi=160)
    plt.close(fig)
    names = [r["name"] for r in runs][: args.panels]
    cols = 3
    rows = -(-len(names) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(5.2 * cols, 3.6 * rows), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for ax, name in zip(axes.ravel(), names, strict=False):
        ax.axis("on")
        _draw(ax, frames[name], name[:38])
    fig.tight_layout()
    fig.savefig(args.output / "typed_panels.png", dpi=130)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
