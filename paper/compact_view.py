"""Compact view of the four full per-type matrices of the manuscript.

The appendix "Full per-type matrices" is generated and holds every value. This script derives from
those same tables, and from nothing else, which detector is best on each injected type of each
dataset, so that the reader gets the competence map without reading 4 x 17 rows. No value is
invented or rounded further: a cell repeats the maximum of a column of a matrix.

    python paper/compact_view.py            rewrite the block between the markers of paper/main.tex
    python paper/compact_view.py --check    exit 1 when the block is stale (for a review or a hook)
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

TEX = Path(__file__).resolve().parent / "main.tex"
START = "% BEGIN generated compact view\n"
END = "% END generated compact view\n"
MATRICES = "% BEGIN generated matrices\n"
DATASETS = [
    ("tab:m-customer", "Customer table"),
    ("tab:m-transactions", "Card transactions"),
    ("tab:m-sensors", "Sensor readings"),
    ("tab:m-typed", "42 real tables"),
]
TYPES = [
    "Missing values",
    "Duplicates",
    "Univariate outliers",
    "Multivariate outliers",
    "Drift",
    "Invalid values",
]


def _matrix(text: str, label: str) -> list[tuple[str, list[float]]]:
    start = text.index(f"\\label{{{label}}}")
    block = text[start : text.index("\\end{tabular}", start)]
    rows = []
    for line in block.splitlines():
        if "&" not in line or line.lstrip().startswith("Method"):
            continue
        cells = [c.strip().rstrip("\\").strip() for c in line.split("&")]
        values = [float(re.sub(r"\\textbf\{(.*?)\}", r"\1", c)) for c in cells[1:]]
        rows.append((cells[0], values))
    if any(len(values) != len(TYPES) for _, values in rows) or not rows:
        raise ValueError(f"{label}: expected {len(TYPES)} values on every row")
    return rows


def _best(rows: list[tuple[str, list[float]]], column: int) -> tuple[float, list[str]]:
    top = max(values[column] for _, values in rows)
    return top, [name for name, values in rows if abs(values[column] - top) < 1e-9]


def _cell(top: float, names: list[str]) -> str:
    label = " / ".join(names) if len(names) <= 2 else f"{len(names)} detectors"
    return f"{label} ({top:.2f})"


def render(text: str) -> str:
    matrices = {label: _matrix(text, label) for label, _ in DATASETS}
    wins: Counter[str] = Counter()
    body = []
    for column, kind in enumerate(TYPES):
        cells = []
        for label, _ in DATASETS:
            top, names = _best(matrices[label], column)
            wins.update(names if len(names) <= 2 else [])
            cells.append(_cell(top, names))
        body.append(f"{kind} & " + " & ".join(cells) + r" \\")
    top = [f"{name} ({count} cells)" for name, count in wins.most_common(3) if count > 1]
    leaders = (", ".join(top[:-1]) + " and " + top[-1]) if len(top) > 1 else "".join(top)
    detectors = sorted({name for rows in matrices.values() for name, _ in rows})
    lines = [
        START.rstrip("\n"),
        r"\section{Which method detects which type: a compact view}",
        r"\label{app:compact}",
        r"The next appendix gives every value; this one keeps only the best detector of each",
        r"column of its tables, which is what the claim that each method has a narrow",
        r"competence rests on.",
        r"A cell names the detector or detectors that reach the highest recall of a type on a",
        r"dataset, with that recall; when more than two detectors tie, the cell gives their",
        r"number.",
        r"Nothing here is a new measurement: every cell repeats a value of",
        r"Tables~\ref{tab:m-customer} to~\ref{tab:m-typed}, which are generated from the",
        r"archived runs.",
        "",
        r"\begin{table*}[t]",
        r"\caption{Best detector by injected type and dataset, from the full matrices of the",
        r"next appendix (mean recall over five seeds for the three synthetic tables, median over",
        r"the tables for the real ones).}",
        r"\label{tab:compact}",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{lllll}",
        r"\toprule",
        "Type & " + " & ".join(name for _, name in DATASETS) + r" \\",
        r"\midrule",
        *body,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table*}",
        "",
        f"Across the {len(TYPES) * len(DATASETS)} cells, {len(detectors)} detectors appear in the"
        " matrices."
        + (f" Where at most two detectors tie, the leaders are {leaders}." if leaders else ""),
        END.rstrip("\n"),
    ]
    return "\n".join(lines) + "\n"


def current(text: str) -> str:
    """The text of ``text`` with the compact block regenerated from its matrices."""
    block = render(text)
    if START in text:
        head, rest = text.split(START, 1)
        return head + block + rest.split(END, 1)[1]
    head, rest = text.split(MATRICES, 1)
    return head + block + "\n" + MATRICES + rest


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    text = TEX.read_text()
    new = current(text)
    if "--check" in args:
        if new != text:
            print("stale: run python paper/compact_view.py")
            return 1
        return 0
    TEX.write_text(new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
