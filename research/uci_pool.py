"""Choose relevant datasets from the UCI catalogue for the benchmark pool (issue 66).

A dataset enters the pool only if its metadata makes it usable (tabular, a sensible size, a
download URL, a classification or regression task), its own page states an open licence, and
its identity matches the catalogue. Every dataset also gets strata tags (size, dimension,
missing values, mixed types, time order, domain) so that the benchmark and the tests can draw
from specific categories. Nothing is redistributed; only metadata and checksums are recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "src")]

import dataset_registry as dr  # noqa: E402

API = "https://archive.ics.uci.edu/api"
ACCEPTED = {"CC BY 4.0", "CC0 1.0"}
EXCLUDED_MODALITIES = {"Image", "Text", "Sequential"}
TASKS = {"Classification", "Regression"}
MIN_ROWS, MAX_ROWS, MIN_FEATURES, MAX_FEATURES = 300, 1_000_000, 4, 300


def rejection(meta: dict[str, Any]) -> str | None:
    reasons = []
    rows, features = meta.get("num_instances"), meta.get("num_features")
    if rows is None or not MIN_ROWS <= rows <= MAX_ROWS:
        reasons.append(f"rows ({rows})")
    if features is None or not MIN_FEATURES <= features <= MAX_FEATURES:
        reasons.append(f"features ({features})")
    if EXCLUDED_MODALITIES & set(meta.get("characteristics") or []):
        reasons.append("modality")
    if not TASKS & set(meta.get("tasks") or []):
        reasons.append("task")
    if not meta.get("data_url"):
        reasons.append("download")
    return "; ".join(reasons) or None


def strata(meta: dict[str, Any]) -> dict[str, Any]:
    rows, features = meta["num_instances"], meta["num_features"]
    size = (
        "tiny"
        if rows < 2000
        else "small"
        if rows < 20_000
        else "medium"
        if rows < 200_000
        else "large"
    )
    dim = "low" if features <= 10 else "mid" if features <= 50 else "high"
    return {
        "size": size,
        "dim": dim,
        "missing": meta.get("has_missing_values") == "yes",
        "mixed_types": "Categorical" in (meta.get("feature_types") or []),
        "time": "Time-Series" in (meta.get("characteristics") or []),
        "domain": meta.get("area"),
    }


def select(catalogue, licences):
    chosen, rejected = [], []
    for meta in catalogue:
        reason = rejection(meta)
        if reason is None and licences.get(meta["uci_id"], {}).get("licence") not in ACCEPTED:
            reason = "licence not open or not stated on the page"
        (rejected.append((meta, reason)) if reason else chosen.append(meta))
    return chosen, rejected


def crawl(fetch: Callable[[str], str], sleep=time.sleep, delay: float = 0.3) -> dict[str, Any]:
    listing = json.loads(fetch(f"{API}/datasets/list"))["data"]
    datasets, failed = [], []
    for item in listing:
        try:
            datasets.append(json.loads(fetch(f"{API}/dataset?id={item['id']}"))["data"])
        except (OSError, ValueError, KeyError):
            failed.append(item["id"])
        sleep(delay)
    return {"datasets": datasets, "failed": failed}


def balance_report(chosen) -> dict[str, Any]:
    tags = [strata(m) for m in chosen]
    report: dict[str, Any] = {"total": len(chosen)}
    for key in ("size", "dim", "missing", "mixed_types", "time", "domain"):
        report[key] = dict(Counter(t[key] for t in tags))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, help="crawl the catalogue metadata to this file")
    parser.add_argument("--select", type=Path, help="survey file to filter")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    if args.survey:
        result = crawl(dr._text)
        with atomic_path(args.survey) as partial:
            partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
        print(f"surveyed {len(result['datasets'])} datasets, {len(result['failed'])} failed")
        return 0
    survey = json.loads(args.select.read_text())["datasets"]
    candidates = [m for m in survey if rejection(m) is None]
    licences = {}
    for meta in candidates:
        page = dr._text(meta["repository_url"])
        licences[meta["uci_id"]] = {**dr.uci_licence(page), "url": meta["repository_url"]}
        time.sleep(0.3)
    chosen, rejected = select(survey, licences)
    out = {
        "checked": time.strftime("%Y-%m-%d"),
        "chosen": [
            {**m, "licence": licences[m["uci_id"]]["licence"], "strata": strata(m)} for m in chosen
        ],
        "rejected": [{"uci_id": m["uci_id"], "name": m["name"], "reason": r} for m, r in rejected],
        "report": balance_report(chosen),
    }
    with atomic_path(args.output) as partial:
        partial.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"chosen {len(chosen)}, rejected {len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
