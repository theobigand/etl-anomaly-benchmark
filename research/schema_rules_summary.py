# ruff: noqa: E501
"""Compare the schema-rule baseline with the archived detectors (protocol verification/schema_rules.md).

Per table and fault type: the baseline recall against the best of the 17 archived detectors and
against the three registry rule detectors. Tables are grouped by independent source before any
interval or test (``coverage_matrix.source_key``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import coverage_matrix as cm  # noqa: E402
import paired_inference as pinf  # noqa: E402

EVIDENCE = ROOT / "verification" / "evidence"
RULE_DETECTORS = ("zscore", "iqr", "great_expectations")
TYPES = (
    "invalid_code", "cross_column_swap", "missing_value", "univariate_outlier",
    "multivariate_outlier", "invalid_format", "distribution_shift", "duplicate",
)  # fmt: skip


def archived(directory: Path, table: str) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for kind in ("classical", "deep"):
        path = directory / kind / f"{table}.json"
        if path.exists():
            out.update(json.loads(path.read_text())["recall_pooled"])
    out.pop("transform_dedup", None)
    return out


def summarise(rules_dir: Path, typed_dir: Path, draws: int = pinf.DRAWS) -> dict[str, Any]:
    rows = []
    for path in sorted(rules_dir.glob("*.json")):
        mine = json.loads(path.read_text())
        theirs = archived(typed_dir, path.stem)
        rows.append((path.stem, mine, theirs))
    out: dict[str, Any] = {"tables": len(rows), "types": {}}
    fpr = [m["fpr_pooled"] for _, m, _ in rows]
    out["S2"] = {
        "share_tables_fpr_at_most_0.05": float(np.mean([f <= 0.05 for f in fpr])),
        "median_fpr": float(np.median(fpr)),
    }
    for t in TYPES:
        names, base, best, rule_best, rule_med, others_med = [], [], [], [], [], []
        for stem, mine, theirs in rows:
            r = mine["recall_pooled"].get(t)
            values = {m: v[t] for m, v in theirs.items() if v.get(t) is not None}
            if r is None or not values:
                continue
            names.append(stem.replace("_", ":", 1))
            base.append(r)
            best.append(max(values.values()))
            rule_vals = [v for m, v in values.items() if m in RULE_DETECTORS]
            other_vals = [v for m, v in values.items() if m not in RULE_DETECTORS]
            rule_best.append(max(rule_vals))
            rule_med.append(float(np.median(rule_vals)))
            others_med.append(float(np.median(other_vals)))
        if not base:
            continue
        groups = {n: cm.source_key(n) for n in names}

        def by_source(v: list[float], names=names, groups=groups) -> np.ndarray:
            return np.array(
                list(pinf.group_means(dict(zip(names, v, strict=True)), groups).values())
            )

        out["types"][t] = {
            "tables": len(base),
            "sources": len(set(groups.values())),
            "baseline_median_recall": float(np.median(base)),
            "best_archived_median_recall": float(np.median(best)),
            "rule_detectors_median_recall": float(np.median(rule_med)),
            "other_detectors_median_recall": float(np.median(others_med)),
            "tables_baseline_at_least_best": float(
                np.mean(np.array(base) >= np.array(best) - 1e-12)
            ),
            "tables_baseline_at_least_0.9": float(np.mean(np.array(base) >= 0.9)),
            "baseline_minus_best": pinf.paired_effect(by_source(base), by_source(best), draws),
            "baseline_minus_rule_detectors": pinf.paired_effect(
                by_source(base), by_source(rule_med), draws
            ),
        }
    return out


def render(summary: dict[str, Any]) -> str:
    lines = [
        "# Schema-rule baseline against the archived detectors",
        "",
        f"Tables: {summary['tables']}. Median false-positive rate on clean rows "
        f"{summary['S2']['median_fpr']:.3f}; {summary['S2']['share_tables_fpr_at_most_0.05']:.0%} of tables at or below 0.05.",
        "",
        "| Fault type | Tables | Sources | Baseline | Best archived | Rule detectors | Other detectors | Baseline >= best (tables) | Baseline - best, source median [95 %] |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for t, v in summary["types"].items():
        e = v["baseline_minus_best"]
        lines.append(
            f"| {t} | {v['tables']} | {v['sources']} | {v['baseline_median_recall']:.2f} | {v['best_archived_median_recall']:.2f} "
            f"| {v['rule_detectors_median_recall']:.2f} | {v['other_detectors_median_recall']:.2f} | {v['tables_baseline_at_least_best']:.0%} "
            f"| {e['median_difference']:+.2f} [{e['ci_low']:+.2f}, {e['ci_high']:+.2f}] |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    out = EVIDENCE / "pool_extension_v3"
    summary = summarise(out / "schema_rules", EVIDENCE / "pool_extension_v2" / "typed_mixed")
    (out / "schema_rules_summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n"
    )
    (out / "schema_rules_summary.md").write_text(render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
