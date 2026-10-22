"""Find the pool datasets that carry a genuine time variable (pool_extension.md, study 5).

A column qualifies when it is readable as a date or a time and the rows are not all equal. The
scan only reports candidates: whether the row order is chronological is decided from the sorted
column, never assumed, and a dataset is kept for the chronological study only if it is labelled
and large enough.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uci_loader as ul  # noqa: E402

NAME = re.compile(r"(date|time|timestamp|datetime|year|month|day|hour|week)", re.I)
MIN_PARSED = 0.95


def candidate_columns(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Columns that can be ordered in time, with how they were read."""
    found = []
    for name in frame.columns:
        column = frame[name]
        if column.nunique(dropna=True) < 10:
            continue
        if not NAME.search(str(name)) and not pd.api.types.is_object_dtype(column):
            continue
        if pd.api.types.is_numeric_dtype(column):
            if NAME.search(str(name)):
                found.append(
                    {"column": str(name), "kind": "numeric", "distinct": int(column.nunique())}
                )
            continue
        parsed = pd.to_datetime(column, errors="coerce", format="mixed")
        if parsed.notna().mean() >= MIN_PARSED and parsed.nunique() >= 10:
            found.append(
                {"column": str(name), "kind": "datetime", "distinct": int(parsed.nunique())}
            )
    return found


def scan(curated: Path, pool: Path, data: Path) -> list[dict[str, Any]]:
    meta = {m["uci_id"]: m for m in json.loads(curated.read_text())["kept"]}
    rows = []
    for row in json.loads(pool.read_text())["rows"]:
        path = data / f"{row['uci_id']}.csv"
        try:
            frame = ul.read_table(path)
        except Exception as error:  # recorded
            rows.append({"uci_id": row["uci_id"], "error": repr(error)})
            continue
        # variables declared with a time role in the repository metadata count too
        declared = [
            v["name"] for v in meta[row["uci_id"]].get("variables") or [] if v.get("type") == "Date"
        ]
        cands = candidate_columns(frame)
        for name in declared:
            if name in frame.columns and all(c["column"] != name for c in cands):
                cands.append(
                    {"column": name, "kind": "declared", "distinct": int(frame[name].nunique())}
                )
        rows.append(
            {
                "uci_id": row["uci_id"],
                "name": row["name"],
                "labelled": "labelled" in row["roles"],
                "rows": int(len(frame)),
                "candidates": cands,
            }
        )
    return rows


if __name__ == "__main__":
    root = HERE.parent
    registry = root / "verification" / "evidence" / "dataset_registry"
    result = scan(registry / "uci_curated.json", registry / "uci_pool.json", root / "data" / "pool")
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n")
    with_time = [r for r in result if r.get("candidates")]
    print(len(result), "datasets,", len(with_time), "with a time candidate")
    for r in with_time:
        print(
            r["uci_id"], r["name"], r["labelled"], r["rows"], [c["column"] for c in r["candidates"]]
        )
