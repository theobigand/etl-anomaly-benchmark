"""Summary of the batch-level pipeline fault pilot (protocol pipeline_batch_faults.md, B1 to B4).

Reads one result file per source, reports the recall at the label-free alert budget by detector and
mechanism, and checks the four preregistered hypotheses. The unit of analysis is the source; with
fewer than 15 sources every statement is descriptive.
"""

# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE)]

import pipeline_batch as pb  # noqa: E402

CLEAR = ("partial_load", "duplicate_load", "stale_batch", "null_spike", "schema_drop")
HARD = ("silent_corruption", "distribution_shift")
DESCRIPTIVE_BELOW = 15


def load(directory: Path, extra: Path | None = None) -> list[dict[str, Any]]:
    """Result files of one run; ``extra`` merges the detectors of a second run of the same sources."""
    sources = [json.loads(p.read_text()) for p in sorted(directory.glob("uci_*.json"))]
    if extra is None:
        return sources
    other = {p.stem: json.loads(p.read_text()) for p in extra.glob("uci_*.json")}
    for source in sources:
        match = other.get(source["id"].replace(":", "_"))
        if match is None:
            continue
        for arm, data in source["arms"].items():
            added = match["arms"][arm]
            data["results"].update(
                {d: r for d, r in added["results"].items() if d not in data["results"]}
            )
            data["detectors"] = [d for d in pb.DETECTORS if d in data["results"]]
    return sources


def recall(
    arm: dict[str, Any], detector: str, mechanism: str, levels: tuple[str, ...]
) -> float | None:
    by_level = arm["results"].get(detector, {}).get(mechanism, {})
    values = [by_level[lv]["recall"] for lv in levels if lv in by_level]
    return float(np.mean(values)) if values else None


def family_best(arm: dict[str, Any], mechanism: str, levels: tuple[str, ...]) -> dict[str, float]:
    """Best recall of each family (rules, statistical, learned, floor) for one mechanism."""
    best: dict[str, float] = {}
    for detector in arm["detectors"]:
        r = recall(arm, detector, mechanism, levels)
        if r is not None:
            family = pb.FAMILY[detector]
            best[family] = max(best.get(family, -1.0), r)
    return best


def summarise(sources: list[dict[str, Any]]) -> dict[str, Any]:
    clean = {s["id"]: s["arms"]["clean_reference"] for s in sources}
    dirty = {s["id"]: s["arms"]["contaminated_reference"] for s in sources}
    detectors = sorted({d for a in clean.values() for d in a["detectors"]}, key=pb.DETECTORS.index)
    table: dict[str, dict[str, dict[str, float]]] = {}
    for d in detectors:
        table[d] = {}
        for m in pb.MECHANISMS:
            row = {}
            for label, lv in (("low", ("0",)), ("medium", ("1",)), ("high", ("2",))):
                vals = [recall(a, d, m, lv) for a in clean.values() if d in a["detectors"]]
                vals = [v for v in vals if v is not None]
                if vals:
                    row[label] = float(np.median(vals))
            table[d][m] = row
    # B1: constraint_rules recall >= 0.9 on the clear mechanisms at medium and high severity
    b1 = {m: [recall(a, "constraint_rules", m, ("1", "2")) for a in clean.values()] for m in CLEAR}
    b1_share = {m: float(np.mean([v >= 0.9 for v in vals])) for m, vals in b1.items()}
    # B2: rules versus the best learned detector on hard mechanisms (low severity for shift)
    b2: dict[str, Any] = {}
    for m, lv in (("silent_corruption", ("0", "1", "2")), ("distribution_shift", ("0",))):
        gaps = []
        for a in clean.values():
            best = max(
                (recall(a, d, m, lv) for d in (*pb.LEARNED, *pb.COMPACT) if d in a["detectors"]),
                default=None,
            )
            rule = recall(a, "constraint_rules", m, lv)
            if best is not None and rule is not None:
                gaps.append(best - rule)
        b2[m] = {
            "sources": len(gaps),
            "median_gap": float(np.median(gaps)),
            "share_ge_0.2": float(np.mean([g >= 0.2 for g in gaps])),
        }
    # B5: compact versus full profile on the gross mechanisms (best learned variant of each)
    b5: dict[str, Any] = {}
    for m in ("partial_load", "duplicate_load", "null_spike", "schema_drop", "unit_change"):
        gaps = []
        for a in clean.values():
            full = [recall(a, d, m, ("0", "1", "2")) for d in pb.LEARNED if d in a["detectors"]]
            comp = [recall(a, d, m, ("0", "1", "2")) for d in pb.COMPACT if d in a["detectors"]]
            if full and comp:
                gaps.append(max(comp) - max(full))
        if gaps:
            b5[m] = {
                "sources": len(gaps),
                "median_gain": float(np.median(gaps)),
                "share_gain_positive": float(np.mean([g > 0 for g in gaps])),
            }
    # B3: the family with the best median recall differs between mechanisms
    winners = {}
    for m in pb.MECHANISMS:
        meds = {}
        for fam in ("rules", "statistical", "learned"):
            vals = [family_best(a, m, ("0", "1", "2")).get(fam) for a in clean.values()]
            vals = [v for v in vals if v is not None]
            meds[fam] = float(np.median(vals)) if vals else None
        winners[m] = max((k for k, v in meds.items() if v is not None), key=lambda k: meds[k])
    # B4: recall change with a contaminated reference, by family
    b4: dict[str, float] = {}
    for fam in ("rules", "statistical", "learned"):
        deltas = []
        for i, a in clean.items():
            for m in pb.MECHANISMS:
                c, d = (
                    family_best(a, m, ("0", "1", "2")).get(fam),
                    family_best(dirty[i], m, ("0", "1", "2")).get(fam),
                )
                if c is not None and d is not None:
                    deltas.append(d - c)
        b4[fam] = float(np.mean(deltas)) if deltas else float("nan")
    false_alerts = {
        d: float(
            np.median(
                [
                    np.mean(
                        [
                            lv["false_alert_rate"]
                            for m in a["results"][d].values()
                            for lv in m.values()
                        ]
                    )
                    for a in clean.values()
                    if d in a["detectors"]
                ]
            )
        )
        for d in detectors
    }
    return {
        "sources": sorted(clean),
        "descriptive_only": len(clean) < DESCRIPTIVE_BELOW,
        "median_recall_at_budget": table,
        "median_false_alert_rate": false_alerts,
        "B1_share_of_sources_recall_ge_0.9": b1_share,
        "B2_rules_vs_best_learned": b2,
        "B3_best_family_by_mechanism": winners,
        "B3_holds": len(set(winners.values())) > 1,
        "B4_mean_recall_change_contaminated_minus_clean": b4,
        "B5_compact_minus_full_profile_best_learned": b5,
    }


