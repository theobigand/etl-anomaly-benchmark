"""Detection rate versus injection severity, on the synthetic dataset.

The synthetic magnitudes are a design choice and a stated threat to
validity. This sweep turns the choice into a curve: for a range of
``--severities`` (1.0 is the reference dataset) it regenerates the data,
runs the same held-out per-type evaluation as
``run_synthetic_benchmark.py``, and plots per-type recall against
severity for every method.

    python experiments/run_severity.py
    python experiments/run_severity.py --severities 0.5 1 2 4 --seeds 42
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_synthetic_benchmark import _prepare, evaluate  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.logging_setup import setup_logging  # noqa: E402
from etl_benchmark.synthetic import make_synthetic  # noqa: E402

log = logging.getLogger(__name__)

PAPER_FIGURE = config.PROJECT_ROOT / "paper" / "figures" / "severity_curves.png"
# the three types whose injection has a magnitude to scale
MAGNITUDE_TYPES = ["univariate_outlier", "multivariate_outlier", "temporal_drift"]


def run(severities: list[float], seeds: list[int], rows: int | None) -> pd.DataFrame:
    """Return a long frame: severity, method, anomaly_type, recall (seed-mean)."""
    records = []
    for sev in severities:
        per_seed = []
        for s in seeds:
            kw = {"n_rows": rows} if rows else {}
            df = _prepare(make_synthetic(seed=s, severity=sev, **kw))
            per_seed.append(evaluate(df, s)["recall"])
            log.info("severity %.2f seed %d done", sev, s)
        mean_recall = pd.concat(per_seed).groupby(level=0, sort=False).mean()
        for method, row in mean_recall.iterrows():
            for atype, recall in row.items():
                records.append(
                    {"severity": sev, "method": method, "anomaly_type": atype, "recall": recall}
                )
    return pd.DataFrame(records)


def render(curves: pd.DataFrame, path: Path) -> Path:
    methods = [m for m in curves["method"].unique() if m != "transform_dedup"]
    fig, axes = plt.subplots(1, len(MAGNITUDE_TYPES), figsize=(4.2 * len(MAGNITUDE_TYPES), 3.6))
    cmap = plt.get_cmap("tab10")

    for ax, atype in zip(axes, MAGNITUDE_TYPES, strict=True):
        sub = curves[curves["anomaly_type"] == atype]
        for i, method in enumerate(methods):
            line = sub[sub["method"] == method].sort_values("severity")
            ax.plot(
                line["severity"],
                line["recall"],
                marker="o",
                markersize=3,
                linewidth=1.4,
                color=cmap(i % 10),
                label=method,
            )
        ax.set_title(atype.replace("_", " "))
        ax.set_xlabel("injection severity (1.0 = reference)")
        ax.set_ylim(-0.03, 1.03)
        ax.axvline(1.0, color="0.7", linewidth=0.8, linestyle="--")
    axes[0].set_ylabel("recall on that type")
    axes[-1].legend(fontsize=7, loc="lower right")
    fig.suptitle("Detection rate by anomaly type versus injection severity (synthetic)")
    fig.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--severities", type=float, nargs="+", default=[0.5, 1.0, 2.0, 3.0, 5.0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 1, 2])
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--figure", type=Path, default=PAPER_FIGURE)
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    curves = run(args.severities, args.seeds, args.rows)

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    curves.to_csv(config.RESULTS_DIR / f"severity_{stamp}.csv", index=False)
    figure = render(curves, args.figure)

    wide = curves[curves["anomaly_type"].isin(MAGNITUDE_TYPES)].pivot_table(
        index=["anomaly_type", "method"], columns="severity", values="recall"
    )
    print("\n" + wide.round(3).to_string())
    log.info("figure -> %s", figure)


if __name__ == "__main__":
    main()
