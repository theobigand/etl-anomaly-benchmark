"""Paired comparison of the train-only replay with the archived labelled-pool results (T062/T063).

Reads both archives, writes a JSON and a Markdown summary. Nothing archived is modified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "verification/evidence/labelled_pool/runs"
THRESHOLD = 0.05
DRAWS = 2000


def _mean_ap(metrics: dict, method: str) -> float | None:
    rows = metrics.get(method)
    return float(np.mean([r["pr_auc"] for r in rows])) if rows else None


def compare(new_dir: Path, old_dir: Path = ARCHIVE) -> dict:
    pairs: dict[str, dict[str, tuple[float, float, str]]] = {}
    failed, skipped_new = {}, {}
    for path in sorted(new_dir.glob("*.json")):
        new = json.loads(path.read_text())
        if "failed" in new:
            failed[new["problem"]] = new["failed"]
            continue
        old = json.loads((old_dir / path.name).read_text())
        for method in new["metrics"]:
            a, b = _mean_ap(old["metrics"], method), _mean_ap(new["metrics"], method)
            if a is not None and b is not None:
                pairs.setdefault(method, {})[new["problem"]] = (a, b, new["source"])
        if new["errors"]:
            skipped_new[new["problem"]] = new["errors"]
    rng = np.random.default_rng(0)
    methods = {}
    for method, items in sorted(pairs.items()):
        old_ap = np.array([v[0] for v in items.values()])
        new_ap = np.array([v[1] for v in items.values()])
        delta = new_ap - old_ap
        boots = [np.median(delta[rng.integers(0, len(delta), len(delta))]) for _ in range(DRAWS)]
        methods[method] = {
            "problems": len(delta),
            "median_archived_ap": float(np.median(old_ap)),
            "median_replay_ap": float(np.median(new_ap)),
            "median_delta": float(np.median(delta)),
            "median_delta_ci95": [
                float(np.percentile(boots, 2.5)),
                float(np.percentile(boots, 97.5)),
            ],
            "share_abs_delta_above_threshold": float(np.mean(np.abs(delta) > THRESHOLD)),
            "max_abs_delta": float(np.max(np.abs(delta))),
            "share_unchanged": float(np.mean(np.abs(delta) < 1e-9)),
            "mean_delta": float(np.mean(delta)),
            "by_source": {
                src: {
                    "problems": int(mask.sum()),
                    "share_unchanged": float(np.mean(np.abs(delta[mask]) < 1e-9)),
                    "mean_delta": float(np.mean(delta[mask])),
                    "mean_abs_delta": float(np.mean(np.abs(delta[mask]))),
                }
                for src in ("adbench", "uci")
                if (mask := np.array([v[2] == src for v in items.values()])).any()
            },
        }
    order_old = sorted(methods, key=lambda m: -methods[m]["median_archived_ap"])
    order_new = sorted(methods, key=lambda m: -methods[m]["median_replay_ap"])
    return {
        "protocol": "pool-train-only-replay-v1",
        "threshold": THRESHOLD,
        "bootstrap_draws": DRAWS,
        "methods": methods,
        "ranking_archived": order_old,
        "ranking_replay": order_new,
        "failed_problems": failed,
        "problems_with_errors": skipped_new,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    args = parser.parse_args(argv)
    result = compare(args.new, args.archive)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = [
        "| detector | n | AP archived | AP replay | median delta [95% CI] "
        "| mean delta | unchanged | >0.05 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m, r in result["methods"].items():
        lo, hi = r["median_delta_ci95"]
        share = r["share_abs_delta_above_threshold"]
        lines.append(
            f"| {m} | {r['problems']} | {r['median_archived_ap']:.3f} "
            f"| {r['median_replay_ap']:.3f} | {r['median_delta']:+.3f} "
            f"[{lo:+.3f}, {hi:+.3f}] | {r['mean_delta']:+.3f} "
            f"| {r['share_unchanged']:.2f} | {share:.2f} |"
        )
    args.output.with_suffix(".md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
