"""Diagnostic: do invalid-format rows in the training split mask the z-score on univariate outliers?

The z-score detector fits its mean and standard deviation on the training split, which contains
the injected rows. A sentinel or a thousandfold scale error inflates the standard deviation and
hides moderate outliers. The diagnostic refits the same detector without the invalid rows.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import injection as inj
import pandas as pd
import typed_benchmark as tb

from etl_benchmark import config
from etl_benchmark.quality import ZScoreDetector


def masking(df: pd.DataFrame, cols: list[str], seed: int) -> dict[str, float]:
    train, _val, test = tb.split(df, seed)
    rows = test["anomaly_type"] == "univariate_outlier"
    out = {}
    for label, part in (
        ("with_invalid_in_train", train),
        ("without_invalid_in_train", train[train["anomaly_type"] != "invalid_format"]),
    ):
        detector = ZScoreDetector(threshold=config.ZSCORE_THRESHOLD).fit(part[cols])
        out[label] = float(detector.predict(test[cols])[rows].mean())
    return out


def main(argv: list[str] | None = None) -> int:
    import typed_run as tr

    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True, help="typed_run output, for the ids")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    registry = root / "verification" / "evidence" / "dataset_registry"
    meta = {m["uci_id"]: m for m in json.loads((registry / "uci_curated.json").read_text())["kept"]}
    rows = []
    for path in sorted(args.runs.glob("*.json")):
        uci_id = json.loads(path.read_text())["uci_id"]
        carrier, _ = tr.load_carrier(meta[uci_id], root / "data" / "pool" / f"{uci_id}.csv", seed=0)
        df = inj.inject(carrier, seed=config.RANDOM_SEED)
        rows.append(
            {
                "uci_id": uci_id,
                "name": meta[uci_id]["name"],
                **masking(df, list(carrier.columns), config.RANDOM_SEED),
            }
        )
    args.output.write_text(json.dumps(rows, indent=1) + "\n")
    print(f"{len(rows)} datasets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
