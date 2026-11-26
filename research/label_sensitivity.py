"""Sensitivity of the labelled-pool ranking to the labelling rule (issue 83).

Protocol: verification/validity_study.md. The 64 UCI problems take their anomalies from a class of
the target, not from experts. This module derives the labels of the alternative rules fixed in the
protocol, runs the detectors of the registry on them and archives one file per problem and rule.
The baseline rule R0 is the archived one (``uci_loader.derive_labels``) and is not rerun.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from functools import partial as bind
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import labelled_benchmark as lb  # noqa: E402
import normalise as nm  # noqa: E402
import uci_loader as ul  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

SEEDS = (42, 1, 2)
#: rule -> (which class is the anomaly, target rate or None for the natural rate)
RULES: dict[str, tuple[str, float | None]] = {
    "R1": ("rarest", 0.02),
    "R2": ("rarest", 0.05),
    "R3": ("rarest", None),
    "R4": ("second_rarest", 0.10),
    "R5": ("all_minority", 0.10),
}


def derive_rule(
    frame: pd.DataFrame, meta: dict[str, Any], rule: str
) -> tuple[pd.DataFrame, np.ndarray, dict[str, Any]]:
    """Features, labels and facts of one problem under an alternative rule.

    ``rarest``: the rarest class is the anomaly. ``second_rarest``: the second rarest class is
    the anomaly and the rarest one is removed. ``all_minority``: every class but the most frequent
    is the anomaly. The anomaly share is downsampled to the target rate with seed 0 when above it;
    ``None`` keeps the natural share. Raises ``NoLabels`` when the rule has no valid anomaly set.
    """
    which, target_rate = RULES[rule]
    if "Classification" not in (meta.get("tasks") or []):
        raise ul.NoLabels("not a classification task")
    features, target = ul.split_columns(frame, meta)
    known = target.notna().to_numpy()
    features, target = features[known].reset_index(drop=True), target[known].reset_index(drop=True)
    text = target.astype(str)
    counts = text.value_counts()
    if len(counts) < 2 or (which != "rarest" and len(counts) < 3):
        raise ul.NoLabels(f"{len(counts)} classes: rule {rule} needs more")
    ordered = list(counts.index)  # most frequent first
    if which == "rarest":
        is_anomaly, keep = (text == ordered[-1]).to_numpy(), np.ones(len(text), dtype=bool)
        label = ordered[-1]
    elif which == "second_rarest":
        is_anomaly = (text == ordered[-2]).to_numpy()
        keep = (text != ordered[-1]).to_numpy()
        label = ordered[-2]
    else:
        is_anomaly = (text != ordered[0]).to_numpy()
        keep = np.ones(len(text), dtype=bool)
        label = "all but " + ordered[0]
    n_anomaly = int((is_anomaly & keep).sum())
    if n_anomaly < ul.MIN_ANOMALIES:
        raise ul.NoLabels(f"{n_anomaly} anomalies under rule {rule} (at least {ul.MIN_ANOMALIES})")
    pool = keep & ~is_anomaly
    natural = n_anomaly / int(keep.sum())
    info: dict[str, Any] = {"rule": rule, "anomaly_class": label, "natural_rate": float(natural)}
    selected = keep.copy()
    if target_rate is not None and natural > target_rate:
        k = round(int(pool.sum()) * target_rate / (1 - target_rate))
        chosen = np.random.default_rng(ul.SEED).choice(
            np.flatnonzero(is_anomaly & keep), k, replace=False
        )
        selected = pool.copy()
        selected[chosen] = True
        info["kind"] = "downsampled"
    else:
        info["kind"] = "natural"
    labels = is_anomaly[selected].astype(int)
    info.update(rows=int(selected.sum()), anomalies=int(labels.sum()))
    return features[selected].reset_index(drop=True), labels, info


def run_job(job: dict[str, Any], methods: list[str] | None = None) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    head = {"problem": job["problem"], "rule": job["rule"]}
    try:
        features, labels, info = derive_rule(
            ul.read_table(Path(job["path"])), job["meta"], job["rule"]
        )
    except ul.NoLabels as reason:
        return {**head, "not_applicable": str(reason)}
    try:
        x, y, report = nm.clean(features, labels)
        result = lb.run_problem(x, y, seeds=SEEDS, methods=methods)
    except Exception as error:  # recorded, never dropped silently
        return {**head, "failed": repr(error)}
    return {
        **head,
        "name": job["meta"]["name"],
        "prevalence": float(y.mean()),
        "rows": int(len(y)),
        "features": int(x.shape[1]),
        "report": {**report, **info},
        **result,
    }


def jobs(registry: Path, pool: Path, rules: list[str]) -> list[dict[str, Any]]:
    curated = {
        m["uci_id"]: m for m in json.loads((registry / "uci_curated.json").read_text())["kept"]
    }
    rows = json.loads((registry / "uci_pool.json").read_text())["rows"]
    return [
        {
            "problem": f"uci:{row['uci_id']}",
            "rule": rule,
            "meta": curated[row["uci_id"]],
            "path": str(pool / f"{row['uci_id']}.csv"),
        }
        for row in rows
        if "labelled" in row["roles"]
        for rule in rules
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    registry = ROOT / "verification" / "evidence" / "dataset_registry"
    parser.add_argument("--registry", type=Path, default=registry)
    parser.add_argument("--pool", type=Path, default=ROOT / "data" / "pool")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rules", nargs="*", default=list(RULES))
    parser.add_argument("--only", nargs="*", help="problem ids, for a quick check")
    parser.add_argument("--methods", choices=("classical", "deep"), default="classical")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    methods = list(DEEP_NAMES) if args.methods == "deep" else list(lb.METHODS)
    todo = [
        j
        for j in jobs(args.registry, args.pool, args.rules)
        if not args.only or j["problem"] in args.only
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    todo = [
        j
        for j in todo
        if not (args.output / f"{j['problem'].replace(':', '_')}_{j['rule']}.json").exists()
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as workers:
        for result in workers.map(bind(run_job, methods=methods), todo):
            stem = f"{result['problem'].replace(':', '_')}_{result['rule']}"
            with atomic_path(args.output / f"{stem}.json") as partial:
                partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
            state = result.get("failed") or result.get("not_applicable") or "ok"
            print(result["problem"], result["rule"], state, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
