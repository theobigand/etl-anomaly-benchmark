"""Vector figures of the manuscript, regenerated from archived data (no value is typed by hand).

Figure 1 (synthetic detection rate by type) and Figure 3 (median detection rate over the real
tables) come from ``research/full_registry_summary.py``: this script runs that same ``build`` on the
archived evidence and only changes the output format, a PDF whose fonts are embedded as TrueType
(``pdf.fonttype = 42``, accepted by IEEE PDF eXpress), so the cell annotations are the values of the
generated tables and of nothing else.

Figures 2 and 4 (severity and precision-recall curves) and the quality-versus-cost figure are drawn
at the width of an IEEE page or column with one colour-blind-safe style per detector (Okabe-Ito
colours, then dashes), so that no two curves share a colour and a line style.

    python paper/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "research"), str(ROOT / "src"), str(ROOT / "experiments")]

import full_registry_summary as frs  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from paper_tables import NAMES  # noqa: E402

FIGURES = Path(__file__).resolve().parent / "figures"
#: Okabe-Ito colour-blind-safe palette (black first, the pale yellow replaced by a grey)
PALETTE = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#D55E00", "#0072B2", "#CC79A7", "#8C8C8C"]
LINESTYLES = ["-", "--", ":"]
DISPLAY = {**NAMES, "drift": "Row drift"}
ORDER = list(DISPLAY)
FAMILY_MARKER = {"rule": "o", "classical": "s", "neural": "^"}
#: labels placed to the left of their point where the right side is taken by a neighbour
LABEL_OFFSET = {"deep_svdd": (-3, -9), "lof": (-3, -9)}
RULES, CLASSICAL = ORDER[:3], ORDER[3:11]


def style(method: str) -> dict:
    """The colour and line style of a detector, the same in every figure."""
    i = ORDER.index(method)
    return {"color": PALETTE[i % len(PALETTE)], "linestyle": LINESTYLES[(i // len(PALETTE)) % 3]}


def family(method: str) -> str:
    return "rule" if method in RULES else "classical" if method in CLASSICAL else "neural"


def _legend(fig, handles, ncol: int) -> None:
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=ncol,
        fontsize=6.5,
        frameon=False,
        handlelength=2.6,
        columnspacing=1.0,
        borderaxespad=0.0,
    )


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


def pr_curves() -> None:
    """Figure 4: precision-recall curves of seed 42, from the data the slides draw."""
    data = json.loads((ROOT / "slides" / "art" / "data" / "pr_curves.json").read_text())
    names = {"credit_card": "Credit Card", "water_quality": "Water Quality", "cardio": "Cardio"}
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 5.5), sharex=True)
    handles = {}
    for ax, (key, panel) in zip(axes.flat, data["datasets"].items(), strict=True):
        for method, curve in panel["methods"].items():
            xs, ys = zip(*curve["points"], strict=True)
            (line,) = ax.plot(xs, ys, linewidth=1.1, label=DISPLAY[method], **style(method))
            handles.setdefault(method, line)
        ax.axhline(panel["base_rate"], color="0.55", linewidth=0.7, linestyle="-.")
        ax.set_title(names.get(key, key.capitalize()), fontsize=8)
        ax.set_ylabel("precision", fontsize=7.5)
        ax.set_xlim(0, 1.01)
        ax.set_ylim(0, 1.02)
        ax.tick_params(labelsize=7)
    for ax in axes[-1]:
        ax.set_xlabel("recall", fontsize=7.5)
    ordered = [handles[m] for m in ORDER if m in handles]
    fig.tight_layout(rect=(0, 0.07, 1, 1), pad=0.5)
    _legend(fig, ordered, 6)
    fig.savefig(FIGURES / "pr_curves.pdf")
    plt.close(fig)


def severity_curves() -> None:
    """Figure 2: per-type recall against injection severity, from the archived severity run."""
    frame = pd.read_csv(ROOT / "verification" / "evidence" / "severity.csv")
    types = ["univariate_outlier", "multivariate_outlier", "temporal_drift"]
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.9), sharey=True)
    handles = {}
    for ax, kind in zip(axes, types, strict=True):
        sub = frame[frame["anomaly_type"] == kind]
        for method in ORDER:
            line = sub[sub["method"] == method].sort_values("severity")
            if line.empty:
                continue
            (handle,) = ax.plot(
                line["severity"],
                line["recall"],
                marker="o",
                markersize=2.2,
                linewidth=1.1,
                label=DISPLAY[method],
                **style(method),
            )
            handles.setdefault(method, handle)
        ax.axvline(1.0, color="0.55", linewidth=0.7, linestyle="-.")
        ax.set_title(kind.replace("_", " "), fontsize=8)
        ax.set_xlabel("injection severity (1.0 = reference)", fontsize=7)
        ax.set_ylim(-0.03, 1.03)
        ax.tick_params(labelsize=7)
    axes[0].set_ylabel("recall on that type", fontsize=7.5)
    fig.tight_layout(rect=(0, 0.17, 1, 1), pad=0.5)
    _legend(fig, [handles[m] for m in ORDER if m in handles], 6)
    fig.savefig(FIGURES / "severity_curves.pdf")
    plt.close(fig)


def detection_times(evidence: Path, size: int = 10_000) -> dict[str, float]:
    """Median detection-stage time at ``size`` rows from the two archived cost studies."""
    times = {}
    for path in (
        evidence / "cost_study" / "cost_study.json",
        evidence / "full_registry" / "cost" / "cost_study.json",
    ):
        for method, summary in json.loads(path.read_text())["summary"].items():
            times[method] = summary["points"][str(size)]["detect_s_median"]
    return times


def quality_cost() -> None:
    """Quality-versus-cost figure: median AP over the labelled pool against detection-stage time.

    Quality and cost come from different studies (the labelled pool, and synthetic data of eight
    features), so the figure compares ranks of two separate measurements, not a joint outcome.
    """
    evidence = frs.EVIDENCE
    results = json.loads((evidence / "labelled_pool" / "labelled_results.json").read_text())

    def table(payload: dict) -> pd.DataFrame:
        return pd.DataFrame(payload["data"], payload["index"], payload["columns"])

    quality = pd.concat([table(results["pr_auc"]), table(results["deep"]["pr_auc"])])
    times = detection_times(evidence)
    fig, ax = plt.subplots(figsize=(3.45, 3.0))
    for method in ORDER:
        if method not in times or method not in quality.index:
            continue
        row = quality.loc[method]
        ax.errorbar(
            times[method],
            row["median"],
            yerr=[[row["median"] - row["lo"]], [row["hi"] - row["median"]]],
            color=style(method)["color"],
            marker=FAMILY_MARKER[family(method)],
            markersize=4,
            linewidth=0.6,
            capsize=1.2,
        )
        ax.annotate(
            DISPLAY[method].replace("Isolation Forest", "IF").replace("One-Class SVM", "OCSVM"),
            (times[method], row["median"]),
            textcoords="offset points",
            xytext=LABEL_OFFSET.get(method, (3, 3)),
            ha="right" if method in LABEL_OFFSET else "left",
            fontsize=5,
        )
    ax.set_xscale("log")
    ax.set_xlim(1e-3, 150)
    ax.set_xlabel("median detection-stage time at $10^4$ rows (s)", fontsize=7)
    ax.set_ylabel("median AP, labelled pool", fontsize=7)
    ax.tick_params(labelsize=6.5)
    markers = [
        plt.Line2D([], [], color="0.3", marker=m, linestyle="", markersize=4, label=label)
        for label, m in (("rule", "o"), ("classical", "s"), ("neural", "^"))
    ]
    ax.legend(handles=markers, fontsize=6, loc="lower right", frameon=False)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGURES / "quality_cost.pdf")
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
    pr_curves()
    severity_curves()
    quality_cost()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
