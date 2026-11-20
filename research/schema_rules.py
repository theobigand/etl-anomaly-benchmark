"""Schema-rule baseline on the mixed-schema faults (protocol verification/schema_rules.md).

Constraints (allowed values, missing cells, far-out ranges, signs, near-functional dependencies
between categorical columns) are learned from the training partition of the raw columns and
evaluated on the very layouts of ``typed_mixed.py``, so its recalls pair with the archived ones.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import injection_mixed as im  # noqa: E402
import typed_benchmark as tb  # noqa: E402
import typed_mixed as tm  # noqa: E402

MIN_LEVEL_COUNT = im.MIN_LEVEL_COUNT
FENCE = 3.0
DEP_MIN_ROWS, DEP_PURITY, DEP_MAX_LEVELS = 5, 0.99, 50
DEP_MAX_COLUMNS = 80
CONSTRAINTS = ("domain", "missing", "range", "sign", "combination")


class SchemaRules:
    """Constraints fitted on raw training rows; ``violations`` returns one flag column each."""

    def fit(self, train: pd.DataFrame, kinds: dict[str, str]) -> SchemaRules:
        self.kinds = dict(kinds)
        self.levels: dict[str, set[str]] = {}
        self.complete: set[str] = set()
        self.fence: dict[str, tuple[float, float]] = {}
        self.nonnegative: set[str] = set()
        for name, kind in kinds.items():
            column = train[name]
            if column.isna().mean() <= im.MAX_MISSING_SHARE:
                self.complete.add(name)
            if kind == "cat":
                counts = column.dropna().astype(str).value_counts()
                self.levels[name] = set(counts[counts >= MIN_LEVEL_COUNT].index)
            else:
                values = column.dropna().to_numpy(dtype=float)
                q1, q3 = np.quantile(values, [0.25, 0.75])
                self.fence[name] = (q1 - FENCE * (q3 - q1), q3 + FENCE * (q3 - q1))
                if (values >= 0).all():
                    self.nonnegative.add(name)
        self.dependencies = self._dependencies(train)
        return self

    def _dependencies(self, train: pd.DataFrame) -> list[tuple[str, str, dict[str, str]]]:
        cats = [c for c, k in self.kinds.items() if k == "cat"]
        # pairs grow with the square of the columns: keep the 80 with the most levels (ties by name)
        cats = sorted(cats, key=lambda c: (-train[c].nunique(), c))[:DEP_MAX_COLUMNS]
        rules = []
        for a in cats:
            if not 2 <= train[a].nunique() <= DEP_MAX_LEVELS:
                continue
            for b in cats:
                if a == b or train[b].nunique() < 2:
                    continue
                table = train.groupby(a)[b].value_counts().rename("n").reset_index()
                total = table.groupby(a)["n"].sum()
                top = table.sort_values("n", ascending=False).drop_duplicates(a).set_index(a)
                mapping = {
                    str(level): str(top.loc[level, b])
                    for level in total.index
                    if total[level] >= DEP_MIN_ROWS and top.loc[level, "n"] / total[level] >= DEP_PURITY
                }
                if mapping:
                    rules.append((a, b, mapping))
        return rules

    def violations(self, frame: pd.DataFrame) -> pd.DataFrame:
        n = len(frame)
        out = {c: np.zeros(n, dtype=bool) for c in CONSTRAINTS}
        for name, kind in self.kinds.items():
            column = frame[name]
            out["missing"] |= (column.isna() & (name in self.complete)).to_numpy()
            if kind == "cat":
                known = column.astype(str).isin(self.levels[name]) | column.isna()
                out["domain"] |= ~known.to_numpy()
            else:
                values = column.to_numpy(dtype=float)
                low, high = self.fence[name]
                out["range"] |= (values < low) | (values > high)
                if name in self.nonnegative:
                    out["sign"] |= values < 0
        for a, b, mapping in self.dependencies:
            expected = frame[a].astype(str).map(mapping)
            out["combination"] |= (expected.notna() & (expected != frame[b].astype(str))).to_numpy()
        return pd.DataFrame(out, index=frame.index)

    def flags(self, frame: pd.DataFrame) -> np.ndarray:
        return self.violations(frame).any(axis=1).to_numpy()


def evaluate_seed(clean: pd.DataFrame, kinds: dict[str, str], seed: int) -> dict[str, Any]:
    frame = tm._seed_layout(clean, kinds, seed)
    cols = list(clean.columns)
    train, _val, test = tb.split(frame, seed)
    rules = SchemaRules().fit(train[cols], kinds)
    violated = rules.violations(test[cols])
    flagged = violated.any(axis=1).to_numpy()
    types = test["anomaly_type"].to_numpy()
    return {
        "counts": {t: int((types == t).sum()) for t in im.ANOMALY_TYPES},
        "clean": int((types == "clean").sum()),
        "hits": {t: int(flagged[types == t].sum()) for t in im.ANOMALY_TYPES},
        "false_alarms": int(flagged[types == "clean"].sum()),
        "by_constraint": {
            t: {c: int(violated[c].to_numpy()[types == t].sum()) for c in CONSTRAINTS}
            for t in im.ANOMALY_TYPES
        },
        "false_alarms_by_constraint": {
            c: int(violated[c].to_numpy()[types == "clean"].sum()) for c in CONSTRAINTS
        },
        "rules": {"dependencies": len(rules.dependencies)},
    }


def run_one(job: dict[str, Any]) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    clean, kinds, report = tm.load_carrier(job)
    seeds = tm.seeds_for(len(clean))
    runs = [evaluate_seed(clean, kinds, seed) for seed in seeds]
    types = im.supported_types(kinds, clean)
    counts = {t: sum(r["counts"][t] for r in runs) for t in types}
    clean_n = sum(r["clean"] for r in runs)
    return {
        "protocol": "schema-rules-v1",
        "id": job["id"],
        "name": job["name"],
        "tier": im.tier(len(clean)),
        "seeds": list(seeds),
        "types": types,
        "test_counts": counts,
        "clean_test_rows": clean_n,
        "recall_pooled": {
            t: (sum(r["hits"][t] for r in runs) / counts[t] if counts[t] else None) for t in types
        },
        "fpr_pooled": sum(r["false_alarms"] for r in runs) / clean_n,
        "share_by_constraint": {
            t: {c: sum(r["by_constraint"][t][c] for r in runs) for c in CONSTRAINTS} for t in types
        },
        "false_alarms_by_constraint": {
            c: sum(r["false_alarms_by_constraint"][c] for r in runs) for c in CONSTRAINTS
        },
        "dependency_rules": [r["rules"]["dependencies"] for r in runs],
        "carrier": {"rows": len(clean), "kinds": {k: sum(v == k for v in kinds.values()) for k in ("num", "cat")}},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    eligibility = ROOT / "verification/evidence/pool_extension_v2/typed_mixed/eligibility.json"
    eligible = {r["id"] for r in json.loads(eligibility.read_text()) if r["eligible"]}
    ns = argparse.Namespace(only=args.only, scope="ineligible")
    todo = [j for j in tm.selected_jobs(ns) if j["id"] in eligible]
    args.output.mkdir(parents=True, exist_ok=True)
    todo = [j for j in todo if not (args.output / f"{tm.stem(j)}.json").exists()]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for job, result in zip(todo, pool.map(run_one, todo), strict=True):
            with atomic_path(args.output / f"{tm.stem(job)}.json") as partial:
                partial.write_text(json.dumps(result, sort_keys=True) + "\n")
            print(job["id"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