def render(summary: dict[str, Any]) -> str:
    lines = [
        "# Batch-level pipeline faults: pilot results",
        "",
        f"Sources: {len(summary['sources'])} ({', '.join(summary['sources'])}). "
        + (
            "Descriptive only (fewer than 15 sources): no ranking claim."
            if summary["descriptive_only"]
            else ""
        ),
        "",
        "Median recall at the label-free 5 % alert budget, over sources, averaged over severities (clean reference).",
        "",
        "| Detector | " + " | ".join(pb.MECHANISMS) + " | false alerts |",
        "|---|" + "---:|" * (len(pb.MECHANISMS) + 1),
    ]
    for d, rows in summary["median_recall_at_budget"].items():
        cells = [
            f"{np.mean(list(rows[m].values())):.2f}" if rows[m] else "-" for m in pb.MECHANISMS
        ]
        lines.append(
            f"| {d} | " + " | ".join(cells) + f" | {summary['median_false_alert_rate'][d]:.2f} |"
        )
    lines += ["", "Hypotheses (exploratory):", ""]
    lines.append(
        "- B1 share of sources with `constraint_rules` recall >= 0.9 (medium and high): "
        + ", ".join(f"{m} {v:.0%}" for m, v in summary["B1_share_of_sources_recall_ge_0.9"].items())
    )
    for m, v in summary["B2_rules_vs_best_learned"].items():
        lines.append(
            f"- B2 {m}: best learned minus rules, median {v['median_gap']:+.2f}; gap >= 0.2 in {v['share_ge_0.2']:.0%} of {v['sources']} sources"
        )
    lines.append(
        f"- B3 best family per mechanism: {summary['B3_best_family_by_mechanism']}; differs between mechanisms: {summary['B3_holds']}"
    )
    lines.append(
        "- B4 mean recall change with a contaminated reference: "
        + ", ".join(
            f"{k} {v:+.3f}"
            for k, v in summary["B4_mean_recall_change_contaminated_minus_clean"].items()
        )
    )
    for m, v in summary["B5_compact_minus_full_profile_best_learned"].items():
        lines.append(
            f"- B5 {m}: best compact minus best full-profile learned detector, median {v['median_gain']:+.2f}; positive in {v['share_gain_positive']:.0%} of {v['sources']} sources"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    default = ROOT / "verification/evidence/pipeline_batch/pilot"
    parser.add_argument("--results", type=Path, default=default)
    parser.add_argument("--compact-results", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = summarise(load(args.results, args.compact_results))
    (args.results / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (args.results / "summary.md").write_text(render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
