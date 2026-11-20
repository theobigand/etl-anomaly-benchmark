"""Typed injection on mixed-schema and small tables (issue 77, verification/typed_mixed.md).

One job is one catalog table. The carrier keeps numeric and categorical columns, the faults of
``injection_mixed`` are drawn with statistics from the training partition only, the encoder is
fitted on the training partition, and each detector is scored per fault type on the test
partition. Test counts are pooled over seeds so that small tables are measurable.
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

import injection as inj  # noqa: E402
import injection_mixed as im  # noqa: E402
import pool_typed as pt  # noqa: E402
import typed_benchmark as tb  # noqa: E402
import uci_loader as ul  # noqa: E402
from deep_support import build, capped  # noqa: E402

from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality import TemporalDriftDetector  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

PROTOCOL = "typed-mixed-v1"
SEEDS_A = (42, 1, 2, 3, 4)
SEEDS_B = (42, *range(1, 20))


def seeds_for(n_rows: int) -> tuple[int, ...]:
    return SEEDS_A if im.tier(n_rows) == "A" else SEEDS_B


def load_carrier(job: dict[str, Any], seed: int = 0):
    """Feature table (normal-class rows of a labelled set) as a mixed carrier."""
    if job["source"] == "uci":
        frame = ul.read_table(Path(job["path"]))
        try:
            features, labels, _ = ul.derive_labels(frame, job["meta"])
            features, normal_only = features[labels == 0], True
        except ul.NoLabels:
            features, _ = ul.split_columns(frame, job["meta"])
            normal_only = False
    else:
        data = np.load(job["path"])
        keep = np.asarray(data["y"]) == 0
        features, normal_only = pd.DataFrame(data["X"]).add_prefix("f")[keep], True
    table, kinds, report = im.prepare_mixed(features.reset_index(drop=True), seed=seed)
    report.update(
        source_rows=len(features), normal_class_only=normal_only, tier=im.tier(len(table))
    )
    return table, kinds, report


def eligibility(job: dict[str, Any]) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    row = {"id": job["id"], "name": job["name"], "source": job["source"]}
    try:
        table, kinds, report = load_carrier(job)
    except inj.NotEligible as reason:
        return {**row, "eligible": False, "reason": str(reason)}
    except Exception as error:  # recorded, not hidden
        return {**row, "eligible": False, "reason": f"load failed: {error!r}"}
    return {
        **row,
        "eligible": True,
        "rows": len(table),
        "tier": im.tier(len(table)),
        "types": im.supported_types(kinds, table),
        "kinds": {k: sum(v == k for v in kinds.values()) for k in ("num", "cat")},
        "report": report,
    }


def _seed_layout(clean: pd.DataFrame, kinds: dict[str, str], seed: int):
    """The injected table with training-only statistics, checked against the schema layout."""
    cols = list(clean.columns)
    layout = im.inject_mixed(clean, kinds, seed)
    train, _val, _test = tb.split(layout, seed)
    reference = train.loc[train["anomaly_type"] == "clean", cols].reset_index(drop=True)
    frame = im.inject_mixed(clean, kinds, seed, reference=reference)
    keys = ["group_id", "anomaly_type"]
    if not frame[keys].equals(layout[keys]):
        raise AssertionError("the reference changed the group or type layout")
    return frame


def evaluate_seed(clean, kinds, seed, names):
    frame = _seed_layout(clean, kinds, seed)
    cols = list(clean.columns)
    train, _val, test = tb.split(frame, seed)
    contamination = float(train["anomaly"].mean())
    encoder = im.Encoder.fit(train[cols], kinds)
    x_train = encoder.transform(train[cols]).assign(t=train["t"].to_numpy())
    x_test = encoder.transform(test[cols]).assign(t=test["t"].to_numpy())
    numeric = [c for c in x_train.columns if c != "t"]
    types = test["anomaly_type"]
    row_types = types.to_numpy()
    out: dict[str, Any] = {"counts": {t: int((types == t).sum()) for t in im.ANOMALY_TYPES}}
    out["clean"] = int((types == "clean").sum())
    hits: dict[str, dict[str, int]] = {}
    false_alarms: dict[str, int] = {}
    for name in [*names, "transform_dedup"]:
        if name == "transform_dedup":
            raw = pd.concat([test[cols].astype(str), test[["t"]]], axis=1)
            flags = raw.duplicated(keep=False)
        elif name == "drift":
            flags = detect(
                x_test, TemporalDriftDetector(time_column="t", columns=numeric), fit_df=x_train
            ).flags
        else:
            flags = detect(
                x_test, build(name, contamination, seed), fit_df=capped(x_train, name, seed)
            ).flags
        flagged = np.asarray(flags, dtype=bool)
        false_alarms[name] = int(flagged[row_types == "clean"].sum())
        hits[name] = {t: int(flagged[row_types == t].sum()) for t in im.ANOMALY_TYPES}
    out.update(hits=hits, false_alarms=false_alarms)
    return out


def run_one(job: dict[str, Any], names: list[str] | None = None) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    names = names or tb.DETECTORS
    clean, kinds, report = load_carrier(job)
    seeds = seeds_for(len(clean))
    runs = [evaluate_seed(clean, kinds, seed, names) for seed in seeds]
    types = im.supported_types(kinds, clean)
    methods = [*names, "transform_dedup"]
    counts = {t: sum(r["counts"][t] for r in runs) for t in types}
    clean_n = sum(r["clean"] for r in runs)
    recall = {
        m: {
            t: (sum(r["hits"][m][t] for r in runs) / counts[t] if counts[t] else None)
            for t in types
        }
        for m in methods
    }
    fpr = {m: sum(r["false_alarms"][m] for r in runs) / clean_n for m in methods}
    return {
        "protocol": PROTOCOL,
        "id": job["id"],
        "name": job["name"],
        "tier": im.tier(len(clean)),
        "carrier": report,
        "seeds": list(seeds),
        "types": types,
        "test_counts": counts,
        "clean_test_rows": clean_n,
        "recall_pooled": recall,
        "fpr_pooled": fpr,
    }


REGISTRY = ("verification", "evidence", "dataset_registry")
NUMERIC_ELIGIBILITY = ("verification", "evidence", "pool_extension", "typed", "eligibility.json")
POOL_DIR, ADBENCH_DIR = ("data", "pool"), ("data", "adbench")
ELIGIBILITY_FILE = "eligibility.json"

PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument("command", choices=("eligibility", "run"))
PARSER.add_argument("--output", type=Path, required=True)
PARSER.add_argument("--workers", type=int, default=4)
PARSER.add_argument("--methods", choices=("classical", "deep"), default="classical")
PARSER.add_argument("--resume", action="store_true")
PARSER.add_argument("--only", nargs="*", help="dataset ids, for a quick check")
PARSER.add_argument("--scope", choices=("ineligible", "all"), default="ineligible")


def selected_jobs(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Catalog tables to process: the ones the numeric protocol rejected, or all of them."""
    numeric = {
        r["id"]: r["eligible"] for r in json.loads(ROOT.joinpath(*NUMERIC_ELIGIBILITY).read_text())
    }
    jobs = pt.jobs(ROOT.joinpath(*REGISTRY), ROOT.joinpath(*POOL_DIR), ROOT.joinpath(*ADBENCH_DIR))
    return [
        j
        for j in jobs
        if (not args.only or j["id"] in args.only) and (args.scope == "all" or not numeric[j["id"]])
    ]


def stem(job: dict[str, Any]) -> str:
    return job["id"].replace(":", "_")


def main(argv: list[str] | None = None) -> int:
    args = PARSER.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    todo = selected_jobs(args)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "eligibility":
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            rows = list(pool.map(eligibility, todo))
        with atomic_path(args.output / ELIGIBILITY_FILE) as partial:
            partial.write_text(json.dumps(rows, indent=1) + "\n")
        print(sum(r["eligible"] for r in rows), "eligible of", len(rows))
        return 0
    recorded = json.loads((args.output / ELIGIBILITY_FILE).read_text())
    eligible = {r["id"] for r in recorded if r["eligible"]}
    todo = [j for j in todo if j["id"] in eligible]
    names = list(DEEP_NAMES) if args.methods == "deep" else None
    folder = args.output / args.methods
    folder.mkdir(exist_ok=True)
    if args.resume:
        todo = [j for j in todo if not (folder / f"{stem(j)}.json").exists()]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, result in enumerate(pool.map(bind(run_one, names=names), todo)):
            job = todo[n]
            with atomic_path(folder / f"{stem(job)}.json") as partial:
                partial.write_text(json.dumps(result, sort_keys=True) + "\n")
            print(job["id"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
