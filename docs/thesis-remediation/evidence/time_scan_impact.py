# ruff: noqa: E501
"""Does the pandas-3 fix of `research/time_scan.py` change which columns are scanned?

    python docs/thesis-remediation/evidence/time_scan_impact.py [OUTPUT.json]

Loads `candidate_columns` as it was before the fix (commit fd67310^) and as it is now, applies both to every
table of `data/pool/` read the way `scan` reads it (`uci_loader.read_table`), and writes the number of tables,
the pandas version and the tables on which the two differ. The pool tables are not tracked; the output is the
record of this check.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BEFORE = "fd67310^"


def load(name: str, source: str):
    path = ROOT / "research" / f"_{name}.py"
    path.write_text(source)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        path.unlink()
    return module


def main() -> None:
    sys.path[:0] = [str(ROOT / "research"), str(ROOT / "src")]
    import uci_loader

    old_source = subprocess.run(
        ["git", "show", f"{BEFORE}:research/time_scan.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    old = load("time_scan_before", old_source)
    new = load("time_scan_after", (ROOT / "research" / "time_scan.py").read_text())
    differing, scanned = [], 0
    for table in sorted((ROOT / "data" / "pool").glob("*.csv"), key=lambda p: int(p.stem)):
        frame = uci_loader.read_table(table)
        scanned += 1
        before = [c["column"] for c in old.candidate_columns(frame)]
        after = [c["column"] for c in new.candidate_columns(frame)]
        if before != after:
            differing.append({"table": table.name, "before": before, "after": after})
    report = {
        "pandas": pd.__version__,
        "tables_scanned": scanned,
        "tables_that_differ": len(differing),
        "differences": differing,
    }
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    text = json.dumps(report, indent=2) + "\n"
    if out:
        out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
