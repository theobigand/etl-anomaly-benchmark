"""Export the precision-recall curves behind paper/figures/pr_curves.png as plain data.

Same datasets, seed and detectors as experiments/run_curves.py (it calls its scores_for); the only
change is that the curve points are written to JSON so the slide can draw them natively.
Nothing is retuned.

    python slides/art/tooling/export_pr_curves.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments"))

import numpy as np  # noqa: E402
from run_curves import scores_for  # noqa: E402
from sklearn.metrics import average_precision_score, precision_recall_curve  # noqa: E402

from etl_benchmark import config  # noqa: E402

OUT = ROOT / "slides" / "art" / "data" / "pr_curves.json"


def downsample(points, step=0.0025):
    """Ascending-recall copy with the mean precision per recall bin of width `step`.

    `points` is sklearn's output order (recall descending, ending with the sentinel recall 0,
    precision 1). The sentinel is kept as the first point. The step curves have up to 100k vertices
    (credit_card); at slide size a bin is under a pixel.
    """
    asc = list(reversed(points))
    sentinel, rest = asc[0], asc[1:]
    bins: dict[int, list[float]] = {}
    for rec, prec in rest:
        bins.setdefault(int(rec / step), []).append(prec)
    out = [list(sentinel)]
    for k in sorted(bins):
        vals = bins[k]
        out.append([round(min(1.0, (k + 0.5) * step), 4), round(sum(vals) / len(vals), 4)])
    return out


def main() -> None:
    out = {"seed": config.RANDOM_SEED, "datasets": {}}
    for name in ["credit_card", "water_quality", "cardio", "synthetic"]:
        data = scores_for(name, config.RANDOM_SEED)
        methods = {}
        for method, s in data["scores"].items():
            prec, rec, _ = precision_recall_curve(data["y"], s)
            ap = float(average_precision_score(data["y"], s))
            pts = downsample(np.round(np.column_stack([rec, prec]), 4).tolist())
            methods[method] = {"ap": ap, "points": pts}
        out["datasets"][name] = {"base_rate": round(data["base_rate"], 4), "methods": methods}
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
