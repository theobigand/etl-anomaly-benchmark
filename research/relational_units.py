"""Relational sources: declared keys, their verification and the provisional relational load unit.

The foreign keys come from the ``relations`` entries that the view builders recorded in
``experimental_views.json`` (child column, parent column, rows checked, natural orphans); nothing is
inferred from column names. ``verify`` recomputes those counts on the local tables, so a declaration
that does not reflect the data is reported. ``relational_cells`` is the provisional unit: logical
loads are consecutive child rows in file order (these tables have no load time), a share of the
test loads receive the referential-integrity fault of ``relational_faults``, and the orphan share of
a load is scored against the clean validation loads. The unit is not approved (section 8 of
``batch_pilot_addendum_proposal.md``) and is neither registered nor confirmatory.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import relational_faults as rf

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "verification/evidence/dataset_registry_v2/experimental_views.json"
#: relations the manifest records that are not modelled as a plain foreign key, with the reason
UNMODELLED = {
    ("fec_federal_campaign_finance_2024", "pas2.OTHER_ID"): (
        "polymorphic: holds committee and candidate identifiers; its type column is not declared"
    ),
}
PLAIN = re.compile(
    r"^\w+\.\w+$"
)  # table.column; anything else is a conditional or compound reference
LOADS, FAULT_SHARE, BUDGET = 40, 0.3, 0.05


def declared_keys(
    manifest: dict[str, Any],
) -> dict[str, list[tuple[rf.ForeignKey, dict[str, Any]]]]:
    """Per view, the plain foreign keys of its ``relations`` entries with the recorded counts."""
    out: dict[str, list[tuple[rf.ForeignKey, dict[str, Any]]]] = {}
    for view, entry in sorted(manifest.items()):
        for relation in entry.get("relations", []):
            if (view, relation["child"]) in UNMODELLED or not (
                PLAIN.match(relation["child"]) and PLAIN.match(relation["parent"])
            ):
                continue
            child, child_column = relation["child"].split(".")
            parent, parent_column = relation["parent"].split(".")
            fk = rf.ForeignKey(child, (child_column,), parent, (parent_column,))
            out.setdefault(view, []).append((fk, relation))
    return out


def read_tables(views: Path, view: str, names: set[str]) -> dict[str, pd.DataFrame]:
    """The named tables of a view as text; only an empty field is missing (``NA`` is a value)."""
    return {
        n: pd.read_csv(views / view / f"{n}.csv", dtype=str, keep_default_na=False, na_values=[""])
        for n in sorted(names)
    }


def verify(
    keys: list[tuple[rf.ForeignKey, dict[str, Any]]], tables: dict[str, pd.DataFrame]
) -> list[dict[str, Any]]:
    """Recompute asserted references and natural orphans of each declared key."""
    rows = []
    for fk, recorded in keys:
        found = rf.natural_orphans(fk, tables)
        rows.append(
            {
                "key": f"{fk.child}.{fk.columns[0]} -> {fk.parent}.{fk.parent_columns[0]}",
                "recorded": {"checked": recorded["checked"], "orphans": recorded["orphans"]},
                "found": {"checked": found["asserted"], "orphans": found["orphans"]},
                "match": (recorded["checked"], recorded["orphans"])
                == (found["asserted"], found["orphans"]),
            }
        )
    return rows


def relational_cells(
    tables: dict[str, pd.DataFrame], fk: rf.ForeignKey, level: int, seed: int
) -> dict[str, Any]:
    """Provisional unit: recall and clean false-alert rate of the orphan-share rule for one key.

    Loads are consecutive child rows. The threshold is the 95th percentile of the orphan shares of
    the clean validation loads (the registered label-free rule); a load alerts when its share is
    strictly above it. Natural orphans are part of every share and are never labelled faulty.
    """
    child = tables[fk.child]
    size = max(24, len(child) // LOADS)
    loads = [child.iloc[i * size : (i + 1) * size] for i in range(len(child) // size)]
    ref, val = int(len(loads) * 0.4), int(len(loads) * 0.6)
    validation = [rf.orphan_share(fk, tables, load) for load in loads[ref:val]]
    threshold = float(np.quantile(validation, 1.0 - BUDGET))
    test = loads[val:]
    rng = np.random.default_rng([seed, level])
    count = max(1, int(round(FAULT_SHARE * len(test))))
    faulty = sorted(int(i) for i in rng.permutation(len(test))[:count])
    shares = []
    for position, load in enumerate(test):
        if position in faulty:
            load, _ = rf.inject_orphans(fk, tables, load.copy(), level, rng)
        shares.append(rf.orphan_share(fk, tables, load))
    alerts = np.array(shares) > threshold
    mask = np.isin(np.arange(len(test)), faulty)
    return {
        "recall": float(alerts[mask].mean()),
        "false_alert_rate": float(alerts[~mask].mean()),
        "threshold": threshold,
        "loads": {"validation": len(validation), "test": len(test), "faulty": faulty},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--views", type=Path, default=ROOT / "data/experimental")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    report: dict[str, Any] = {}
    for view, keys in declared_keys(manifest).items():
        names = {n for fk, _ in keys for n in (fk.child, fk.parent)}
        if not all((args.views / view / f"{n}.csv").is_file() for n in names):
            report[view] = {"status": "tables not built locally"}
            continue
        checks = verify(keys, read_tables(args.views, view, names))
        report[view] = {
            "status": "ok" if all(c["match"] for c in checks) else "mismatch",
            "keys": checks,
        }
    report["_unmodelled"] = {f"{v}:{c}": why for (v, c), why in UNMODELLED.items()} | {
        f"{view}:{r['child']}": f"conditional or compound reference to {r['parent']}"
        for view, entry in sorted(manifest.items())
        for r in entry.get("relations", [])
        if (view, r["child"]) not in UNMODELLED
        and not (PLAIN.match(r["child"]) and PLAIN.match(r["parent"]))
    }
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
